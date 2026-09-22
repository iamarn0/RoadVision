import numpy as np

from app.pipeline.candidates import PlateCandidateStore
from app.pipeline.geometry import BoundingBox
from app.pipeline.plate_search import crop_from_original, map_resized_box_to_original
from app.preprocessing.quality import (
    DEFAULT_QUALITY,
    brightness_value,
    contrast_value,
    evaluate_plate_crop,
    exposure_score,
    rank_score,
    saturation_ratio,
    sharpness_value,
    size_score,
)


def _bar_plate(width: int, height: int, *, blur: int = 0, fill: int = 220, bar: int = 18) -> np.ndarray:
    import cv2

    img = np.full((height, width, 3), fill, dtype=np.uint8)
    step = max(8, width // 12)
    for x in range(6, width - 6, step):
        img[3 : height - 3, x : x + 3] = bar
    if blur:
        k = blur if blur % 2 == 1 else blur + 1
        img = cv2.GaussianBlur(img, (k, k), 0)
    return img


def test_plate_size_and_size_score() -> None:
    from app.preprocessing.quality import plate_width_band

    assert size_score(182, 53) == 1.0
    assert size_score(91, 26) < 0.5
    assert size_score(20, 8) < size_score(182, 53)
    assert size_score(120, 35) == 1.0
    assert plate_width_band(60) == "low"
    assert plate_width_band(80) == "narrow"
    assert plate_width_band(120) == "target"
    assert plate_width_band(182) == "wide"


def test_saturation_ratio_on_clipped_white() -> None:
    white = np.full((40, 120, 3), 255, dtype=np.uint8)
    gray = np.full((40, 120, 3), 80, dtype=np.uint8)
    assert saturation_ratio(white) == 1.0
    assert saturation_ratio(gray) == 0.0


def test_sharpness_drops_on_blur() -> None:
    sharp = _bar_plate(182, 53)
    blur = _bar_plate(182, 53, blur=21)
    assert sharpness_value(sharp) > sharpness_value(blur)
    assert sharpness_value(blur) < DEFAULT_QUALITY.min_sharpness


def test_contrast_and_exposure() -> None:
    plate = _bar_plate(182, 53)
    flat = np.full((53, 182, 3), 80, dtype=np.uint8)
    assert contrast_value(plate) > contrast_value(flat)
    assert exposure_score(128) == 1.0
    assert exposure_score(0) == 0.0
    assert exposure_score(255) < 0.05
    assert 0.4 < exposure_score(brightness_value(plate)) <= 1.0


def test_dark_ranking_penalizes_bloom_more_than_daylight() -> None:
    from app.preprocessing.quality import DEFAULT_QUALITY, config_for_dark

    shared = dict(width=140, height=40, sharpness=80, contrast=30, detector_confidence=0.7)
    clear = dict(brightness=140, sat_ratio=0.02, **shared)
    bloom = dict(brightness=230, sat_ratio=0.40, **shared)
    day_clear, _ = rank_score(**clear)
    day_bloom, _ = rank_score(**bloom)
    night = config_for_dark(DEFAULT_QUALITY)
    night_clear, _ = rank_score(**clear, config=night)
    night_bloom, _ = rank_score(**bloom, config=night)
    assert day_clear > day_bloom
    assert (night_clear - night_bloom) > (day_clear - day_bloom)


def test_evaluate_flags_plate_narrower_than_75px() -> None:
    narrow = _bar_plate(60, 18)
    wide = _bar_plate(120, 36)
    narrow_metrics = evaluate_plate_crop(narrow, 60, 18, 0.8)
    wide_metrics = evaluate_plate_crop(wide, 120, 36, 0.8)
    assert narrow_metrics.extra["good_evidence"] is False
    assert narrow_metrics.extra["width_band"] == "low"
    assert wide_metrics.extra["good_evidence"] is True
    assert wide_metrics.extra["width_band"] == "target"


def test_candidate_store_prefers_readable_width_over_higher_score() -> None:
    store = PlateCandidateStore(top_n=2)
    store.record_detection(
        4,
        width=40,
        height=14,
        accepted=True,
        candidate={
            "frame_number": 1,
            "total_score": 0.95,
            "plate_width": 40,
            "good_evidence": False,
            "image_plate": np.zeros((8, 24, 3), dtype=np.uint8),
        },
    )
    store.record_detection(
        4,
        width=120,
        height=36,
        accepted=True,
        candidate={
            "frame_number": 8,
            "total_score": 0.4,
            "plate_width": 120,
            "good_evidence": True,
            "image_plate": np.zeros((8, 24, 3), dtype=np.uint8),
        },
    )
    assert store.winner(4)["frame_number"] == 8


def test_ranking_prefers_larger_readable_over_tiny_noisy() -> None:
    large_total, _ = rank_score(
        width=182,
        height=53,
        sharpness=45,
        contrast=28,
        brightness=140,
        sat_ratio=0.02,
        detector_confidence=0.6,
    )
    tiny_total, _ = rank_score(
        width=40,
        height=14,
        sharpness=300,
        contrast=35,
        brightness=140,
        sat_ratio=0.02,
        detector_confidence=0.9,
    )
    assert large_total > tiny_total


def test_evaluate_accepts_useful_cctv_plate() -> None:
    plate = _bar_plate(182, 53)
    metrics = evaluate_plate_crop(plate, 182, 53, 0.7)
    assert metrics.accepted is True
    assert metrics.plate_width == 182
    assert metrics.plate_height == 53
    assert metrics.sharpness_score >= DEFAULT_QUALITY.min_sharpness
    assert metrics.total_score > 0.3


def test_evaluate_accepts_moderate_sharpness_on_high_res_frame() -> None:
    import cv2

    plate = _bar_plate(182, 53)
    moderate = None
    for k in (9, 11, 13, 15, 17, 19, 21):
        candidate = cv2.GaussianBlur(plate, (k, k), 0)
        sharp = sharpness_value(candidate)
        if DEFAULT_QUALITY.min_sharpness <= sharp < 70:
            moderate = candidate
            break
    assert moderate is not None
    metrics = evaluate_plate_crop(moderate, 182, 53, 0.65)
    assert metrics.accepted is True
    smeared = cv2.GaussianBlur(plate, (41, 41), 0)
    rejected = evaluate_plate_crop(smeared, 182, 53, 0.65)
    assert rejected.accepted is False
    assert rejected.reject_reason == "sharpness"


def test_evaluate_rejects_empty_overexposed_and_tiny() -> None:
    empty = np.full((30, 90, 3), 80, dtype=np.uint8)
    assert evaluate_plate_crop(empty, 90, 30, 0.9).accepted is False
    white = np.full((40, 140, 3), 255, dtype=np.uint8)
    assert evaluate_plate_crop(white, 140, 40, 0.9).accepted is False
    tiny = _bar_plate(20, 8)
    assert evaluate_plate_crop(tiny, 20, 8, 0.9).accepted is False
    tall = _bar_plate(40, 40)
    assert evaluate_plate_crop(tall, 40, 40, 0.9).accepted is False


def test_candidate_store_keeps_top_n_and_selects_best() -> None:
    store = PlateCandidateStore(top_n=3)
    store.record_detection(7, width=40, height=14, accepted=False)
    assert store.state(7).detections == 1
    assert store.state(7).valid == 0
    for i, score in enumerate((0.2, 0.9, 0.4, 0.7, 0.1)):
        store.record_detection(
            7,
            width=100 + i,
            height=30,
            accepted=True,
            candidate={
                "frame_number": 500 + i,
                "total_score": score,
                "plate_area": 100 + i,
                "image_plate": np.zeros((8, 24, 3), dtype=np.uint8),
            },
        )
    assert store.state(7).valid == 5
    assert len(store.state(7).candidates) == 3
    assert store.winner(7)["frame_number"] == 501
    assert [c["frame_number"] for c in store.state(7).candidates] == [501, 503, 502]


def test_candidate_store_single_detection_and_empty_track() -> None:
    store = PlateCandidateStore(top_n=20)
    assert store.winner(1) is None
    store.record_detection(
        2,
        width=90,
        height=28,
        accepted=True,
        candidate={"frame_number": 10, "total_score": 0.4, "image_plate": np.zeros((8, 8, 3), dtype=np.uint8)},
    )
    assert store.winner(2)["frame_number"] == 10
    store.record_detection(3, width=10, height=4, accepted=False)
    assert store.winner(3) is None


def test_candidate_store_merge_and_missing_frames() -> None:
    store = PlateCandidateStore(top_n=5)
    store.record_detection(
        10,
        width=80,
        height=24,
        accepted=True,
        candidate={"frame_number": 1, "total_score": 0.3, "image_plate": np.zeros((4, 8, 3), dtype=np.uint8)},
    )
    store.record_detection(
        11,
        width=180,
        height=50,
        accepted=True,
        candidate={"frame_number": 20, "total_score": 0.8, "image_plate": np.zeros((4, 8, 3), dtype=np.uint8)},
    )
    store.merge(10, 11)
    assert 11 not in store._tracks
    assert store.winner(10)["frame_number"] == 20
    assert store.state(10).detections == 2


def test_resized_box_maps_back_and_crop_uses_original_pixels() -> None:
    original = np.zeros((1520, 2688, 3), dtype=np.uint8)
    original[400:453, 1000:1182] = (20, 180, 220)
    original[412:440, 1020:1030] = (10, 10, 10)
    resized_w, resized_h = 640, 362
    scale_x = resized_w / 2688.0
    scale_y = resized_h / 1520.0
    local = BoundingBox(1000 * scale_x, 400 * scale_y, 1182 * scale_x, 453 * scale_y)
    mapped = map_resized_box_to_original(local, resized_w, resized_h, 2688, 1520)
    assert abs(mapped.width - 182) < 2
    assert abs(mapped.height - 53) < 2
    crop = crop_from_original(original, mapped, pad=0.0)
    assert crop.shape[1] >= 170
    assert crop.shape[0] >= 48
    assert not np.array_equal(crop, np.zeros_like(crop))
    assert crop.mean() > 10
