from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Optional

import cv2

from packages.overlay_clock import (
    origin_from_sample,
    overlay_clock_payload,
    parse_overlay_datetime,
)

logger = logging.getLogger("worker")

_ALLOWLIST = "0123456789-:.APMapm /"


def _candidate_crops(image: Any) -> list[Any]:
    height, width = image.shape[:2]
    crops: list[Any] = []
    specs = (
        (0.12, 0.45, True),
        (0.18, 0.58, True),
        (0.10, 1.0, False),
    )
    for height_frac, width_frac, from_right in specs:
        y2 = max(int(height * height_frac), 28)
        crop_w = max(int(width * width_frac), 80)
        x1 = max(width - crop_w, 0) if from_right else 0
        crop = image[0:y2, x1:width]
        if crop.size:
            crops.append(crop)
    return crops


def _preprocess_variants(crop: Any) -> list[Any]:
    variants = [crop]
    if crop.ndim == 3:
        gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
    else:
        gray = crop
    scaled = cv2.resize(gray, None, fx=3.0, fy=3.0, interpolation=cv2.INTER_CUBIC)
    clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8)).apply(scaled)
    _otsu, binary = cv2.threshold(clahe, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    inverted = cv2.bitwise_not(binary)
    for gray_img in (scaled, clahe, binary, inverted):
        variants.append(cv2.cvtColor(gray_img, cv2.COLOR_GRAY2BGR))
    hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV) if crop.ndim == 3 else None
    if hsv is not None:
        white = cv2.inRange(hsv, (0, 0, 170), (180, 80, 255))
        white = cv2.resize(white, None, fx=3.0, fy=3.0, interpolation=cv2.INTER_NEAREST)
        variants.append(cv2.cvtColor(cv2.bitwise_not(white), cv2.COLOR_GRAY2BGR))
    return variants


def _ocr_text(engine: Any, image: Any) -> str:
    kwargs = {
        "allowlist": _ALLOWLIST,
        "detail": 1,
        "paragraph": False,
        "min_size": 3,
        "mag_ratio": 2.0,
        "text_threshold": 0.4,
        "low_text": 0.3,
    }
    try:
        rows = engine._reader.readtext(image, **kwargs)
    except TypeError:
        rows = engine._reader.readtext(image, allowlist=_ALLOWLIST, detail=1, paragraph=False)
    parts = [str(text) for _, text, _conf in rows if text]
    return " ".join(parts)


def _read_from_image(engine: Any, image: Any, video_seconds: float) -> Optional[dict]:
    last_raw = ""
    for crop in _candidate_crops(image):
        for variant in _preprocess_variants(crop):
            raw = _ocr_text(engine, variant)
            if raw:
                last_raw = raw
            parsed = parse_overlay_datetime(raw)
            if parsed is None:
                continue
            origin = origin_from_sample(parsed, video_seconds)
            logger.info("overlay clock parsed: %s (video t=%.2fs)", raw, video_seconds)
            return overlay_clock_payload(origin, raw, video_seconds)
    if last_raw:
        logger.debug("overlay clock OCR miss: %s", last_raw)
    return None


def extract_overlay_clock_from_video(video_path: Path, max_frames: int = 2) -> Optional[dict]:
    from app.ocr.engine import get_ocr_engine

    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        logger.warning("overlay clock: could not open %s", video_path)
        return None
    fps = float(cap.get(cv2.CAP_PROP_FPS) or 25.0) or 25.0
    # CPU keeps the GPU free for YOLO while this runs in the background.
    device = "cpu"
    frame_indexes = (0, 12, 25, 50, 75, 125)[: max(1, int(max_frames))]
    try:
        logger.info("overlay clock OCR device=%s frames=%s", device, frame_indexes)
        engine = get_ocr_engine("easyocr", "en", device)
        for frame_index in frame_indexes:
            cap.set(cv2.CAP_PROP_POS_FRAMES, frame_index)
            ok, frame = cap.read()
            if not ok or frame is None:
                continue
            payload = _read_from_image(engine, frame, frame_index / fps)
            if payload:
                return payload
    except Exception:
        logger.exception("overlay clock: OCR failed for %s", video_path)
        return None
    finally:
        cap.release()
    logger.warning("overlay clock: no timestamp parsed from %s", video_path)
    return None
