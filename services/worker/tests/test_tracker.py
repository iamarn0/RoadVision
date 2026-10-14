import numpy as np

from app.pipeline.geometry import BoundingBox, Detection
from app.tracking.tracker import VehicleTracker, coerce_track_id


def test_coerce_track_id_rejects_nan_none_and_negative() -> None:
    assert coerce_track_id(None) is None
    assert coerce_track_id(float("nan")) is None
    assert coerce_track_id(float("inf")) is None
    assert coerce_track_id(-1) is None
    assert coerce_track_id(12) == 12
    assert coerce_track_id(12.0) == 12

    class _Tensor:
        def item(self):
            return float("nan")

    assert coerce_track_id(_Tensor()) is None

    class _Good:
        def item(self):
            return 7

    assert coerce_track_id(_Good()) == 7


class _Box:
    def __init__(self, xyxy, conf, cls_id) -> None:
        self.xyxy = [np.asarray(xyxy, dtype=float)]
        self.conf = [conf]
        self.cls = [cls_id]


class _Boxes:
    def __init__(self, boxes, ids) -> None:
        self._boxes = boxes
        self.id = ids

    def __iter__(self):
        return iter(self._boxes)


class _Result:
    def __init__(self, boxes) -> None:
        self.boxes = boxes
        self.names = {2: "car"}


class _TrackModel:
    def __init__(self, id_frames: list) -> None:
        self.id_frames = id_frames
        self.calls = 0

    def track(self, image, **kwargs):
        ids = self.id_frames[min(self.calls, len(self.id_frames) - 1)]
        self.calls += 1
        box = _Box([10.0, 10.0, 80.0, 80.0], 0.9, 2)
        id_tensor = None if ids is None else np.asarray(ids, dtype=float)
        return [_Result(_Boxes([box], id_tensor))]


class _Detector:
    confidence = 0.35
    iou = 0.45
    image_size = 64
    device = "cpu"
    half = False

    def __init__(self, model=None) -> None:
        self.model = model

    def detect(self, image, frame_number, timestamp, confidence=None):
        return [Detection(BoundingBox(10, 10, 80, 80), "car", 0.9, frame_number, timestamp)]


def _blank() -> np.ndarray:
    return np.zeros((100, 100, 3), dtype=np.uint8)


def test_missing_bytetrack_ids_keep_the_same_vehicle() -> None:
    tracker = VehicleTracker(_Detector(_TrackModel([None] * 8)))
    ids = []
    for frame in range(8):
        vehicles = tracker.update(_blank(), frame, frame / 25.0)
        assert len(vehicles) == 1
        ids.append(vehicles[0].track_id)
    assert ids == [ids[0]] * 8
    assert ids[0] == 1


def test_nan_ids_do_not_mint_a_new_id_each_frame() -> None:
    nans = [[float("nan")] for _ in range(12)]
    tracker = VehicleTracker(_Detector(_TrackModel(nans)))
    seen = []
    for frame in range(12):
        vehicles = tracker.update(_blank(), frame, frame / 25.0)
        assert len(vehicles) == 1
        seen.append(vehicles[0].track_id)
    assert max(seen) == min(seen)
    assert len(set(seen)) == 1


def test_confirmed_id_survives_a_nan_gap() -> None:
    tracker = VehicleTracker(_Detector(_TrackModel([[4], [float("nan")], [4]])))
    first = tracker.update(_blank(), 0, 0.0)
    gap = tracker.update(_blank(), 1, 0.04)
    back = tracker.update(_blank(), 2, 0.08)
    assert [v.track_id for v in first] == [4]
    assert [v.track_id for v in gap] == [4]
    assert [v.track_id for v in back] == [4]


def test_unconfirmed_boxes_do_not_steal_new_ids_when_bytetrack_is_live() -> None:
    class _TwoBoxModel:
        def track(self, image, **kwargs):
            confirmed = _Box([10.0, 10.0, 80.0, 80.0], 0.9, 2)
            extra = _Box([200.0, 10.0, 260.0, 70.0], 0.4, 2)
            return [_Result(_Boxes([confirmed, extra], np.asarray([3.0, float("nan")])))]

    tracker = VehicleTracker(_Detector(_TwoBoxModel()))
    vehicles = tracker.update(_blank(), 0, 0.0)
    assert [v.track_id for v in vehicles] == [3]


def test_iou_fallback_keeps_id_when_boxes_overlap() -> None:
    tracker = VehicleTracker(_Detector(model=None))
    first = tracker.update(_blank(), 0, 0.0)
    second = tracker.update(_blank(), 1, 0.04)
    assert first[0].track_id == second[0].track_id
