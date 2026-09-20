from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from packages.overlay_clock import overlay_at, origin_from_metrics

INDEX_NAME = "index.json"


def index_path(captures_dir: Path) -> Path:
    return captures_dir / INDEX_NAME


def load_index(captures_dir: Path) -> dict[str, Any]:
    path = index_path(captures_dir)
    if not path.is_file():
        return {"overlay_clock": None, "items": []}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"overlay_clock": None, "items": []}
    if isinstance(data, list):
        return {"overlay_clock": None, "items": data}
    items = data.get("items")
    return {
        "overlay_clock": data.get("overlay_clock"),
        "items": items if isinstance(items, list) else [],
    }


def save_index(captures_dir: Path, data: dict[str, Any]) -> None:
    captures_dir.mkdir(parents=True, exist_ok=True)
    index_path(captures_dir).write_text(json.dumps(data, indent=2), encoding="utf-8")


def overlay_for_seconds(overlay_clock: dict[str, Any] | None, seconds: float) -> str | None:
    if not overlay_clock:
        return None
    origin = origin_from_metrics({"overlay_clock": overlay_clock})
    if origin is None:
        return None
    return overlay_at(origin, seconds)


def plate_index_item(
    track_id: int,
    first_seen: float,
    last_seen: float,
    vehicle_type: str | None,
    overlay_clock: dict[str, Any] | None,
    plate_confidence: float | None = None,
    vehicle_confidence: float | None = None,
) -> dict[str, Any]:
    return {
        "key": f"plate-{track_id}",
        "track_id": track_id,
        "kind": "plate",
        "vehicle_type": vehicle_type,
        "first_seen_seconds": float(first_seen),
        "last_seen_seconds": float(last_seen),
        "captured_at": overlay_for_seconds(overlay_clock, first_seen),
        "last_seen_overlay": overlay_for_seconds(overlay_clock, last_seen),
        "plate_confidence": plate_confidence,
        "vehicle_confidence": vehicle_confidence,
    }


def snapshot_index_item(
    snapshot_id: int,
    first_seen: float,
    overlay_clock: dict[str, Any] | None,
) -> dict[str, Any]:
    return {
        "key": f"snapshot-{snapshot_id}",
        "track_id": snapshot_id,
        "kind": "snapshot",
        "vehicle_type": None,
        "first_seen_seconds": float(first_seen),
        "last_seen_seconds": float(first_seen),
        "captured_at": overlay_for_seconds(overlay_clock, first_seen),
    }


def replace_plate_items(
    captures_dir: Path,
    plate_items: list[dict[str, Any]],
    overlay_clock: dict[str, Any] | None = None,
) -> None:
    data = load_index(captures_dir)
    snapshots = [item for item in data["items"] if item.get("kind") == "snapshot"]
    if overlay_clock is not None:
        data["overlay_clock"] = overlay_clock
    save_index(captures_dir, {"overlay_clock": data.get("overlay_clock"), "items": snapshots + plate_items})


def upsert_index_item(captures_dir: Path, item: dict[str, Any], overlay_clock: dict[str, Any] | None = None) -> None:
    data = load_index(captures_dir)
    key = item.get("key")
    items = [existing for existing in data["items"] if existing.get("key") != key]
    items.append(item)
    if overlay_clock is not None:
        data["overlay_clock"] = overlay_clock
    save_index(captures_dir, {"overlay_clock": data.get("overlay_clock"), "items": items})


def item_by_key(data: dict[str, Any], key: str) -> dict[str, Any] | None:
    for item in data.get("items") or []:
        if item.get("key") == key:
            return item
    return None
