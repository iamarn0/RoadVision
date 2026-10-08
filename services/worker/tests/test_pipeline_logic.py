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
    img = rng.integers(40, 110, (8, 18, 3), dtype=np.uint8)
    ok, _, _ = is_plausible_plate_crop(img, 18, 8, 0.9, night=True)
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
    tiny = np.full((8, 20, 3), 230, dtype=np.uint8)
    for x in range(2, 18, 4):
        tiny[2:6, x : x + 1] = 15
    ok, _, _ = has_plate_evidence(tiny, 20, 8, 0.9, dark=False, frame_width=1920)
    assert ok is False

    small = np.full((18, 42, 3), 230, dtype=np.uint8)
    for x in range(4, 38, 8):
        small[3:15, x : x + 2] = 15
    ok, _, _ = has_plate_evidence(small, 42, 18, 0.75, dark=False, frame_width=848)
    assert ok is True


def test_high_resolution_rejects_motion_blur() -> None:
    import cv2
    import numpy as np
    from app.preprocessing.plates import has_plate_evidence

    sharp = np.full((80, 280, 3), 235, dtype=np.uint8)
    for x in range(16, 260, 22):
        sharp[12:68, x : x + 6] = 12
    ok, _, _ = has_plate_evidence(sharp, 280, 80, 0.85, dark=False, frame_width=2500)
    assert ok is True
    smeared = cv2.GaussianBlur(sharp, (41, 41), 0)
    ok, _, _ = has_plate_evidence(smeared, 280, 80, 0.85, dark=False, frame_width=2500)
    assert ok is False


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


def test_plate_outside_vehicle_body_is_not_attached() -> None:
    import numpy as np
    from app.pipeline.geometry import BoundingBox, Detection
    from app.pipeline.plate_search import crop_vehicle_roi, search_plates_in_vehicles
    from app.tracking.tracker import TrackedVehicle

    frame = np.zeros((240, 480, 3), dtype=np.uint8)
    vehicle = TrackedVehicle(
        track_id=1,
        detection=Detection(BoundingBox(30, 40, 150, 180), "car", 0.9, 1, 0.0),
    )
    _crop, ox, oy = crop_vehicle_roi(frame, vehicle.detection.bounding_box, "car")

    class Detector:
        def detect_many(self, images, frame_number, timestamp, confidence=None, image_size=None):
            # A clear plate sitting on the next car, to the right of this body.
            local = BoundingBox(300 - ox, 90 - oy, 360 - ox, 120 - oy)
            return [[Detection(local, "license_plate", 0.95, frame_number, timestamp)]]

    assigned = search_plates_in_vehicles(frame, [vehicle], Detector(), 1, 0.0)
    assert assigned == []


def test_same_plate_seen_in_two_rois_stays_with_the_car_that_contains_it() -> None:
    import numpy as np
    from app.pipeline.geometry import BoundingBox, Detection
    from app.pipeline.plate_search import crop_vehicle_roi, search_plates_in_vehicles
    from app.tracking.tracker import TrackedVehicle

    frame = np.zeros((240, 480, 3), dtype=np.uint8)
    owner = TrackedVehicle(
        track_id=1,
        detection=Detection(BoundingBox(40, 40, 180, 190), "car", 0.9, 1, 0.0),
    )
    neighbour = TrackedVehicle(
        track_id=2,
        detection=Detection(BoundingBox(190, 40, 340, 190), "car", 0.9, 1, 0.0),
    )
    plate = BoundingBox(70, 150, 140, 175)

    class Detector:
        def detect_many(self, images, frame_number, timestamp, confidence=None, image_size=None):
            batches = []
            for vehicle in (owner, neighbour):
                _crop, ox, oy = crop_vehicle_roi(frame, vehicle.detection.bounding_box, "car")
                local = BoundingBox(plate.x1 - ox, plate.y1 - oy, plate.x2 - ox, plate.y2 - oy)
                batches.append([Detection(local, "license_plate", 0.95, frame_number, timestamp)])
            return batches

    assigned = search_plates_in_vehicles(frame, [owner, neighbour], Detector(), 1, 0.0)
    assert [vehicle.track_id for vehicle, _plate in assigned] == [1]


def test_duplicate_plate_captures_collapse_to_one_row() -> None:
    from app.pipeline.capture_merge import collapse_duplicate_captures

    plate = _plate_bars()
    best = {
        4: {
            "first_seen": 1.0,
            "last_seen": 1.4,
            "quality": 0.4,
            "vehicle_box": {"x1": 10, "y1": 20, "x2": 80, "y2": 90},
            "image_plate": plate,
            "source_ids": {4},
        },
        19: {
            "first_seen": 1.8,
            "last_seen": 2.2,
            "quality": 0.8,
            "vehicle_box": {"x1": 200, "y1": 20, "x2": 280, "y2": 100},
            "image_plate": plate,
            "source_ids": {19},
        },
    }
    merged = collapse_duplicate_captures(best)
    assert merged == [(19, 4)] or set(merged) == {(19, 4)}
    assert list(best) == [19]
    assert 4 in best[19]["source_ids"]


def test_vehicle_only_duplicate_collapses_into_plate_row() -> None:
    import numpy as np
    from app.pipeline.capture_merge import collapse_duplicate_captures

    plate = _plate_bars()
    vehicle = np.zeros((30, 40, 3), dtype=np.uint8)
    best = {
        4: {
            "first_seen": 1.0,
            "last_seen": 2.0,
            "quality": 0.7,
            "vehicle_box": {"x1": 10, "y1": 10, "x2": 90, "y2": 80},
            "image_plate": plate,
            "image_vehicle": vehicle,
            "source_ids": {4},
        },
        9: {
            "first_seen": 2.1,
            "last_seen": 2.4,
            "vehicle_only": True,
            "vehicle_box": {"x1": 16, "y1": 14, "x2": 96, "y2": 86},
            "image_vehicle": vehicle,
            "source_ids": {9},
        },
    }
    collapse_duplicate_captures(best)
    assert list(best) == [4]
    assert 9 in best[4]["source_ids"]
    assert best[4].get("vehicle_only") is not True


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
    low = plate_index_item(3, 0.0, 1.0, "car", None, plate_width=60)
    assert low["good_evidence"] is False
    assert low["plate_width"] == 60.0


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


def test_plate_frame_quality_prefers_larger_readable_over_tiny_noise() -> None:
    from app.preprocessing.plates import plate_frame_quality

    readable = plate_frame_quality(sharp=45, plate_area=182 * 53, plate_confidence=0.6, contrast=28)
    tiny_noisy = plate_frame_quality(sharp=300, plate_area=40 * 14, plate_confidence=0.9, contrast=35)
    assert readable > tiny_noisy


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
    assert ROI_IMAGE_SIZE == 416


def test_diagnostics_writes_json_not_info_png_when_enabled(tmp_path) -> None:
    import numpy as np
    from app.pipeline.candidates import PlateCandidateStore
    from app.pipeline.diagnostics import video_summary, write_diagnostics
    from app.preprocessing.quality import DEFAULT_QUALITY

    store = PlateCandidateStore(top_n=4)
    plate = np.full((20, 60, 3), 90, dtype=np.uint8)
    store.record_detection(
        127,
        width=182,
        height=53,
        accepted=True,
        candidate={
            "frame_number": 530,
            "timestamp": 21.2,
            "plate_bbox": {"x1": 1, "y1": 2, "x2": 183, "y2": 55},
            "plate_width": 182,
            "plate_height": 53,
            "plate_area": 182 * 53,
            "plate_detection_confidence": 0.8,
            "sharpness_score": 40.0,
            "contrast_score": 22.0,
            "brightness_score": 140.0,
            "saturation_ratio": 0.01,
            "exposure_score": 0.9,
            "geometry_score": 0.95,
            "total_score": 0.7,
            "image_plate": plate,
        },
    )
    summary = video_summary(
        width=2688,
        height=1520,
        fps=25.0,
        duration=180.0,
        frame_count=4500,
        vehicle_meta={127: {"first_frame": 400, "last_frame": 649, "frame_count": 250, "type": "bus"}},
        store=store,
        captures={127: {"best_frame": 530}},
        config=DEFAULT_QUALITY,
    )
    dest = tmp_path / "diagnostics"
    write_diagnostics(dest, summary, store, save_candidate_png=True)
    assert (dest / "summary.json").is_file()
    assert (dest / "track_127.json").is_file()
    assert (dest / "track_127" / "frame_530.png").is_file()
    assert summary["plates"]["vehicles_with_usable_quality_candidate"] == 1
    assert "Vehicle ID: 127" in (dest / "track_127.json").read_text(encoding="utf-8")


def test_save_jpeg_writes_quality_param(tmp_path) -> None:
    import numpy as np
    from app.preprocessing.plates import JPEG_PLATE_QUALITY, save_jpeg

    img = np.zeros((24, 80, 3), dtype=np.uint8)
    img[:] = (30, 40, 50)
    dest = tmp_path / "plate.jpg"
    save_jpeg(dest, img, JPEG_PLATE_QUALITY)
    assert dest.is_file()
    assert dest.stat().st_size > 0


def test_apply_store_winners_uses_buffer_crop() -> None:
    import numpy as np
    from app.pipeline.candidates import PlateCandidateStore
    from app.pipeline.runner import _apply_store_winners

    store = PlateCandidateStore(top_n=5)
    winner_img = np.full((16, 48, 3), 200, dtype=np.uint8)
    other = np.full((16, 48, 3), 10, dtype=np.uint8)
    store.record_detection(
        4,
        width=48,
        height=16,
        accepted=True,
        candidate={"frame_number": 12, "total_score": 0.2, "image_plate": other},
    )
    store.record_detection(
        4,
        width=90,
        height=28,
        accepted=True,
        candidate={"frame_number": 40, "total_score": 0.9, "image_plate": winner_img, "plate_bbox": {"x1": 1}},
    )
    capture = {"image_plate": other, "best_frame": 12, "quality": 0.2}
    _apply_store_winners({4: capture}, store)
    assert capture["best_frame"] == 40
    assert capture["image_plate"] is winner_img


def test_capture_publishes_after_unseen_delay() -> None:
    from app.pipeline.runner import capture_is_due_to_publish

    pending = {"published": False, "last_seen": 1.0}
    assert capture_is_due_to_publish(pending, visible=True, now_ts=10.0) is False
    assert capture_is_due_to_publish(pending, visible=False, now_ts=1.2) is False
    assert capture_is_due_to_publish(pending, visible=False, now_ts=1.5) is True
    assert capture_is_due_to_publish({"published": True, "last_seen": 1.0}, visible=False, now_ts=10.0) is False


def test_end_of_video_publishes_vehicle_still_in_frame(tmp_path) -> None:
    import numpy as np
    from app.pipeline.runner import (
        _publish_all_pending,
        _queue_vehicles_still_in_frame,
        capture_is_due_to_publish,
    )

    img = np.zeros((20, 40, 3), dtype=np.uint8)
    capture = {
        "published": False,
        "image_plate": img,
        "image_vehicle": img,
        "image_full": img,
        "first_seen": 8.0,
        "last_seen": 10.0,
        "vehicle_type": "car",
        "plate_confidence": 0.8,
        "vehicle_confidence": 0.9,
    }
    assert capture_is_due_to_publish(capture, visible=True, now_ts=10.0) is False
    assert _publish_all_pending(tmp_path, {7: capture}, None) == 1
    assert (tmp_path / "track_7.jpg").is_file()
    assert (tmp_path / "vehicle_7.jpg").is_file()
    assert (tmp_path / "full_7.jpg").is_file()
    assert capture["published"] is True

    still = tmp_path / "still"
    still.mkdir()
    vehicle = np.zeros((30, 50, 3), dtype=np.uint8)
    best: dict = {}
    meta = {
        9: {"type": "car", "first_seen": 2.0, "last_seen": 34.8, "last_frame": 870, "conf": 0.8},
        5: {"type": "car", "first_seen": 1.0, "last_seen": 17.0, "last_frame": 435, "conf": 0.7},
    }
    crops = {
        9: {"image": vehicle, "frame": 870},
        5: {"image": vehicle, "frame": 435},
    }
    _queue_vehicles_still_in_frame(best, meta, crops, final_index=873, source_fps=25.0)
    assert 9 in best
    assert 5 not in best
    assert best[9]["vehicle_only"] is True
    assert _publish_all_pending(still, best, None) == 1
    assert (still / "vehicle_9.jpg").is_file()
    assert not (still / "track_9.jpg").exists()
    sidecar = (still / "track_9.json").read_text(encoding="utf-8")
    assert '"kind": "vehicle"' in sidecar


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
    assert (tmp_path / "track_3.png").is_file()
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


def test_two_wheelers_map_to_motorcycle() -> None:
    from app.detection.detector import VEHICLE_CLASS_MAP

    for name in ("motorcycle", "motorbike", "bike", "bicycle", "scooter", "moped"):
        assert VEHICLE_CLASS_MAP[name] == "motorcycle"


def test_working_image_scale_maps_back_to_native() -> None:
    import numpy as np
    from app.pipeline.geometry import BoundingBox
    from app.pipeline.plate_search import make_working_image

    image = np.zeros((2160, 3840, 3), dtype=np.uint8)
    working, scale = make_working_image(image)
    assert working.shape[1] == 960
    assert working.shape[0] == 540
    native = BoundingBox(10, 20, 30, 40).scaled(scale, scale)
    assert native.x1 == 40
    assert native.y1 == 80
    assert native.x2 == 120
    assert native.y2 == 160


def test_unattached_plate_is_kept_and_drawn() -> None:
    import numpy as np
    from app.pipeline.association import associate_plates, unassigned_plates
    from app.pipeline.geometry import BoundingBox, Detection
    from app.rendering.annotate import draw_overlay
    from app.tracking.tracker import TrackedVehicle

    vehicle = TrackedVehicle(
        track_id=1,
        detection=Detection(BoundingBox(0, 0, 40, 40), "car", 0.9, 1, 0.0),
    )
    near = Detection(BoundingBox(10, 20, 30, 35), "license_plate", 0.9, 1, 0.0)
    far = Detection(BoundingBox(200, 200, 260, 230), "license_plate", 0.8, 1, 0.0)
    assigned = associate_plates([vehicle], [near, far])
    loose = unassigned_plates([near, far], assigned)
    assert near not in loose
    assert far in loose
    frame = np.zeros((300, 320, 3), dtype=np.uint8)
    out = draw_overlay(frame, [], [], loose_plates=[far])
    x1, y1, _x2, _y2 = far.bounding_box.as_int()
    assert tuple(int(channel) for channel in out[y1, x1]) == (201, 146, 42)


def test_grab_skips_frames_without_decoding(tmp_path) -> None:
    import cv2
    import numpy as np
    from app.pipeline.video_source import UploadedFileSource

    video = tmp_path / "clip.mp4"
    writer = cv2.VideoWriter(str(video), cv2.VideoWriter_fourcc(*"mp4v"), 5.0, (32, 32))
    for value in range(6):
        writer.write(np.full((32, 32, 3), value * 20, dtype=np.uint8))
    writer.release()
    source = UploadedFileSource(video)
    source.open()
    try:
        first = source.read()
        assert first is not None and first.index == 0
        assert source.grab(2) == 2
        later = source.read()
        assert later is not None and later.index == 3
    finally:
        source.close()


def test_playback_strides_sample_about_four_fps() -> None:
    from app.pipeline.runner import _playback_strides, _preview_size

    preview, vehicle, plate, preview_fps = _playback_strides(25)
    assert preview == vehicle == plate == 6
    assert 4.0 <= preview_fps <= 4.3
    behind_preview, behind_vehicle, behind_plate, behind_fps = _playback_strides(25, behind=True)
    assert behind_preview == behind_vehicle == behind_plate == 6
    assert behind_fps == preview_fps
    fast_preview, fast_vehicle, fast_plate, fast_fps = _playback_strides(100)
    assert fast_preview == fast_vehicle == fast_plate
    assert fast_fps == 4.0
    assert _preview_size(2500, 1400)[0] == 1280


def test_consider_prefers_readable_width_over_sharper_tiny_crop() -> None:
    from app.preprocessing.plates import consider_plate_candidate

    tiny = _candidate(0.9, 1, "a")
    tiny["plate_width"] = 40
    tiny["good_evidence"] = False
    wide = _candidate(0.4, 5, "b")
    wide["plate_width"] = 120
    wide["good_evidence"] = True
    capture = consider_plate_candidate(None, tiny)
    assert capture["good_evidence"] is False
    capture = consider_plate_candidate(capture, wide)
    assert capture["best_frame"] == 5
    assert capture["good_evidence"] is True


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
