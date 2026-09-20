from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass, field
from typing import Optional

from app.normalization.plates import NormalizedPlate, normalize_plate


def _levenshtein(a: str, b: str) -> int:
    if a == b:
        return 0
    if not a:
        return len(b)
    if not b:
        return len(a)
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            ins, delete, sub = prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)
            cur.append(min(ins, delete, sub))
        prev = cur
    return prev[-1]


@dataclass
class ObservationRecord:
    frame_number: int
    timestamp: float
    raw: str
    normalized: str
    ocr_confidence: float
    plate_confidence: float
    vehicle_confidence: float
    vehicle_type: str
    plate_box: dict
    vehicle_box: dict
    plate_area: float
    sharpness: float
    image_full: object
    image_vehicle: object
    image_plate: object


@dataclass
class UniqueDetection:
    track_id: int
    vehicle_type: str
    raw_ocr_text: Optional[str]
    normalized_plate_text: Optional[str]
    ocr_confidence: float
    plate_detection_confidence: float
    vehicle_detection_confidence: float
    status: str
    first_seen: float
    last_seen: float
    best_frame: int
    consistency_score: float
    observations: list[ObservationRecord] = field(default_factory=list)
    best: Optional[ObservationRecord] = None
    uncertain: bool = False


def confidence_status(
    ocr_conf: float,
    consistency: float,
    high: float,
    medium: float,
    low: float,
) -> str:
    if consistency < 0.45:
        return "needs_verification"
    if ocr_conf >= high and consistency >= 0.7:
        return "high_confidence"
    if ocr_conf >= medium:
        return "medium_confidence"
    if ocr_conf >= low:
        return "low_confidence"
    return "uncertain"


def aggregate_track(
    track_id: int,
    vehicle_type: str,
    observations: list[ObservationRecord],
    high: float,
    medium: float,
    low: float,
) -> UniqueDetection:
    if not observations:
        return UniqueDetection(
            track_id=track_id,
            vehicle_type=vehicle_type,
            raw_ocr_text=None,
            normalized_plate_text=None,
            ocr_confidence=0.0,
            plate_detection_confidence=0.0,
            vehicle_detection_confidence=0.0,
            status="uncertain",
            first_seen=0.0,
            last_seen=0.0,
            best_frame=0,
            consistency_score=0.0,
            uncertain=True,
        )

    texts = [o.normalized for o in observations if o.normalized]
    counts = Counter(texts)
    scored: dict[str, float] = defaultdict(float)
    for o in observations:
        if not o.normalized:
            continue
        scored[o.normalized] += o.ocr_confidence + 0.15 * counts[o.normalized]

    winner = None
    if scored:
        winner = max(scored, key=scored.get)
        close = [t for t in scored if t != winner and _levenshtein(t, winner) <= 2]
        # Keep winner; disagreement is recorded as consistency, not silently rewritten.

    matching = [o for o in observations if o.normalized == winner] if winner else observations
    consistency = (len(matching) / len(observations)) if observations else 0.0
    if winner and counts and counts.most_common(1)[0][0] != winner:
        consistency *= 0.8

    best = max(
        observations,
        key=lambda o: (
            0.35 * o.ocr_confidence
            + 0.25 * o.plate_confidence
            + 0.2 * min(1.0, o.plate_area / 4000.0)
            + 0.2 * min(1.0, o.sharpness / 200.0)
        ),
    )
    ocr_conf = max((o.ocr_confidence for o in matching), default=best.ocr_confidence)
    status = confidence_status(ocr_conf, consistency, high, medium, low)
    disagree = False
    if winner:
        for text, _n in counts.most_common():
            if text != winner and _levenshtein(text, winner) > 2 and counts[text] >= max(2, counts[winner] * 0.4):
                disagree = True
                status = "needs_verification"
                break

    raw_best = next((o.raw for o in matching if o.normalized == winner), best.raw)
    return UniqueDetection(
        track_id=track_id,
        vehicle_type=vehicle_type,
        raw_ocr_text=raw_best,
        normalized_plate_text=winner,
        ocr_confidence=ocr_conf,
        plate_detection_confidence=max(o.plate_confidence for o in observations),
        vehicle_detection_confidence=max(o.vehicle_confidence for o in observations),
        status=status,
        first_seen=min(o.timestamp for o in observations),
        last_seen=max(o.timestamp for o in observations),
        best_frame=best.frame_number,
        consistency_score=consistency,
        observations=observations,
        best=best,
        uncertain=disagree or winner is None,
    )
