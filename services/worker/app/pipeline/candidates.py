"""Top-N native plate crops per vehicle track.

A vehicle can stay in view for ~250 frames while the readable plate only appears
in a short window. Keep those crops until the track closes, then pick by total
image-quality score. Full 2688x1520 frames are not stored here.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


# A plate this much wider is a closer view. Smaller gaps are the same distance,
# so sharpness still breaks the tie.
CLOSER_WIDTH_RATIO = 1.12


def _score(item: dict[str, Any]) -> float:
    return float(item.get("total_score") or item.get("quality") or 0.0)


def _plate_width(item: dict[str, Any]) -> float:
    width = item.get("plate_width")
    if width is None:
        return 0.0
    return float(width)


def _is_good(item: dict[str, Any]) -> bool:
    from app.preprocessing.quality import is_good_plate_evidence

    return is_good_plate_evidence(item)


def plate_is_closer_view(candidate: dict[str, Any], current: dict[str, Any]) -> bool:
    """True when the candidate is the frame to keep.

    Approaching traffic is worst on the first frame and departing traffic is
    worst on the last frame. Plate width grows as the vehicle nears the camera,
    so a clearly wider plate replaces a sharper but farther crop.
    """
    candidate_good = _is_good(candidate)
    current_good = _is_good(current)
    if candidate_good != current_good:
        return candidate_good
    candidate_width = _plate_width(candidate)
    current_width = _plate_width(current)
    if candidate_width <= 0.0 and current_width <= 0.0:
        return _score(candidate) > _score(current)
    if candidate_width > current_width * CLOSER_WIDTH_RATIO:
        return True
    if current_width > candidate_width * CLOSER_WIDTH_RATIO:
        return False
    return _score(candidate) > _score(current)


def _keep_key(item: dict[str, Any]) -> tuple[int, float, float]:
    return (1 if _is_good(item) else 0, _plate_width(item), _score(item))


@dataclass
class TrackCandidateState:
    detections: int = 0
    valid: int = 0
    max_width: float = 0.0
    max_height: float = 0.0
    candidates: list[dict[str, Any]] = field(default_factory=list)


class PlateCandidateStore:
    def __init__(self, top_n: int = 20) -> None:
        self.top_n = max(1, int(top_n))
        self._tracks: dict[int, TrackCandidateState] = {}

    def state(self, track_id: int) -> TrackCandidateState:
        found = self._tracks.get(track_id)
        if found is None:
            found = TrackCandidateState()
            self._tracks[track_id] = found
        return found

    def record_detection(
        self,
        track_id: int,
        *,
        width: float,
        height: float,
        accepted: bool,
        candidate: dict[str, Any] | None = None,
    ) -> None:
        st = self.state(track_id)
        st.detections += 1
        st.max_width = max(st.max_width, float(width))
        st.max_height = max(st.max_height, float(height))
        if not accepted or candidate is None:
            return
        st.valid += 1
        st.candidates.append(candidate)
        st.candidates.sort(key=_keep_key, reverse=True)
        if len(st.candidates) > self.top_n:
            st.candidates = st.candidates[: self.top_n]

    def merge(self, dest_id: int, source_id: int) -> None:
        if dest_id == source_id or source_id not in self._tracks:
            return
        dest = self.state(dest_id)
        src = self._tracks.pop(source_id)
        dest.detections += src.detections
        dest.valid += src.valid
        dest.max_width = max(dest.max_width, src.max_width)
        dest.max_height = max(dest.max_height, src.max_height)
        dest.candidates.extend(src.candidates)
        dest.candidates.sort(key=_keep_key, reverse=True)
        dest.candidates = dest.candidates[: self.top_n]

    def winner(self, track_id: int) -> dict[str, Any] | None:
        cands = list(self.state(track_id).candidates)
        if not cands:
            return None
        good = [item for item in cands if _is_good(item)]
        pool = good or cands
        widest = max(_plate_width(item) for item in pool)
        if widest <= 0.0:
            return max(pool, key=_score)
        near = [item for item in pool if _plate_width(item) >= widest / CLOSER_WIDTH_RATIO]
        return max(near, key=_score)

    def items(self) -> list[tuple[int, TrackCandidateState]]:
        return list(self._tracks.items())
