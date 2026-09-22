"""Native-resolution plate crop quality.

Each metric exists because a specific kind of crop is unreadable, not because a
detector score looked low. Hard gates stay loose so a ~182x53 CCTV plate is kept.
Old high-resolution Laplacian floors (70 on 2688px video) are a score penalty, not a delete.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

import numpy as np

# Reference size of a useful CCTV plate (the known readable bus plate is ~182x53).
REFERENCE_PLATE_WIDTH = 182.0
REFERENCE_PLATE_HEIGHT = 53.0
REFERENCE_PLATE_AREA = REFERENCE_PLATE_WIDTH * REFERENCE_PLATE_HEIGHT
# Axis LPC: two pixels per stroke is about 75 px across a European plate.
# 100–150 px is the width most LPR software expects. Below 75 px the crop is
# kept only as a flagged low-detail capture, not as good evidence.
READABLE_PLATE_WIDTH = 75.0
TARGET_PLATE_WIDTH = 100.0
TARGET_PLATE_WIDTH_HIGH = 150.0
# Laplacian values above this are treated as fully sharp for ranking.
SHARPNESS_NORM = 140.0
CONTRAST_NORM = 45.0
SATURATION_VALUE = 250
# Typical Indian car plate aspect; score falls off toward the configured extremes.
IDEAL_ASPECT = REFERENCE_PLATE_WIDTH / REFERENCE_PLATE_HEIGHT


@dataclass(frozen=True)
class PlateQualityConfig:
    """Defaults chosen so a ~182x53 H.264 plate is not hard-rejected."""

    min_width_px: float = 28.0
    min_height_px: float = 10.0
    min_detector_confidence: float = 0.15
    max_saturation_ratio: float = 0.45
    min_sharpness: float = 12.0
    min_contrast: float = 8.0
    min_aspect: float = 1.3
    max_aspect: float = 7.0
    weight_size: float = 0.22
    weight_sharpness: float = 0.18
    weight_contrast: float = 0.16
    weight_exposure: float = 0.14
    weight_saturation: float = 0.12
    weight_geometry: float = 0.10
    weight_detector_confidence: float = 0.08


DEFAULT_QUALITY = PlateQualityConfig()


@dataclass
class PlateQualityMetrics:
    plate_width: float
    plate_height: float
    plate_area: float
    plate_detection_confidence: float
    sharpness_score: float
    contrast_score: float
    brightness_score: float
    saturation_ratio: float
    exposure_score: float
    geometry_score: float
    size_score: float
    saturation_score: float
    detector_score: float
    total_score: float
    accepted: bool
    reject_reason: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        data = asdict(self)
        extra = data.pop("extra", {}) or {}
        data.update(extra)
        return data


def _gray(image: np.ndarray) -> np.ndarray:
    import cv2

    if image.size == 0:
        return image
    if image.ndim == 3:
        return cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    return image


def plate_size(width: float, height: float) -> tuple[float, float, float]:
    w = max(0.0, float(width))
    h = max(0.0, float(height))
    return w, h, w * h


def sharpness_value(image: np.ndarray) -> float:
    """Laplacian variance after a light blur so sensor noise does not look 'sharp'."""
    import cv2

    if image.size == 0:
        return 0.0
    gray = _gray(image)
    work = cv2.GaussianBlur(gray, (3, 3), 0)
    return float(cv2.Laplacian(work, cv2.CV_64F).var())


def contrast_value(image: np.ndarray) -> float:
    """Gray-level spread. Near-zero means characters melt into the plate."""
    if image.size == 0:
        return 0.0
    return float(_gray(image).std())


def brightness_value(image: np.ndarray) -> float:
    if image.size == 0:
        return 0.0
    return float(_gray(image).mean())


def saturation_ratio(image: np.ndarray, threshold: int = SATURATION_VALUE) -> float:
    """Share of pixels at or above the clip ceiling. Washed-out plates score high."""
    if image.size == 0:
        return 1.0
    gray = _gray(image)
    return float((gray >= int(threshold)).mean())


def exposure_score(brightness: float) -> float:
    """1 at mid-gray, 0 at solid black or solid white."""
    return max(0.0, 1.0 - abs(float(brightness) - 128.0) / 128.0)


def geometry_score(width: float, height: float, config: PlateQualityConfig = DEFAULT_QUALITY) -> float:
    """1 near a typical plate aspect, 0 at or beyond the configured extremes."""
    aspect = float(width) / max(float(height), 1.0)
    if aspect < config.min_aspect or aspect > config.max_aspect:
        return 0.0
    span = max(config.max_aspect - config.min_aspect, 1e-6)
    return max(0.0, 1.0 - abs(aspect - IDEAL_ASPECT) / span)


def size_score(width: float, height: float) -> float:
    """Larger plates are easier to read. Saturates around the known useful CCTV size.

    A plate that already covers the 100 px Axis target is credited fully once
    its area matches that width at a normal plate aspect.
    """
    area = max(0.0, float(width) * float(height))
    reference = min(1.0, area / REFERENCE_PLATE_AREA)
    if float(width) < TARGET_PLATE_WIDTH:
        return reference
    target_height = TARGET_PLATE_WIDTH / IDEAL_ASPECT
    target = min(1.0, area / max(TARGET_PLATE_WIDTH * target_height, 1.0))
    return max(reference, target)


def plate_width_band(width: float) -> str:
    """low under 75 px, narrow until 100 px, target through 150 px, then wide."""
    w = float(width)
    if w < READABLE_PLATE_WIDTH:
        return "low"
    if w < TARGET_PLATE_WIDTH:
        return "narrow"
    if w <= TARGET_PLATE_WIDTH_HIGH:
        return "target"
    return "wide"


def is_good_plate_evidence(item: dict[str, Any]) -> bool:
    """A crop under 75 px wide cannot resolve character strokes."""
    flagged = item.get("good_evidence")
    if flagged is not None:
        return bool(flagged)
    width = item.get("plate_width")
    if width is None:
        return True
    return float(width) >= READABLE_PLATE_WIDTH


def config_for_dark(config: PlateQualityConfig) -> PlateQualityConfig:
    """Night frames: headlight washout should lose to a dimmer, sharper plate."""
    from dataclasses import replace

    return replace(
        config,
        weight_exposure=max(float(config.weight_exposure), 0.30),
        weight_saturation=max(float(config.weight_saturation), 0.30),
    )


def _normalize_weights(config: PlateQualityConfig) -> PlateQualityConfig:
    total = (
        config.weight_size
        + config.weight_sharpness
        + config.weight_contrast
        + config.weight_exposure
        + config.weight_saturation
        + config.weight_geometry
        + config.weight_detector_confidence
    )
    if total <= 0:
        return config
    scale = 1.0 / total
    return PlateQualityConfig(
        min_width_px=config.min_width_px,
        min_height_px=config.min_height_px,
        min_detector_confidence=config.min_detector_confidence,
        max_saturation_ratio=config.max_saturation_ratio,
        min_sharpness=config.min_sharpness,
        min_contrast=config.min_contrast,
        min_aspect=config.min_aspect,
        max_aspect=config.max_aspect,
        weight_size=config.weight_size * scale,
        weight_sharpness=config.weight_sharpness * scale,
        weight_contrast=config.weight_contrast * scale,
        weight_exposure=config.weight_exposure * scale,
        weight_saturation=config.weight_saturation * scale,
        weight_geometry=config.weight_geometry * scale,
        weight_detector_confidence=config.weight_detector_confidence * scale,
    )


def rank_score(
    *,
    width: float,
    height: float,
    sharpness: float,
    contrast: float,
    brightness: float,
    sat_ratio: float,
    detector_confidence: float,
    config: PlateQualityConfig = DEFAULT_QUALITY,
) -> tuple[float, dict[str, float]]:
    cfg = _normalize_weights(config)
    size = size_score(width, height)
    sharp_n = min(1.0, max(0.0, float(sharpness) / SHARPNESS_NORM))
    contrast_n = min(1.0, max(0.0, float(contrast) / CONTRAST_NORM))
    exposure = exposure_score(brightness)
    sat = max(0.0, 1.0 - min(1.0, float(sat_ratio)))
    geom = geometry_score(width, height, cfg)
    det = min(1.0, max(0.0, float(detector_confidence)))
    total = (
        cfg.weight_size * size
        + cfg.weight_sharpness * sharp_n
        + cfg.weight_contrast * contrast_n
        + cfg.weight_exposure * exposure
        + cfg.weight_saturation * sat
        + cfg.weight_geometry * geom
        + cfg.weight_detector_confidence * det
    )
    parts = {
        "size_score": size,
        "sharpness_norm": sharp_n,
        "contrast_norm": contrast_n,
        "exposure_score": exposure,
        "saturation_score": sat,
        "geometry_score": geom,
        "detector_score": det,
    }
    return float(total), parts


def gate_plate(
    *,
    image: np.ndarray,
    width: float,
    height: float,
    detector_confidence: float,
    sharpness: float,
    contrast: float,
    sat_ratio: float,
    config: PlateQualityConfig = DEFAULT_QUALITY,
) -> str | None:
    """Return a reject reason, or None when the crop may enter ranking.

    Extreme blur, clipping, and wrong aspect still fail. A moderate Laplacian
    on a high-resolution frame does not.
    """
    from app.preprocessing.plates import is_burned_in_caption

    if image.size == 0:
        return "empty"
    if is_burned_in_caption(image):
        return "caption"
    if float(detector_confidence) < config.min_detector_confidence:
        return "detector_confidence"
    if float(width) < config.min_width_px or float(height) < config.min_height_px:
        return "size"
    aspect = float(width) / max(float(height), 1.0)
    if aspect < config.min_aspect or aspect > config.max_aspect:
        return "geometry"
    if float(sharpness) < config.min_sharpness:
        return "sharpness"
    if float(contrast) < config.min_contrast:
        return "contrast"
    if float(sat_ratio) > config.max_saturation_ratio:
        return "saturation"
    mean = brightness_value(image)
    if mean > 230 and contrast < config.min_contrast * 2 and aspect < 1.4:
        return "headlight"
    if mean < 10 and contrast < config.min_contrast:
        return "underexposed"
    return None


def evaluate_plate_crop(
    image: np.ndarray,
    width: float,
    height: float,
    detector_confidence: float,
    config: PlateQualityConfig | None = None,
    dark: bool = False,
) -> PlateQualityMetrics:
    cfg = config or DEFAULT_QUALITY
    w, h, area = plate_size(width, height)
    if image.size == 0:
        return PlateQualityMetrics(
            plate_width=w,
            plate_height=h,
            plate_area=area,
            plate_detection_confidence=float(detector_confidence),
            sharpness_score=0.0,
            contrast_score=0.0,
            brightness_score=0.0,
            saturation_ratio=1.0,
            exposure_score=0.0,
            geometry_score=0.0,
            size_score=0.0,
            saturation_score=0.0,
            detector_score=0.0,
            total_score=0.0,
            accepted=False,
            reject_reason="empty",
        )
    sharp = sharpness_value(image)
    contrast = contrast_value(image)
    brightness = brightness_value(image)
    sat = saturation_ratio(image)
    rank_cfg = config_for_dark(cfg) if dark else cfg
    total, parts = rank_score(
        width=w,
        height=h,
        sharpness=sharp,
        contrast=contrast,
        brightness=brightness,
        sat_ratio=sat,
        detector_confidence=detector_confidence,
        config=rank_cfg,
    )
    reason = gate_plate(
        image=image,
        width=w,
        height=h,
        detector_confidence=detector_confidence,
        sharpness=sharp,
        contrast=contrast,
        sat_ratio=sat,
        config=cfg,
    )
    if dark and reason == "sharpness" and sharp >= max(6.0, cfg.min_sharpness * 0.5):
        reason = None
    return PlateQualityMetrics(
        plate_width=w,
        plate_height=h,
        plate_area=area,
        plate_detection_confidence=float(detector_confidence),
        sharpness_score=sharp,
        contrast_score=contrast,
        brightness_score=brightness,
        saturation_ratio=sat,
        exposure_score=parts["exposure_score"],
        geometry_score=parts["geometry_score"],
        size_score=parts["size_score"],
        saturation_score=parts["saturation_score"],
        detector_score=parts["detector_score"],
        total_score=0.0 if reason else total,
        accepted=reason is None,
        reject_reason=reason,
        extra={
            "sharpness_norm": parts["sharpness_norm"],
            "contrast_norm": parts["contrast_norm"],
            "good_evidence": w >= READABLE_PLATE_WIDTH,
            "width_band": plate_width_band(w),
        },
    )


def config_from_settings(settings: Any) -> PlateQualityConfig:
    return PlateQualityConfig(
        min_width_px=float(settings.plate_quality_min_width_px),
        min_height_px=float(settings.plate_quality_min_height_px),
        min_detector_confidence=float(settings.plate_quality_min_detector_confidence),
        max_saturation_ratio=float(settings.plate_quality_max_saturation_ratio),
        min_sharpness=float(settings.plate_quality_min_sharpness),
        min_contrast=float(settings.plate_quality_min_contrast),
        min_aspect=float(settings.plate_quality_min_aspect),
        max_aspect=float(settings.plate_quality_max_aspect),
        weight_size=float(settings.plate_quality_weight_size),
        weight_sharpness=float(settings.plate_quality_weight_sharpness),
        weight_contrast=float(settings.plate_quality_weight_contrast),
        weight_exposure=float(settings.plate_quality_weight_exposure),
        weight_saturation=float(settings.plate_quality_weight_saturation),
        weight_geometry=float(settings.plate_quality_weight_geometry),
        weight_detector_confidence=float(settings.plate_quality_weight_detector_confidence),
    )
