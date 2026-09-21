from pathlib import Path
from typing import Any

import numpy as np

NIGHT_LUMINANCE_MAX = 95.0
ROI_ENHANCE_LUMINANCE_MAX = 110.0
HIGH_EVIDENCE_SCORE = 0.62
JPEG_EVIDENCE_QUALITY = 98
JPEG_PLATE_QUALITY = 100
PLATE_CROP_PAD_DAY = 0.22
PLATE_CROP_PAD_NIGHT = 0.28
VEHICLE_CROP_PAD = 0.16


def save_jpeg(path: Path | str, image: np.ndarray, quality: int = JPEG_EVIDENCE_QUALITY) -> None:
    import cv2

    dest = Path(path)
    dest.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(dest), image, [int(cv2.IMWRITE_JPEG_QUALITY), int(quality)])


def preprocess_plate(image: np.ndarray, variant: str = "default") -> np.ndarray:
    import cv2

    crop = image
    if crop.size == 0:
        return crop
    h, w = crop.shape[:2]
    if w < 16 or h < 8:
        return crop
    scale = max(1.0, 200 / max(w, 1))
    resized = cv2.resize(crop, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_CUBIC)
    if variant == "gray":
        gray = cv2.cvtColor(resized, cv2.COLOR_BGR2GRAY)
        return cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)
    if variant == "contrast":
        lab = cv2.cvtColor(resized, cv2.COLOR_BGR2LAB)
        l, a, b = cv2.split(lab)
        l = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8)).apply(l)
        return cv2.cvtColor(cv2.merge((l, a, b)), cv2.COLOR_LAB2BGR)
    return resized


def frame_luminance(image: np.ndarray) -> float:
    import cv2

    if image.size == 0:
        return 0.0
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if image.ndim == 3 else image
    return float(gray.mean())


def enhance_low_light_frame(image: np.ndarray) -> np.ndarray:
    """CLAHE on the full frame so night/IR plates are visible to YOLO. Does not resize."""
    import cv2

    if image.size == 0:
        return image
    lab = cv2.cvtColor(image, cv2.COLOR_BGR2LAB)
    l_ch, a_ch, b_ch = cv2.split(lab)
    l_ch = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8)).apply(l_ch)
    return cv2.cvtColor(cv2.merge((l_ch, a_ch, b_ch)), cv2.COLOR_LAB2BGR)


def enhance_night_plate_crop(image: np.ndarray) -> np.ndarray:
    """Mild denoise + contrast on the native crop. Never upscale (that makes IR plates look hazy)."""
    import cv2

    if image.size == 0:
        return image
    denoised = cv2.bilateralFilter(image, 5, 40, 40)
    lab = cv2.cvtColor(denoised, cv2.COLOR_BGR2LAB)
    l_ch, a_ch, b_ch = cv2.split(lab)
    l_ch = cv2.createCLAHE(clipLimit=1.4, tileGridSize=(4, 4)).apply(l_ch)
    enhanced = cv2.cvtColor(cv2.merge((l_ch, a_ch, b_ch)), cv2.COLOR_LAB2BGR)
    blur = cv2.GaussianBlur(enhanced, (0, 0), 0.8)
    return cv2.addWeighted(enhanced, 1.25, blur, -0.25, 0)


def _gray(image: np.ndarray) -> np.ndarray:
    import cv2

    if image.ndim == 3:
        return cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    return image


def plate_structure_metrics(image: np.ndarray) -> tuple[float, float, float, float, int]:
    """sharpness, contrast, mean, edge_density, letter-like component count."""
    import cv2

    if image.size == 0:
        return 0.0, 0.0, 0.0, 0.0, 0
    gray = _gray(image)
    work = cv2.GaussianBlur(gray, (3, 3), 0)
    sharp = float(cv2.Laplacian(work, cv2.CV_64F).var())
    contrast = float(gray.std())
    mean = float(gray.mean())
    edges = cv2.Canny(work, 40, 120)
    edge_density = float((edges > 0).mean())
    closed = cv2.morphologyEx(edges, cv2.MORPH_CLOSE, np.ones((2, 2), np.uint8))
    _n, _labels, stats, _ = cv2.connectedComponentsWithStats(closed)
    h, w = gray.shape[:2]
    max_area = max(8.0, w * h * 0.4)
    components = 0
    for i in range(1, stats.shape[0]):
        area = float(stats[i, cv2.CC_STAT_AREA])
        if 6.0 <= area <= max_area:
            components += 1
    return sharp, contrast, mean, edge_density, components


def evidence_score(
    plate_confidence: float,
    box_area: float,
    sharp: float,
    contrast: float,
    edge_density: float,
    components: int,
) -> float:
    return (
        0.26 * float(plate_confidence)
        + 0.20 * min(1.0, box_area / 12000.0)
        + 0.20 * min(1.0, sharp / 140.0)
        + 0.14 * min(1.0, contrast / 40.0)
        + 0.12 * min(1.0, edge_density / 0.12)
        + 0.08 * min(1.0, components / 4.0)
    )


def is_burned_in_caption(image: np.ndarray) -> bool:
    """Yellow glyphs on a dark bar: the camera name burned into the frame, not a plate.

    A yellow commercial plate is the opposite pattern (yellow fill, dark letters), so a
    high yellow share or a bright median keeps it.
    """
    import cv2

    if image.size == 0 or image.ndim != 3 or image.shape[0] < 6 or image.shape[1] < 12:
        return False
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    hue, sat, val = cv2.split(hsv)
    yellow = (hue >= 15) & (hue <= 42) & (sat >= 90) & (val >= 150)
    yellow_ratio = float(yellow.mean())
    if yellow_ratio < 0.02 or yellow_ratio > 0.40:
        return False
    if float(np.median(val)) > 80:
        return False
    row_yellow = yellow.mean(axis=1)
    return float(row_yellow.max()) >= 0.08


def is_hard_false_positive(
    image: np.ndarray,
    box_width: float,
    box_height: float,
    plate_confidence: float,
) -> bool:
    """Obvious non-plates: empty, extreme aspect, headlights, camera captions, no letter-like structure."""
    if image.size == 0:
        return True
    if is_burned_in_caption(image):
        return True
    if plate_confidence < 0.15:
        return True
    aspect = box_width / max(box_height, 1.0)
    if aspect < 1.05 or aspect > 7.0:
        return True
    if box_width < 12 or box_height < 6:
        return True
    sharp, contrast, mean, edge_density, components = plate_structure_metrics(image)
    if mean > 220 and contrast < 28 and aspect < 1.4:
        return True
    if mean < 12 and contrast < 8:
        return True
    if components == 0 and contrast < 14 and sharp < 12:
        return True
    if edge_density > 0.20 and components > 6:
        return True
    return False


def readable_plate_limits(frame_width: float, dark: bool = False) -> tuple[float, float, float]:
    """Minimum width, height, and sharpness that can exist in this picture.

    704x576 and 848x478 clips, including WhatsApp compressions, do not contain an
    80px-wide plate until a vehicle is on top of the camera. Scale the bar with the
    frame and keep the sharpness floor low enough that compression does not wipe
    every crop.
    """
    width = float(frame_width) if frame_width and frame_width > 0 else 1280.0
    if dark:
        min_w = max(16.0, min(40.0, width * 0.025))
        return min_w, max(8.0, min_w / 5.0), 8.0
    min_w = max(26.0, min(56.0, width * 0.040))
    min_h = max(10.0, min(16.0, min_w / 4.5))
    if width >= 2000:
        # High-resolution frames make a smeared plate look large. Require real edges.
        min_sharp = 70.0
    elif width >= 1200:
        min_sharp = 16.0
    else:
        min_sharp = 10.0
    return min_w, min_h, min_sharp


def has_plate_evidence(
    image: np.ndarray,
    box_width: float,
    box_height: float,
    plate_confidence: float,
    dark: bool = False,
    frame_width: float = 0.0,
) -> tuple[bool, float, float]:
    """Keep a crop only when it has enough plate information. Does not force a save to raise counts."""
    if is_hard_false_positive(image, box_width, box_height, plate_confidence):
        return False, 0.0, 0.0
    sharp, contrast, _mean, edge_density, components = plate_structure_metrics(image)
    min_w, min_h, min_sharp = readable_plate_limits(frame_width, dark)
    if box_width < min_w or box_height < min_h or sharp < min_sharp:
        return False, 0.0, sharp
    min_edge = 0.022 if dark else 0.03
    min_contrast = 10.0 if dark else 14.0
    structured = components >= 2 or (
        components >= 1 and (box_width / max(box_height, 1.0)) >= 1.8 and contrast >= min_contrast
    )
    if not structured:
        return False, 0.0, sharp
    if edge_density < min_edge and contrast < min_contrast and sharp < min_sharp:
        return False, 0.0, sharp
    score = evidence_score(
        plate_confidence,
        box_width * box_height,
        sharp,
        contrast,
        edge_density,
        components,
    )
    min_score = 0.26 if dark else 0.30
    if score < min_score:
        return False, score, sharp
    return True, score, sharp


def is_plausible_plate_crop(
    image: np.ndarray,
    box_width: float,
    box_height: float,
    plate_confidence: float,
    night: bool = False,
) -> tuple[bool, float, float]:
    ok, score, sharp = has_plate_evidence(image, box_width, box_height, plate_confidence, dark=night)
    if not ok:
        return False, sharp, 0.0
    _s, contrast, _m, _e, _c = plate_structure_metrics(image)
    return True, sharp, contrast


SHARPNESS_CAP = 400.0
AREA_CAP = 20000.0
CONTRAST_CAP = 40.0
MAX_RUNNERS_UP = 2


def plate_frame_quality(
    sharp: float,
    plate_area: float,
    plate_confidence: float,
    contrast: float,
) -> float:
    """Rank a readable plate crop. A sharp plate beats a larger motion-smeared one."""
    return (
        0.82 * min(1.0, float(sharp) / SHARPNESS_CAP)
        + 0.08 * min(1.0, float(plate_area) / AREA_CAP)
        + 0.07 * min(1.0, float(plate_confidence))
        + 0.03 * min(1.0, float(contrast) / CONTRAST_CAP)
    )


def _quality_of(item: dict[str, Any]) -> float:
    return float(item.get("quality") or item.get("score") or 0.0)


def _winner_fields(candidate: dict[str, Any]) -> dict[str, Any]:
    quality = float(candidate["quality"])
    full = candidate.get("image_full")
    if full is not None and hasattr(full, "copy") and not candidate.get("images_owned"):
        full = full.copy()
    return {
        "quality": quality,
        "score": quality,
        "sharp": candidate.get("sharp"),
        "plate_area": candidate.get("plate_area"),
        "contrast": candidate.get("contrast"),
        "best_frame": candidate.get("best_frame"),
        "plate_confidence": candidate.get("plate_confidence"),
        "vehicle_confidence": candidate.get("vehicle_confidence"),
        "vehicle_type": candidate.get("vehicle_type"),
        "plate_box": candidate.get("plate_box"),
        "vehicle_box": candidate.get("vehicle_box"),
        "image_full": full,
        "image_vehicle": candidate.get("image_vehicle"),
        "image_plate": candidate.get("image_plate"),
    }


def _quality_snapshot(item: dict[str, Any], *, owned: bool) -> dict[str, Any]:
    return _winner_fields({**item, "quality": _quality_of(item), "images_owned": owned})


def _trim_alternates(alternates: list[dict[str, Any]], winner_quality: float) -> list[dict[str, Any]]:
    ranked = [alt for alt in alternates if _quality_of(alt) < winner_quality]
    ranked.sort(key=_quality_of, reverse=True)
    return ranked[:MAX_RUNNERS_UP]


def consider_plate_candidate(
    previous: dict[str, Any] | None,
    candidate: dict[str, Any],
) -> dict[str, Any]:
    """Keep last_seen and observations on every crop. Replace images only on a higher quality score."""
    observation = candidate["observation"]
    timestamp = candidate["timestamp"]
    source_ids = set(candidate.get("source_ids") or [])
    active_tid = candidate.get("active_tid")

    if previous is None:
        capture = _winner_fields(candidate)
        capture.update(
            {
                "first_seen": timestamp,
                "last_seen": timestamp,
                "observations": [observation],
                "published": False,
                "source_ids": source_ids,
                "active_tid": active_tid,
                "alternates": [],
            }
        )
        return capture

    previous["last_seen"] = timestamp
    previous.setdefault("observations", []).append(observation)
    ids = set(previous.get("source_ids") or [])
    ids.update(source_ids)
    previous["source_ids"] = ids
    if active_tid is not None:
        previous["active_tid"] = active_tid

    quality = float(candidate["quality"])
    prev_quality = _quality_of(previous)
    prev_sharp = float(previous.get("sharp") or 0.0)
    cand_sharp = float(candidate.get("sharp") or 0.0)
    if cand_sharp >= max(prev_sharp * 1.25, prev_sharp + 40.0):
        quality = max(quality, prev_quality + 0.01)
    alts = list(previous.get("alternates") or [])
    if quality > prev_quality:
        alts.append(_quality_snapshot(previous, owned=True))
        previous.update(_winner_fields(candidate))
        previous["alternates"] = _trim_alternates(alts, quality)
    else:
        alts.append(_quality_snapshot(candidate, owned=False))
        previous["alternates"] = _trim_alternates(alts, prev_quality)
    return previous


def crop_box(image: np.ndarray, x1: int, y1: int, x2: int, y2: int, pad: float = 0.08) -> np.ndarray:
    crop, _ox, _oy = crop_box_asymmetric(image, x1, y1, x2, y2, pad, pad, pad, pad)
    return crop


def crop_box_asymmetric(
    image: np.ndarray,
    x1: int,
    y1: int,
    x2: int,
    y2: int,
    pad_left: float,
    pad_top: float,
    pad_right: float,
    pad_bottom: float,
) -> tuple[np.ndarray, int, int]:
    h, w = image.shape[:2]
    bw, bh = max(1, x2 - x1), max(1, y2 - y1)
    xa = max(0, int(x1 - bw * pad_left))
    ya = max(0, int(y1 - bh * pad_top))
    xb = min(w, int(x2 + bw * pad_right))
    yb = min(h, int(y2 + bh * pad_bottom))
    return image[ya:yb, xa:xb].copy(), xa, ya


def sharpness(image: np.ndarray) -> float:
    import cv2

    if image.size == 0:
        return 0.0
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if image.ndim == 3 else image
    return float(cv2.Laplacian(gray, cv2.CV_64F).var())
