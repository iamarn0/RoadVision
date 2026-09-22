"""Top-N native plate crops per vehicle track.

A vehicle can stay in view for ~250 frames while the readable plate only appears
in a short window. Keep those crops until the track closes, then pick by total
image-quality score. Full 2688x1520 frames are not stored here.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


def _score(item: dict[str, Any]) -> float:
    return float(item.get("total_score") or item.get("quality") or 0.0)


def _rank_key(item: dict[str, Any]) -> tuple[int, float]:
    from app.preprocessing.quality import is_good_plate_evidence

    return (1 if is_good_plate_evidence(item) else 0, _score(item))


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
        st.candidates.sort(key=_rank_key, reverse=True)
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
        dest.candidates.sort(key=_rank_key, reverse=True)
        dest.candidates = dest.candidates[: self.top_n]

    def winner(self, track_id: int) -> dict[str, Any] | None:
        cands = self.state(track_id).candidates
        return cands[0] if cands else None

    def items(self) -> list[tuple[int, TrackCandidateState]]:
        return list(self._tracks.items())
