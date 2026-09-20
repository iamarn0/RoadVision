import re
from dataclasses import dataclass


@dataclass
class NormalizedPlate:
    raw_ocr_text: str
    normalized_plate_text: str
    uncertain: bool


_PUNCT = re.compile(r"[^A-Z0-9]")
_SPACE = re.compile(r"\s+")


def normalize_plate(raw: str) -> NormalizedPlate:
    original = raw or ""
    text = original.upper()
    text = text.replace("|", "I")
    text = _SPACE.sub("", text)
    text = _PUNCT.sub("", text)
    uncertain = False
    if len(text) < 4 or len(text) > 12:
        uncertain = True
    return NormalizedPlate(raw_ocr_text=original.strip(), normalized_plate_text=text, uncertain=uncertain)
