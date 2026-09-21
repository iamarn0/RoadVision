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


def is_hard_false_positive(
    image: np.ndarray,
    box_width: float,
    box_height: float,
    plate_confidence: float,
) -> bool:
    """Obvious non-plates: empty, extreme aspect, headlights, no letter-like structure."""
    if image.size == 0:
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


def has_plate_evidence(
    image: np.ndarray,
    box_width: float,
    box_height: float,
    plate_confidence: float,
    dark: bool = False,
) -> tuple[bool, float, float]:
    """Keep a crop only when it has enough plate information. Does not force a save to raise counts."""
    if is_hard_false_positive(image, box_width, box_height, plate_confidence):
        return False, 0.0, 0.0
    sharp, contrast, _mean, edge_density, components = plate_structure_metrics(image)
    min_edge = 0.022 if dark else 0.03
    min_contrast = 10.0 if dark else 14.0
    min_sharp = 8.0 if dark else 12.0
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


def is_better_evidence(
    previous: dict[str, Any] | None,
    score: float,
    plate_area: float,
    sharp: float,
) -> bool:
    """Replace only when the new crop is larger and still readable, or clearly sharper.

    A larger motion-blurred plate must not beat a slightly smaller sharp one.
    """
    if previous is None:
        return True
    prev_score = float(previous.get("score") or 0.0)
    prev_area = float(previous.get("plate_area") or 0.0)
    prev_sharp = float(previous.get("sharp") or 0.0)
    readable = sharp >= prev_sharp * 0.90
    if plate_area > prev_area * 1.05 and readable:
        return True
    if sharp > prev_sharp * 1.25 and plate_area >= prev_area * 0.85:
        return True
    if score > prev_score * 1.02 and readable:
        return True
    return False


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
