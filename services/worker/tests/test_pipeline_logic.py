from app.aggregation.temporal import ObservationRecord, aggregate_track
from app.pipeline.association import associate_plates
from app.pipeline.geometry import BoundingBox, Detection
from app.tracking.tracker import TrackedVehicle


def _obs(frame: int, text: str, conf: float) -> ObservationRecord:
    return ObservationRecord(
        frame_number=frame,
        timestamp=frame / 25.0,
        raw=text,
        normalized=text,
        ocr_confidence=conf,
        plate_confidence=0.9,
        vehicle_confidence=0.9,
        vehicle_type="car",
        plate_box={},
        vehicle_box={},
        plate_area=2000,
        sharpness=100,
        image_full=None,
        image_vehicle=None,
        image_plate=None,
    )


def test_temporal_aggregation_prefers_consistent_high_confidence() -> None:
    records = [
        _obs(1, "MH12AB1234", 0.7),
        _obs(2, "MH12AB1234", 0.88),
        _obs(3, "MH12A81234", 0.55),
        _obs(4, "MH12AB1234", 0.91),
    ]
    result = aggregate_track(12, "car", records, 0.85, 0.65, 0.4)
    assert result.normalized_plate_text == "MH12AB1234"
    assert result.ocr_confidence >= 0.88
    assert len(result.observations) == 4


def test_duplicate_suppression_is_one_unique_per_track() -> None:
    records = [_obs(i, "KA01AB1234", 0.8) for i in range(20)]
    result = aggregate_track(1, "car", records, 0.85, 0.65, 0.4)
    assert result.normalized_plate_text == "KA01AB1234"
    assert result.best_frame is not None


def test_plate_association_prefers_containing_vehicle() -> None:
    v1 = TrackedVehicle(
        track_id=1,
        detection=Detection(BoundingBox(0, 0, 100, 100), "car", 0.9, 1, 0.0),
    )
    v2 = TrackedVehicle(
        track_id=2,
        detection=Detection(BoundingBox(200, 0, 300, 100), "car", 0.9, 1, 0.0),
    )
    plate = Detection(BoundingBox(40, 70, 80, 90), "plate", 0.95, 1, 0.0)
    assigned = associate_plates([v1, v2], [plate])
    assert len(assigned) == 1
    assert assigned[0][0].track_id == 1


def test_plate_association_rejects_uncontained_false_positive() -> None:
    vehicle = TrackedVehicle(
        track_id=1,
        detection=Detection(BoundingBox(0, 0, 100, 100), "car", 0.9, 1, 0.0),
    )
    glare = Detection(BoundingBox(250, 10, 270, 30), "plate", 0.4, 1, 0.0)
    assigned = associate_plates([vehicle], [glare])
    assert assigned == []


def test_plate_association_accepts_nearby_rear_plate() -> None:
    vehicle = TrackedVehicle(
        track_id=1,
        detection=Detection(BoundingBox(0, 0, 100, 100), "car", 0.9, 1, 0.0),
    )
    plate = Detection(BoundingBox(40, 105, 80, 125), "plate", 0.9, 1, 0.0)
    assigned = associate_plates([vehicle], [plate])
    assert len(assigned) == 1
    assert assigned[0][0].track_id == 1


def test_plausible_plate_rejects_square_headlight() -> None:
    import numpy as np
    from app.preprocessing.plates import is_plausible_plate_crop

    img = np.full((40, 40, 3), 240, dtype=np.uint8)
    ok, _, _ = is_plausible_plate_crop(img, 40, 40, 0.9, night=True)
    assert ok is False


def test_plausible_plate_rejects_hazy_low_contrast() -> None:
    import numpy as np
    from app.preprocessing.plates import is_plausible_plate_crop

    img = np.full((30, 90, 3), 80, dtype=np.uint8)
    ok, _, _ = is_plausible_plate_crop(img, 90, 30, 0.9, night=True)
    assert ok is False


def test_plausible_plate_accepts_textured_wide_crop() -> None:
    import numpy as np
    from app.preprocessing.plates import is_plausible_plate_crop

    img = np.zeros((28, 90, 3), dtype=np.uint8)
    img[:] = (70, 70, 70)
    img[:, 12:16] = (220, 220, 220)
    img[:, 40:44] = (20, 20, 20)
    img[:, 68:72] = (220, 220, 220)
    ok, _, _ = is_plausible_plate_crop(img, 90, 28, 0.6, night=True)
    assert ok is True


def test_plausible_plate_rejects_tiny_night_crop() -> None:
    import numpy as np
    from app.preprocessing.plates import is_plausible_plate_crop

    rng = np.random.default_rng(0)
    img = rng.integers(40, 110, (16, 32, 3), dtype=np.uint8)
    ok, _, _ = is_plausible_plate_crop(img, 32, 16, 0.9, night=True)
    assert ok is False


def test_night_plate_save_keeps_native_size() -> None:
    import numpy as np
    from app.preprocessing.plates import enhance_night_plate_crop

    img = np.zeros((28, 90, 3), dtype=np.uint8)
    img[:] = (70, 70, 70)
    img[:, 12:16] = (220, 220, 220)
    out = enhance_night_plate_crop(img)
    assert out.shape[:2] == img.shape[:2]


def test_plausible_plate_accepts_small_textured_night() -> None:
    import numpy as np
    from app.preprocessing.plates import has_plate_evidence

    img = np.zeros((16, 48, 3), dtype=np.uint8)
    img[:] = (70, 70, 70)
    img[:, 6:10] = (220, 220, 220)
    img[:, 20:24] = (20, 20, 20)
    img[:, 34:38] = (220, 220, 220)
    ok, score, _ = has_plate_evidence(img, 48, 16, 0.55, dark=True)
    assert ok is True
    assert score > 0


def test_caption_text_is_not_a_plate() -> None:
    import numpy as np
    from app.preprocessing.plates import has_plate_evidence, is_burned_in_caption

    caption = np.full((48, 280, 3), (12, 12, 12), dtype=np.uint8)
    caption[16:34, 24:70] = (0, 230, 255)
    caption[16:34, 86:150] = (0, 220, 255)
    caption[16:34, 166:230] = (0, 235, 250)
    assert is_burned_in_caption(caption) is True
    ok, _, _ = has_plate_evidence(caption, 280, 48, 0.9, dark=False)
    assert ok is False


def test_yellow_plate_is_not_a_caption() -> None:
    import numpy as np
    from app.preprocessing.plates import is_burned_in_caption

    plate = np.full((40, 160, 3), (0, 210, 240), dtype=np.uint8)
    for x in range(12, 140, 16):
        plate[8:32, x : x + 4] = (15, 15, 15)
    assert is_burned_in_caption(plate) is False


def test_day_plate_rejects_blurry_or_tiny_crop() -> None:
    import cv2
    import numpy as np
    from app.preprocessing.plates import has_plate_evidence

    sharp = np.full((36, 140, 3), 235, dtype=np.uint8)
    for x in range(10, 130, 12):
        sharp[6:30, x : x + 3] = 12
    ok, _, _ = has_plate_evidence(sharp, 140, 36, 0.8, dark=False, frame_width=1920)
    assert ok is True

    blur = cv2.GaussianBlur(sharp, (21, 21), 0)
    ok, _, _ = has_plate_evidence(blur, 140, 36, 0.8, dark=False, frame_width=1920)
    assert ok is False
    ok, _, _ = has_plate_evidence(sharp, 48, 16, 0.9, dark=False, frame_width=1920)
    assert ok is False

    small = np.full((18, 42, 3), 230, dtype=np.uint8)
    for x in range(4, 38, 8):
        small[3:15, x : x + 2] = 15
    ok, _, _ = has_plate_evidence(small, 42, 18, 0.75, dark=False, frame_width=848)
    assert ok is True


def test_hard_false_positive_rejects_empty_structure() -> None:
    import numpy as np
    from app.preprocessing.plates import is_hard_false_positive

    img = np.full((28, 80, 3), 80, dtype=np.uint8)
    assert is_hard_false_positive(img, 80, 28, 0.9) is True


def test_remap_plate_box_adds_roi_origin() -> None:
    from app.pipeline.geometry import BoundingBox
    from app.pipeline.plate_search import remap_plate_box

    local = BoundingBox(10, 4, 40, 16)
    mapped = remap_plate_box(local, 100, 50)
    assert mapped.x1 == 110
    assert mapped.y1 == 54
    assert mapped.x2 == 140
    assert mapped.y2 == 66


def test_crop_vehicle_roi_origin_matches_asymmetric_pad() -> None:
    import numpy as np
    from app.pipeline.geometry import BoundingBox
    from app.pipeline.plate_search import crop_vehicle_roi

    frame = np.zeros((200, 200, 3), dtype=np.uint8)
    box = BoundingBox(40, 40, 100, 120)
    crop, ox, oy = crop_vehicle_roi(frame, box, "car")
    assert crop.size > 0
    assert ox <= 40
    assert oy <= 40
    assert ox + crop.shape[1] >= 100
    assert oy + crop.shape[0] >= 120


def test_prepare_roi_skips_enhance_on_bright_crop() -> None:
    import numpy as np
    from app.pipeline.plate_search import prepare_roi_for_detect

    bright = np.full((40, 80, 3), 180, dtype=np.uint8)
    out = prepare_roi_for_detect(bright)
    assert np.array_equal(out, bright)


def test_tiny_vehicle_boxes_are_not_searched_for_plates() -> None:
    import numpy as np
    from app.pipeline.geometry import BoundingBox, Detection
    from app.pipeline.plate_search import search_plates_in_vehicles
    from app.tracking.tracker import TrackedVehicle

    class _NoopDetector:
        def detect_many(self, *args, **kwargs):
            raise AssertionError("tiny vehicles must not trigger plate YOLO")

    vehicle = TrackedVehicle(
        track_id=3,
        detection=Detection(BoundingBox(0, 0, 20, 20), "car", 0.9, 1, 0.0),
    )
    assigned = search_plates_in_vehicles(
        np.zeros((80, 80, 3), dtype=np.uint8),
        [vehicle],
        _NoopDetector(),
        1,
        0.0,
    )
    assert assigned == []


def test_plate_index_item_includes_overlay_and_confidence() -> None:
    from packages.capture_index import plate_index_item

    clock = {"origin_iso": "2026-09-16T21:07:48"}
    item = plate_index_item(12, 0.0, 2.0, "car", clock, plate_confidence=0.81, vehicle_confidence=0.9)
    assert item["vehicle_type"] == "car"
    assert item["captured_at"] == "16-09-2026 09:07:48 PM"
    assert item["last_seen_overlay"] == "16-09-2026 09:07:50 PM"
    assert item["plate_confidence"] == 0.81


def _plate_bars() -> "object":
    import numpy as np

    img = np.zeros((20, 60, 3), dtype=np.uint8)
    img[:] = (70, 70, 70)
    img[:, 8:12] = (220, 220, 220)
    img[:, 28:32] = (20, 20, 20)
    img[:, 48:52] = (220, 220, 220)
    return img


def test_same_second_similar_plate_merges_to_existing_track() -> None:
    from app.pipeline.capture_merge import find_same_passage

    plate = _plate_bars()
    best = {
        15: {
            "first_seen": 21.2,
            "last_seen": 21.4,
            "vehicle_box": {"x1": 10, "y1": 10, "x2": 80, "y2": 90},
            "image_plate": plate,
        }
    }
    merged = find_same_passage(
        best,
        21.6,
        {"x1": 18, "y1": 14, "x2": 86, "y2": 92},
        plate,
        exclude_track_id=183,
    )
    assert merged == 15


def test_later_pass_same_plate_is_new_row() -> None:
    from app.pipeline.capture_merge import find_same_passage

    plate = _plate_bars()
    best = {
        15: {
            "first_seen": 21.2,
            "last_seen": 21.8,
            "vehicle_box": {"x1": 10, "y1": 10, "x2": 80, "y2": 90},
            "image_plate": plate,
        }
    }
    merged = find_same_passage(
        best,
        48.0,
        {"x1": 18, "y1": 14, "x2": 86, "y2": 92},
        plate,
        exclude_track_id=200,
    )
    assert merged is None


def _candidate(quality: float, frame: int, tag: str) -> dict:
    import numpy as np

    plate = np.full((8, 24, 3), ord(tag[0]) % 200, dtype=np.uint8)
    return {
        "quality": quality,
        "sharp": quality * 400,
        "plate_area": 1000.0,
        "contrast": 20.0,
        "best_frame": frame,
        "timestamp": frame / 25.0,
        "plate_confidence": 0.8,
        "vehicle_confidence": 0.9,
        "vehicle_type": "car",
        "plate_box": {"x1": 0, "y1": 0, "x2": 24, "y2": 8},
        "vehicle_box": {"x1": 0, "y1": 0, "x2": 40, "y2": 40},
        "image_full": plate,
        "image_vehicle": plate,
        "image_plate": plate,
        "observation": {
            "frame_number": frame,
            "timestamp": frame / 25.0,
            "plate_confidence": 0.8,
            "bounding_box": {"x1": 0, "y1": 0, "x2": 24, "y2": 8},
        },
        "source_ids": {1},
        "active_tid": 1,
    }


def test_plate_frame_quality_prefers_sharp_over_large_blur() -> None:
    from app.preprocessing.plates import plate_frame_quality

    sharp_small = plate_frame_quality(sharp=280, plate_area=5000, plate_confidence=0.8, contrast=30)
    blur_large = plate_frame_quality(sharp=25, plate_area=18000, plate_confidence=0.8, contrast=30)
    assert sharp_small > blur_large


def test_consider_plate_candidate_keeps_highest_quality() -> None:
    from app.preprocessing.plates import consider_plate_candidate

    capture = consider_plate_candidate(None, _candidate(0.40, 1, "a"))
    capture = consider_plate_candidate(capture, _candidate(0.70, 5, "b"))
    capture = consider_plate_candidate(capture, _candidate(0.50, 8, "c"))
    capture = consider_plate_candidate(capture, _candidate(0.20, 9, "d"))
    assert capture["best_frame"] == 5
    assert capture["quality"] == 0.70
    assert len(capture["observations"]) == 4
    assert capture["last_seen"] == 9 / 25.0
    alts = capture["alternates"]
    assert len(alts) == 2
    assert alts[0]["quality"] == 0.50
    assert alts[1]["quality"] == 0.40


def test_vehicle_capture_pads_keep_bumper_context() -> None:
    from app.pipeline.plate_search import ROI_IMAGE_SIZE, vehicle_capture_pads
    from app.preprocessing.plates import VEHICLE_CROP_PAD

    car = vehicle_capture_pads("car")
    moto = vehicle_capture_pads("motorcycle")
    assert car[0] == VEHICLE_CROP_PAD
    assert car[3] > car[1]
    assert moto[3] > car[3]
    assert ROI_IMAGE_SIZE == 640


def test_save_jpeg_writes_quality_param(tmp_path) -> None:
    import numpy as np
    from app.preprocessing.plates import JPEG_PLATE_QUALITY, save_jpeg

    img = np.zeros((24, 80, 3), dtype=np.uint8)
    img[:] = (30, 40, 50)
    dest = tmp_path / "plate.jpg"
    save_jpeg(dest, img, JPEG_PLATE_QUALITY)
    assert dest.is_file()
    assert dest.stat().st_size > 0


def test_capture_publishes_after_unseen_delay() -> None:
    from app.pipeline.runner import capture_is_due_to_publish

    pending = {"published": False, "last_seen": 1.0}
    assert capture_is_due_to_publish(pending, visible=True, now_ts=10.0) is False
    assert capture_is_due_to_publish(pending, visible=False, now_ts=1.2) is False
    assert capture_is_due_to_publish(pending, visible=False, now_ts=1.5) is True
    assert capture_is_due_to_publish({"published": True, "last_seen": 1.0}, visible=False, now_ts=10.0) is False


def test_publish_track_capture_writes_once(tmp_path) -> None:
    import numpy as np
    from app.pipeline.runner import _publish_track_capture

    img = np.zeros((20, 40, 3), dtype=np.uint8)
    capture = {
        "image_plate": img,
        "image_vehicle": img,
        "image_full": img,
        "first_seen": 1.0,
        "last_seen": 2.0,
        "vehicle_type": "car",
        "plate_confidence": 0.8,
        "vehicle_confidence": 0.9,
        "alternates": [
            {"image_plate": img, "quality": 0.5},
            {"image_plate": img, "quality": 0.4},
        ],
    }
    assert _publish_track_capture(tmp_path, 3, capture, None) is True
    assert (tmp_path / "track_3.jpg").is_file()
    assert (tmp_path / "vehicle_3.jpg").is_file()
    assert (tmp_path / "full_3.jpg").is_file()
    assert (tmp_path / "track_3_alt1.jpg").is_file()
    assert (tmp_path / "track_3_alt2.jpg").is_file()
    assert capture["published"] is True
    assert _publish_track_capture(tmp_path, 3, capture, None) is False


def test_publish_startup_frame_writes_live_and_raw(tmp_path) -> None:
    import cv2
    import numpy as np
    from app.pipeline.runner import _publish_startup_frame

    video = tmp_path / "clip.mp4"
    writer = cv2.VideoWriter(str(video), cv2.VideoWriter_fourcc(*"mp4v"), 5.0, (64, 48))
    frame = np.full((48, 64, 3), 90, dtype=np.uint8)
    writer.write(frame)
    writer.release()
    live = tmp_path / "live.jpg"
    raw = tmp_path / "live_raw.jpg"
    assert _publish_startup_frame(video, live, raw) is True
    assert live.is_file()
    assert raw.is_file()
    assert raw.stat().st_size >= live.stat().st_size


def test_public_error_includes_exception_type() -> None:
    from app.pipeline.runner import _public_error

    message = _public_error(ValueError("Unable to open video"))
    assert message.startswith("ValueError:")
    assert "Unable to open video" in message


def test_annotated_writer_accepts_odd_frame_size(tmp_path) -> None:
    import numpy as np
    from app.rendering.annotate import AnnotatedVideoRenderer

    path = tmp_path / "out.mp4"
    renderer = AnnotatedVideoRenderer(path, 8.0, (63, 47))
    renderer.write(np.full((47, 63, 3), 40, dtype=np.uint8))
    renderer.close()
    assert path.is_file()
    assert path.stat().st_size > 0
