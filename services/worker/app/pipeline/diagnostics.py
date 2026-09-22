"""Per-vehicle plate-quality diagnostics.

Detail goes to JSON (and optional PNG crops), not INFO logs for every frame.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from app.pipeline.candidates import PlateCandidateStore, TrackCandidateState
from app.preprocessing.quality import PlateQualityConfig

logger = logging.getLogger("worker")

CANDIDATE_KEYS = (
    "frame_number",
    "timestamp",
    "plate_bbox",
    "plate_width",
    "plate_height",
    "plate_area",
    "plate_detection_confidence",
    "sharpness_score",
    "contrast_score",
    "brightness_score",
    "saturation_ratio",
    "exposure_score",
    "geometry_score",
    "total_score",
)


def _public_candidate(item: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key in CANDIDATE_KEYS:
        if key in item:
            out[key] = item[key]
    return out


def _best_frame(candidates: list[dict[str, Any]], key: str) -> int | None:
    if not candidates:
        return None
    best = max(candidates, key=lambda c: float(c.get(key) or 0.0))
    frame = best.get("frame_number")
    return int(frame) if frame is not None else None


def track_report(
    track_id: int,
    vehicle: dict[str, Any],
    state: TrackCandidateState,
    selected_frame: int | None,
) -> dict[str, Any]:
    cands = state.candidates
    first = int(vehicle.get("first_frame") or 0)
    last = int(vehicle.get("last_frame") or first)
    frames = int(vehicle.get("frame_count") or max(0, last - first + 1))
    winner = cands[0] if cands else None
    final_frame = selected_frame
    if final_frame is None and winner is not None:
        final_frame = int(winner.get("frame_number") or 0)
    report = {
        "vehicle_id": track_id,
        "first_frame": first,
        "last_frame": last,
        "number_of_vehicle_frames": frames,
        "number_of_plate_detections": state.detections,
        "number_of_valid_plate_candidates": state.valid,
        "max_plate_width": state.max_width,
        "max_plate_height": state.max_height,
        "best_sharpness_frame": _best_frame(cands, "sharpness_score"),
        "best_size_frame": _best_frame(cands, "plate_area"),
        "best_exposure_frame": _best_frame(cands, "exposure_score"),
        "final_selected_frame": final_frame,
        "candidates": [_public_candidate(c) for c in cands],
    }
    report["summary_text"] = (
        f"Vehicle ID: {track_id}\n"
        f"-------------------------\n"
        f"Vehicle frames: {frames}\n"
        f"Plate detections: {state.detections}\n"
        f"Valid candidates: {state.valid}\n"
        f"\n"
        f"Max plate width: {state.max_width:.0f} px\n"
        f"Max plate height: {state.max_height:.0f} px\n"
        f"\n"
        f"Best sharpness frame: {report['best_sharpness_frame']}\n"
        f"Best size frame: {report['best_size_frame']}\n"
        f"Best exposure frame: {report['best_exposure_frame']}\n"
        f"Final selected frame: {final_frame}\n"
    )
    return report


def video_summary(
    *,
    width: int,
    height: int,
    fps: float,
    duration: float | None,
    frame_count: int | None,
    vehicle_meta: dict[int, dict[str, Any]],
    store: PlateCandidateStore,
    captures: dict[int, dict[str, Any]],
    config: PlateQualityConfig,
) -> dict[str, Any]:
    reports = []
    with_det = 0
    with_five = 0
    with_min_width = 0
    with_usable = 0
    for track_id, info in vehicle_meta.items():
        state = store.state(track_id)
        capture = captures.get(track_id)
        selected = int(capture["best_frame"]) if capture and capture.get("best_frame") is not None else None
        reports.append(track_report(track_id, info, state, selected))
        if state.detections:
            with_det += 1
        if state.detections >= 5:
            with_five += 1
        if state.max_width >= config.min_width_px:
            with_min_width += 1
        if state.valid:
            with_usable += 1
    return {
        "video": {
            "resolution": f"{width}x{height}",
            "width": width,
            "height": height,
            "fps": fps,
            "duration_sec": duration,
            "frames": frame_count,
        },
        "vehicles": {
            "total_vehicle_tracks": len(vehicle_meta),
        },
        "plates": {
            "vehicles_with_plate_detections": with_det,
            "vehicles_with_at_least_5_plate_detections": with_five,
            "vehicles_with_plate_width_at_least_minimum": with_min_width,
            "vehicles_with_usable_quality_candidate": with_usable,
            "min_width_px": config.min_width_px,
        },
        "selection": {
            "vehicles_selected_by_image_quality": with_usable,
        },
        "tracks": reports,
    }


def write_diagnostics(
    diagnostics_dir: Path,
    summary: dict[str, Any],
    store: PlateCandidateStore,
    *,
    save_candidate_png: bool,
) -> None:
    diagnostics_dir.mkdir(parents=True, exist_ok=True)
    (diagnostics_dir / "summary.json").write_text(
        json.dumps({k: v for k, v in summary.items() if k != "tracks"}, indent=2) + "\n",
        encoding="utf-8",
    )
    from app.preprocessing.plates import save_png

    for report in summary.get("tracks") or []:
        track_id = int(report["vehicle_id"])
        (diagnostics_dir / f"track_{track_id}.json").write_text(
            json.dumps(report, indent=2) + "\n",
            encoding="utf-8",
        )
        logger.debug("plate diagnostics\n%s", report.get("summary_text") or "")
        if not save_candidate_png:
            continue
        crop_dir = diagnostics_dir / f"track_{track_id}"
        for item in store.state(track_id).candidates:
            image = item.get("image_plate")
            frame_n = item.get("frame_number")
            if image is None or getattr(image, "size", 0) == 0 or frame_n is None:
                continue
            save_png(crop_dir / f"frame_{int(frame_n)}.png", image)
