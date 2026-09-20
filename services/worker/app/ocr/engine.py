from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Optional

import numpy as np


@dataclass
class OCRResult:
    raw_text: str
    confidence: float
    bounding_boxes: list[Any] = field(default_factory=list)
    processing_time: float = 0.0


class OCREngine:
    def read(self, image: np.ndarray) -> OCRResult:
        raise NotImplementedError


class EasyOCREngine(OCREngine):
    def __init__(self, languages: list[str], device: str) -> None:
        try:
            import easyocr
        except Exception as exc:
            raise RuntimeError("EasyOCR is not installed") from exc
        gpu = device.startswith("cuda")
        self._reader = easyocr.Reader(languages, gpu=gpu)

    def read(self, image: np.ndarray) -> OCRResult:
        start = time.perf_counter()
        rows = self._reader.readtext(image)
        elapsed = time.perf_counter() - start
        if not rows:
            return OCRResult(raw_text="", confidence=0.0, bounding_boxes=[], processing_time=elapsed)
        texts = []
        confs = []
        boxes = []
        for box, text, conf in rows:
            texts.append(str(text))
            confs.append(float(conf))
            boxes.append(box)
        combined = " ".join(texts)
        avg = sum(confs) / len(confs) if confs else 0.0
        return OCRResult(raw_text=combined, confidence=avg, bounding_boxes=boxes, processing_time=elapsed)


_ENGINE: Optional[OCREngine] = None


def get_ocr_engine(engine_name: str, languages: str, device: str) -> OCREngine:
    global _ENGINE
    if _ENGINE is None:
        langs = [p.strip() for p in languages.split(",") if p.strip()] or ["en"]
        if engine_name.lower() != "easyocr":
            raise RuntimeError(f"Unsupported OCR engine: {engine_name}")
        ocr_device = device
        if device == "auto":
            from packages.device.probe import select_device

            ocr_device = select_device("auto").device
        _ENGINE = EasyOCREngine(langs, ocr_device)
    return _ENGINE
