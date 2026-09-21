from __future__ import annotations

import json
import logging
import threading
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

import cv2
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from app.config import PROFILES, Settings, get_settings
from app.detection.detector import ModelNotFoundError, VehicleDetector
from app.pipeline.association import associate_plates
from app.pipeline.capture_merge import find_same_passage
from app.pipeline.plate_search import (
    MIN_PLATE_SEARCH_AREA,
    search_plates_in_vehicles,
    skip_ids_with_strong_evidence,
    vehicle_capture_pads,
)
from packages.capture_index import plate_index_item, replace_plate_items
from app.pipeline.video_source import UploadedFileSource
from app.plate_detection.detector import PlateDetector
from app.preprocessing.plates import (
    JPEG_EVIDENCE_QUALITY,
    JPEG_PLATE_QUALITY,
    PLATE_CROP_PAD_DAY,
    PLATE_CROP_PAD_NIGHT,
    ROI_ENHANCE_LUMINANCE_MAX,
    crop_box,
    crop_box_asymmetric,
    enhance_low_light_frame,
    frame_luminance,
    has_plate_evidence,
    is_better_evidence,
    save_jpeg,
)
from app.rendering.annotate import AnnotatedVideoRenderer, draw_overlay
from app.tracking.tracker import VehicleTracker
from packages.db.enums import AssetType, ConfidenceStatus, JobStatus
from packages.db.models import MediaAsset, Observation, PlateDetection, ProcessingJob, VehicleTrack, Video
from packages.device.probe import DeviceError, select_device

logger = logging.getLogger("worker")


class PipelineError(Exception):
    def __init__(self, error_code: str, message: str) -> None:
        self.error_code = error_code
        self.message = message
        super().__init__(message)


def _control_client():
    import redis

    return redis.Redis.from_url(get_settings().redis_url, decode_responses=True)


def _cancelled(job_id: str) -> bool:
    try:
        return _control_client().get(f"roadvision:job:cancel:{job_id}") == "1"
    except Exception:
        return False


def _paused(job_id: str) -> bool:
    try:
        return _control_client().get(f"roadvision:job:pause:{job_id}") == "1"
    except Exception:
        return False


def _consume_capture(job_id: str) -> bool:
    try:
        client = _control_client()
        key = f"roadvision:job:capture:{job_id}"
        if client.get(key) != "1":
            return False
        client.delete(key)
        return True
    except Exception:
        return False


def _set_capture_result(job_id: str, result: str) -> None:
    try:
        _control_client().set(f"roadvision:job:capture-result:{job_id}", result, ex=30)
    except Exception:
        logger.debug("capture result publish skipped", exc_info=True)


def _visible_plate_captures(
    frame_image: Any,
    vehicles: list[Any],
    frame_crops: list[dict[str, Any]],
    best_by_track: dict[int, dict[str, Any]],
    width: int,
    height: int,
) -> list[dict[str, Any]]:
    """Plates shown on the live overlay: this frame's associations, else best crop for visible tracks."""
    by_id: dict[int, dict[str, Any]] = {}
    for item in frame_crops:
        track_id = item.get("track_id")
        if track_id is None:
            continue
        by_id[int(track_id)] = item
    for vehicle in vehicles:
        if vehicle.track_id in by_id:
            continue
        best = best_by_track.get(vehicle.track_id)
        if not best:
            continue
        plate_img = best.get("image_plate")
        if plate_img is None or getattr(plate_img, "size", 0) == 0:
            continue
        vx1, vy1, vx2, vy2 = vehicle.detection.bounding_box.clip(width, height).as_int()
        vehicle_img = crop_box(frame_image, vx1, vy1, vx2, vy2, pad=0.04)
        if vehicle_img is None or getattr(vehicle_img, "size", 0) == 0:
            vehicle_img = best.get("image_vehicle")
        by_id[vehicle.track_id] = {
            "track_id": vehicle.track_id,
            "image_plate": plate_img.copy() if hasattr(plate_img, "copy") else plate_img,
            "image_vehicle": vehicle_img.copy() if vehicle_img is not None and hasattr(vehicle_img, "copy") else vehicle_img,
        }
    return list(by_id.values())


def _write_manual_captures(captures_dir: Path, last_associated: list[dict[str, Any]]) -> int:
    written = 0
    for item in last_associated:
        plate_img = item.get("image_plate")
        vehicle_img = item.get("image_vehicle")
        track_id = item.get("track_id")
        if track_id is None or plate_img is None or getattr(plate_img, "size", 0) == 0:
            continue
        save_jpeg(captures_dir / f"track_{track_id}.jpg", plate_img, JPEG_PLATE_QUALITY)
        if vehicle_img is not None and getattr(vehicle_img, "size", 0) > 0:
            save_jpeg(captures_dir / f"vehicle_{track_id}.jpg", vehicle_img, JPEG_EVIDENCE_QUALITY)
        written += 1
    return written


def _publish_startup_frame(video_path: Path, live_frame_path: Path, live_raw_path: Path) -> bool:
    """Write the first decoded frame so the UI can play before models load."""
    cap = cv2.VideoCapture(str(video_path))
    try:
        ok, image = cap.read()
        if not ok or image is None:
            logger.warning("startup preview: could not read first frame from %s", video_path)
            return False
        save_jpeg(live_raw_path, image, JPEG_EVIDENCE_QUALITY)
        encoded_ok, encoded = cv2.imencode(".jpg", image, [int(cv2.IMWRITE_JPEG_QUALITY), 70])
        if encoded_ok:
            live_frame_path.write_bytes(encoded.tobytes())
        logger.info("startup preview published")
        return True
    except Exception:
        logger.exception("startup preview failed")
        return False
    finally:
        cap.release()


def _write_live_frames(live_frame_path: Path, live_raw_path: Path, overlay: Any, raw_image: Any) -> bytes | None:
    ok, encoded = cv2.imencode(".jpg", overlay, [int(cv2.IMWRITE_JPEG_QUALITY), 70])
    jpeg = encoded.tobytes() if ok else None
    if jpeg:
        live_frame_path.write_bytes(jpeg)
    if raw_image is not None and getattr(raw_image, "size", 0) > 0:
        save_jpeg(live_raw_path, raw_image, JPEG_EVIDENCE_QUALITY)
    return jpeg


def _start_overlay_clock(video_path: Path) -> tuple[threading.Thread, dict[str, Any]]:
    holder: dict[str, Any] = {"clock": None, "done": False}

    def _run() -> None:
        try:
            from app.ocr.overlay import extract_overlay_clock_from_video

            holder["clock"] = extract_overlay_clock_from_video(video_path)
        except Exception:
            logger.exception("overlay clock extraction skipped")
        finally:
            holder["done"] = True

    thread = threading.Thread(target=_run, name="overlay-clock", daemon=True)
    thread.start()
    return thread, holder


def _sync_captures_index(
    captures_dir: Path,
    best_by_track: dict[int, dict[str, Any]],
    overlay_clock: dict[str, Any] | None,
) -> None:
    items = [
        plate_index_item(
            track_id,
            float(capture.get("first_seen") or 0.0),
            float(capture.get("last_seen") or capture.get("first_seen") or 0.0),
            capture.get("vehicle_type"),
            overlay_clock,
            plate_confidence=capture.get("plate_confidence"),
            vehicle_confidence=capture.get("vehicle_confidence"),
        )
        for track_id, capture in best_by_track.items()
        if capture.get("published")
    ]
    replace_plate_items(captures_dir, items, overlay_clock)


SHRINK_PUBLISH_STREAK = 2


def capture_is_due_to_publish(
    capture: dict[str, Any],
    visible: bool,
    shrink_threshold: int = SHRINK_PUBLISH_STREAK,
) -> bool:
    if capture.get("published"):
        return False
    if not visible:
        return True
    return int(capture.get("shrink_streak") or 0) >= shrink_threshold


def _note_vehicle_motion(capture: dict[str, Any], area: float) -> None:
    prev_area = float(capture.get("last_vehicle_area") or 0.0)
    if prev_area > 0 and area < prev_area * 0.95:
        capture["shrink_streak"] = int(capture.get("shrink_streak") or 0) + 1
    elif area >= prev_area * 1.05:
        capture["shrink_streak"] = 0
    capture["last_vehicle_area"] = area


def _capture_for_vehicle(
    best_by_track: dict[int, dict[str, Any]],
    track_id: int,
) -> tuple[int | None, dict[str, Any] | None]:
    direct = best_by_track.get(track_id)
    if direct is not None:
        return track_id, direct
    for cid, capture in best_by_track.items():
        if track_id in (capture.get("source_ids") or []):
            return cid, capture
        if capture.get("active_tid") == track_id:
            return cid, capture
    return None, None


def _vehicle_is_published(track_id: int, best_by_track: dict[int, dict[str, Any]]) -> bool:
    _cid, capture = _capture_for_vehicle(best_by_track, track_id)
    return bool(capture and capture.get("published"))


def _best_lookup(best_by_track: dict[int, dict[str, Any]]) -> dict[int, dict[str, Any]]:
    lookup = dict(best_by_track)
    for capture in best_by_track.values():
        for sid in capture.get("source_ids") or []:
            lookup.setdefault(int(sid), capture)
        active = capture.get("active_tid")
        if active is not None:
            lookup.setdefault(int(active), capture)
    return lookup


def _publish_track_capture(
    captures_dir: Path,
    capture_id: int,
    capture: dict[str, Any],
    overlay_clock: dict[str, Any] | None,
) -> bool:
    if capture.get("published"):
        return False
    plate = capture.get("image_plate")
    if plate is None or getattr(plate, "size", 0) == 0:
        capture["published"] = True
        return False
    vehicle_img = capture.get("image_vehicle")
    full = capture.get("image_full")
    save_jpeg(captures_dir / f"track_{capture_id}.jpg", plate, JPEG_PLATE_QUALITY)
    if vehicle_img is not None and getattr(vehicle_img, "size", 0) > 0:
        save_jpeg(captures_dir / f"vehicle_{capture_id}.jpg", vehicle_img, JPEG_EVIDENCE_QUALITY)
    if full is not None and getattr(full, "size", 0) > 0:
        save_jpeg(captures_dir / f"full_{capture_id}.jpg", full, JPEG_EVIDENCE_QUALITY)
    sidecar = plate_index_item(
        capture_id,
        float(capture.get("first_seen") or 0.0),
        float(capture.get("last_seen") or 0.0),
        capture.get("vehicle_type"),
        overlay_clock,
        plate_confidence=capture.get("plate_confidence"),
        vehicle_confidence=capture.get("vehicle_confidence"),
    )
    (captures_dir / f"track_{capture_id}.json").write_text(json.dumps(sidecar), encoding="utf-8")
    capture["published"] = True
    return True


def _publish_due_captures(
    captures_dir: Path,
    vehicles: list[Any],
    best_by_track: dict[int, dict[str, Any]],
    overlay_clock: dict[str, Any] | None,
) -> int:
    active = {v.track_id for v in vehicles}
    for vehicle in vehicles:
        _cid, capture = _capture_for_vehicle(best_by_track, vehicle.track_id)
        if capture is None:
            continue
        capture["active_tid"] = vehicle.track_id
        ids = set(capture.get("source_ids") or [])
        ids.add(vehicle.track_id)
        capture["source_ids"] = ids
        _note_vehicle_motion(capture, vehicle.detection.bounding_box.area)
    written = 0
    for capture_id, capture in best_by_track.items():
        live_id = capture.get("active_tid", capture_id)
        visible = capture_id in active or live_id in active or bool(active.intersection(capture.get("source_ids") or []))
        if capture_is_due_to_publish(capture, visible):
            if _publish_track_capture(captures_dir, capture_id, capture, overlay_clock):
                written += 1
    return written


def _publish_all_pending(
    captures_dir: Path,
    best_by_track: dict[int, dict[str, Any]],
    overlay_clock: dict[str, Any] | None,
) -> int:
    written = 0
    for capture_id, capture in best_by_track.items():
        if _publish_track_capture(captures_dir, capture_id, capture, overlay_clock):
            written += 1
    return written


def _handle_manual_capture(job_id: str, captures_dir: Path, last_associated: list[dict[str, Any]]) -> None:
    if not _consume_capture(job_id):
        return
    written = _write_manual_captures(captures_dir, last_associated)
    _set_capture_result(job_id, "ok")


def _publish_preview(job_id: UUID, jpeg_bytes: bytes, payload: dict[str, Any]) -> None:
    try:
        import redis

        client = redis.Redis.from_url(get_settings().redis_url)
        client.set(f"roadvision:job:preview:{job_id}", jpeg_bytes, ex=600)
        client.set(f"roadvision:job:live:{job_id}", __import__("json").dumps(payload), ex=600)
    except Exception:
        logger.debug("preview publish skipped", exc_info=True)


def _plate_status(conf: float, high: float, medium: float, low: float) -> str:
    if conf >= high:
        return ConfidenceStatus.HIGH_CONFIDENCE.value
    if conf >= medium:
        return ConfidenceStatus.MEDIUM_CONFIDENCE.value
    if conf >= low:
        return ConfidenceStatus.LOW_CONFIDENCE.value
    return ConfidenceStatus.UNCERTAIN.value


def process_job(db: Session, job_id: UUID) -> None:
    settings = get_settings()
    job = db.get(ProcessingJob, job_id)
    if not job:
        return
    video = db.get(Video, job.video_id)
    if not video:
        _fail(db, job, "VIDEO_INVALID", "Video record is missing")
        return

    profile = PROFILES.get(job.processing_profile or "balanced", PROFILES["balanced"])
    image_size = int(profile.get("inference_image_size", settings.inference_image_size))
    # Realtime playback mode: process every frame at source cadence; detect plates often.
    frame_skip = 0
    plate_interval = max(1, int(profile.get("ocr_interval_frames", settings.ocr_interval_frames)))
    use_half = bool(profile.get("use_half_precision", settings.use_half_precision))
    overrides = (job.model_versions or {}).get("overrides") or {}
    image_size = int(overrides.get("inference_image_size") or image_size)
    if overrides.get("frame_skip") is not None:
        frame_skip = max(0, int(overrides.get("frame_skip")))
    plate_interval = max(1, int(overrides.get("ocr_interval_frames") or plate_interval))
    # Prefer denser plate scanning for continuous capture.
    if plate_interval > 2 and not overrides.get("ocr_interval_frames"):
        plate_interval = 2

    job.status = JobStatus.PROCESSING.value
    job.started_at = datetime.now(UTC)
    job.ocr_engine = "disabled"
    db.commit()

    storage_root = settings.storage_root_path
    video_path = storage_root / video.storage_key
    if not video_path.exists():
        _fail(db, job, "STORAGE_ERROR", f"Original video is missing: {video.storage_key}")
        return

    live_dir = storage_root / "processed" / str(job.id)
    captures_dir = live_dir / "captures"
    live_dir.mkdir(parents=True, exist_ok=True)
    captures_dir.mkdir(parents=True, exist_ok=True)
    live_frame_path = live_dir / "live.jpg"
    live_raw_path = live_dir / "live_raw.jpg"
    _publish_startup_frame(video_path, live_frame_path, live_raw_path)

    try:
        selection = select_device(
            settings.processing_device,
            settings.cuda_device,
            use_half,
            settings.auto_fallback_to_cpu,
        )
    except DeviceError as exc:
        _fail(db, job, exc.error_code, exc.message)
        return

    job.requested_device = settings.processing_device
    job.actual_device = selection.device
    job.gpu_name = selection.gpu_name
    job.fallback_reason = selection.fallback_reason
    db.commit()
    logger.info(
        "inference device=%s gpu=%s cuda=%s",
        selection.device,
        selection.gpu_name,
        selection.cuda_available,
    )

    overlay_clock: dict[str, Any] | None = None
    overlay_applied = False
    overlay_thread, overlay_holder = _start_overlay_clock(video_path)
    best_by_track: dict[int, dict[str, Any]] = {}
    vehicle_meta: dict[int, dict[str, Any]] = {}

    def _maybe_apply_overlay_clock() -> None:
        nonlocal overlay_clock, overlay_applied
        if overlay_applied:
            return
        clock = overlay_holder.get("clock")
        if not clock:
            return
        overlay_clock = clock
        overlay_applied = True
        logger.info("video overlay clock origin=%s", overlay_clock.get("origin_iso"))
        metrics = dict(job.metrics or {})
        metrics["overlay_clock"] = overlay_clock
        job.metrics = metrics
        flag_modified(job, "metrics")
        try:
            db.commit()
        except Exception:
            logger.exception("overlay clock persist skipped")
        _sync_captures_index(captures_dir, best_by_track, overlay_clock)

    try:
        vehicle_detector = VehicleDetector(
            str(settings.resolved_vehicle_model_path),
            selection.device,
            float(overrides.get("vehicle_confidence") or settings.vehicle_confidence),
            settings.iou_threshold,
            image_size,
            selection.fp16_enabled,
        )
        plate_detector = PlateDetector(
            str(settings.resolved_plate_model_path),
            selection.device,
            float(overrides.get("plate_confidence") or settings.plate_confidence),
            settings.iou_threshold,
            image_size,
            selection.fp16_enabled,
        )
    except ModelNotFoundError as exc:
        _fail(
            db,
            job,
            "MODEL_NOT_FOUND",
            f"Required model:\n{exc.name}\n\nExpected location:\n{exc.path}\n\nConfigure the model path and retry.",
        )
        return
    except Exception as exc:
        _fail(db, job, "PROCESSING_FAILED", str(exc))
        return

    tracker = VehicleTracker(vehicle_detector)

    source = UploadedFileSource(video_path, source_id=str(video.id))
    annotated_rel = f"processed/{job.id}.mp4"
    annotated_path = storage_root / annotated_rel
    renderer = None
    processed = 0
    skipped = 0
    failed_frames = 0
    start = time.perf_counter()
    last_fps = 0.0
    inference_times: list[float] = []
    peak_gpu = None
    playback_origin = None
    paused_total = 0.0
    last_associated: list[dict[str, Any]] = []
    last_manual_targets: list[dict[str, Any]] = []
    last_search_areas: dict[int, float] = {}
    last_overlay = None
    last_vehicles: list = []
    last_infer_index = -10_000
    last_full_plate_frame = -10_000
    index_dirty = 0
    index_flushed = False

    try:
        meta = source.open()
        source_fps = float(meta.fps or video.fps or 25.0)
        frame_duration = 1.0 / max(source_fps, 1.0)
        job.total_frames = meta.frame_count or job.total_frames
        renderer = AnnotatedVideoRenderer(annotated_path, source_fps, (meta.width, meta.height))
        last_plate_frame = -10_000

        for frame in source.frames():
            if _cancelled(str(job.id)):
                job.status = JobStatus.CANCELLED.value
                job.completed_at = datetime.now(UTC)
                db.commit()
                return

            paused_at = None
            while _paused(str(job.id)):
                if paused_at is None:
                    paused_at = time.perf_counter()
                if _cancelled(str(job.id)):
                    job.status = JobStatus.CANCELLED.value
                    job.completed_at = datetime.now(UTC)
                    db.commit()
                    return
                _handle_manual_capture(str(job.id), captures_dir, last_manual_targets)
                time.sleep(0.05)
            if paused_at is not None:
                pause_duration = time.perf_counter() - paused_at
                paused_total += pause_duration
                if playback_origin is not None:
                    playback_origin += pause_duration

            _handle_manual_capture(str(job.id), captures_dir, last_manual_targets)
            _maybe_apply_overlay_clock()

            video_ts = frame.timestamp if frame.timestamp is not None else frame.index * frame_duration
            # Clock starts on the first decoded frame so overlay OCR / model load
            # cannot mark the whole clip as "already late" and skip every infer.
            if playback_origin is None:
                playback_origin = time.perf_counter() - video_ts
            target_wall = playback_origin + video_ts
            now = time.perf_counter()
            behind = now > target_wall + frame_duration
            force_infer = frame.index - last_infer_index >= 5
            all_published = bool(best_by_track) and all(c.get("published") for c in best_by_track.values())
            visible_published = bool(last_vehicles) and all(
                _vehicle_is_published(v.track_id, best_by_track) for v in last_vehicles
            )
            cheap_behind = behind and not force_infer and visible_published and all_published
            if cheap_behind:
                skipped += 1
                shown = draw_overlay(
                    frame.image,
                    last_vehicles,
                    [],
                    {tid: {"plate_confidence": cap["plate_confidence"]} for tid, cap in best_by_track.items()},
                    video_ts,
                )
                last_overlay = shown
                renderer.write(shown)
                job.current_frame = frame.index
                job.skipped_frames = skipped
                if source_fps and meta.frame_count:
                    job.estimated_remaining_seconds = max(0.0, (meta.frame_count - frame.index - 1) / source_fps)
                    job.progress = min(99.0, 100.0 * (frame.index + 1) / meta.frame_count)
                if skipped % 2 == 0:
                    _write_live_frames(live_frame_path, live_raw_path, shown, frame.image)
                if skipped % 10 == 0:
                    db.commit()
                continue
            if not behind:
                delay = target_wall - now
                if delay > 0:
                    time.sleep(min(delay, frame_duration * 2))

            if frame_skip and frame.index % (frame_skip + 1) != 0:
                skipped += 1
                shown = draw_overlay(
                    frame.image,
                    last_vehicles,
                    [],
                    {tid: {"plate_confidence": cap["plate_confidence"]} for tid, cap in best_by_track.items()},
                    video_ts,
                )
                renderer.write(shown)
                continue

            t0 = time.perf_counter()
            last_infer_index = frame.index
            try:
                vehicles = tracker.update(frame.image, frame.index, frame.timestamp)
                last_vehicles = vehicles
            except RuntimeError as exc:
                if "out of memory" in str(exc).lower():
                    _handle_oom(db, job, settings)
                    return
                raise

            for v in vehicles:
                info = vehicle_meta.setdefault(
                    v.track_id,
                    {
                        "type": v.detection.class_name,
                        "first_frame": frame.index,
                        "first_seen": frame.timestamp,
                        "conf": v.detection.confidence,
                    },
                )
                info["last_frame"] = frame.index
                info["last_seen"] = frame.timestamp
                info["conf"] = max(info["conf"], v.detection.confidence)
                info["type"] = v.detection.class_name

            plates: list = []
            associated: list = []
            luminance = frame_luminance(frame.image)
            dark = luminance < ROI_ENHANCE_LUMINANCE_MAX
            interval = 2
            detecting_plates = frame.index - last_plate_frame >= interval
            if detecting_plates:
                skip_ids = skip_ids_with_strong_evidence(vehicles, _best_lookup(best_by_track), last_search_areas)
                detect_conf = min(float(plate_detector.confidence), 0.22) if dark else None
                for vehicle in vehicles:
                    if vehicle.track_id in skip_ids:
                        continue
                    box = vehicle.detection.bounding_box
                    if box.area < MIN_PLATE_SEARCH_AREA:
                        continue
                    last_search_areas[vehicle.track_id] = box.area
                associated = search_plates_in_vehicles(
                    frame.image,
                    vehicles,
                    plate_detector,
                    frame.index,
                    frame.timestamp,
                    skip_ids=skip_ids,
                    confidence=detect_conf,
                )
                if not associated and vehicles and frame.index - last_full_plate_frame >= 8:
                    detect_image = enhance_low_light_frame(frame.image) if dark else frame.image
                    plates = plate_detector.detect(
                        detect_image,
                        frame.index,
                        frame.timestamp,
                        confidence=detect_conf,
                    )
                    fallback = associate_plates(vehicles, plates)
                    taken = {item[0].track_id for item in associated}
                    associated.extend(pair for pair in fallback if pair[0].track_id not in taken)
                    last_full_plate_frame = frame.index
                last_plate_frame = frame.index

            frame_crops: list[dict[str, Any]] = []
            accepted_associated: list = []
            for vehicle, plate in associated:
                x1, y1, x2, y2 = plate.bounding_box.clip(meta.width, meta.height).as_int()
                vx1, vy1, vx2, vy2 = vehicle.detection.bounding_box.clip(meta.width, meta.height).as_int()
                plate_img = crop_box(frame.image, x1, y1, x2, y2, pad=0.08)
                pad_l, pad_t, pad_r, pad_b = vehicle_capture_pads(vehicle.detection.class_name)
                vehicle_img, _, _ = crop_box_asymmetric(frame.image, vx1, vy1, vx2, vy2, pad_l, pad_t, pad_r, pad_b)
                if plate_img.size == 0:
                    continue
                ok, score, sharp = has_plate_evidence(
                    plate_img,
                    float(x2 - x1),
                    float(y2 - y1),
                    plate.confidence,
                    dark=dark,
                )
                if not ok:
                    continue
                plate_pad = PLATE_CROP_PAD_NIGHT if dark else PLATE_CROP_PAD_DAY
                saved_plate = crop_box(frame.image, x1, y1, x2, y2, pad=plate_pad)
                if saved_plate.size == 0:
                    saved_plate = plate_img
                accepted_associated.append((vehicle, plate))
                observation = {
                    "frame_number": frame.index,
                    "timestamp": frame.timestamp,
                    "plate_confidence": plate.confidence,
                    "bounding_box": {"x1": x1, "y1": y1, "x2": x2, "y2": y2},
                }
                vehicle_box = {"x1": vx1, "y1": vy1, "x2": vx2, "y2": vy2}
                capture_id = vehicle.track_id
                previous = best_by_track.get(vehicle.track_id)
                if previous is None:
                    merged_id = find_same_passage(
                        best_by_track,
                        frame.timestamp,
                        vehicle_box,
                        saved_plate,
                        exclude_track_id=vehicle.track_id,
                    )
                    if merged_id is not None:
                        capture_id = merged_id
                        previous = best_by_track[merged_id]
                frame_crops.append(
                    {
                        "track_id": capture_id,
                        "image_plate": saved_plate.copy(),
                        "image_vehicle": vehicle_img.copy() if vehicle_img.size else None,
                    }
                )
                plate_area = float(max(1, x2 - x1) * max(1, y2 - y1))
                if previous and not is_better_evidence(previous, score, plate_area, sharp):
                    previous["last_seen"] = frame.timestamp
                    previous["observations"].append(observation)
                    continue
                observations = (previous or {}).get("observations", [])
                observations.append(observation)
                source_ids = set((previous or {}).get("source_ids") or [])
                source_ids.add(vehicle.track_id)
                source_ids.add(capture_id)
                was_published = bool((previous or {}).get("published"))
                best_by_track[capture_id] = {
                    "score": score,
                    "sharp": sharp,
                    "plate_area": plate_area,
                    "first_seen": (previous or {}).get("first_seen", frame.timestamp),
                    "last_seen": frame.timestamp,
                    "best_frame": frame.index,
                    "plate_confidence": plate.confidence,
                    "vehicle_confidence": vehicle.detection.confidence,
                    "vehicle_type": vehicle.detection.class_name,
                    "plate_box": {"x1": x1, "y1": y1, "x2": x2, "y2": y2},
                    "vehicle_box": vehicle_box,
                    "image_full": frame.image.copy(),
                    "image_vehicle": vehicle_img,
                    "image_plate": saved_plate,
                    "observations": observations,
                    "published": False,
                    "shrink_streak": int((previous or {}).get("shrink_streak") or 0),
                    "last_vehicle_area": float((previous or {}).get("last_vehicle_area") or 0.0),
                    "source_ids": source_ids,
                    "active_tid": vehicle.track_id,
                }
                if was_published:
                    _publish_track_capture(captures_dir, capture_id, best_by_track[capture_id], overlay_clock)

            published_now = _publish_due_captures(captures_dir, vehicles, best_by_track, overlay_clock)
            if published_now:
                index_dirty += 1
                _sync_captures_index(captures_dir, best_by_track, overlay_clock)
                index_flushed = True
                index_dirty = 0

            associated = accepted_associated

            if frame_crops:
                last_associated = frame_crops
            last_manual_targets = _visible_plate_captures(
                frame.image,
                vehicles,
                frame_crops,
                best_by_track,
                meta.width,
                meta.height,
            )
            _handle_manual_capture(str(job.id), captures_dir, last_manual_targets)

            inference_times.append(time.perf_counter() - t0)
            overlay = draw_overlay(
                frame.image,
                vehicles,
                associated,
                {tid: {"plate_confidence": cap["plate_confidence"]} for tid, cap in best_by_track.items()},
                frame.timestamp,
            )
            last_overlay = overlay
            renderer.write(overlay)

            jpeg = None
            if processed == 0 or frame.index % 2 == 0:
                jpeg = _write_live_frames(live_frame_path, live_raw_path, overlay, frame.image)
            if jpeg:
                _publish_preview(
                    job.id,
                    jpeg,
                    {
                        "job_id": str(job.id),
                        "status": "processing",
                        "current_frame": frame.index,
                        "total_frames": meta.frame_count or 0,
                        "timestamp_seconds": frame.timestamp,
                        "source_fps": source_fps,
                        "vehicles_detected": len(vehicle_meta),
                        "plates_captured": sum(1 for cap in best_by_track.values() if cap.get("published")),
                        "progress": min(99.0, 100.0 * (frame.index + 1) / meta.frame_count) if meta.frame_count else 0,
                    },
                )

            processed += 1
            elapsed = time.perf_counter() - start - paused_total
            last_fps = processed / elapsed if elapsed else 0.0
            remaining = None
            if source_fps and meta.frame_count:
                remaining = max(0.0, (meta.frame_count - frame.index - 1) / source_fps)
            job.current_frame = frame.index
            job.processed_frames = processed
            job.skipped_frames = skipped
            job.processing_fps = last_fps
            job.estimated_remaining_seconds = remaining
            job.progress = min(99.0, 100.0 * (frame.index + 1) / meta.frame_count) if meta.frame_count else 0
            job.vehicles_detected = len(vehicle_meta)
            job.plates_detected = sum(1 for cap in best_by_track.values() if cap.get("published"))
            if processed % 5 == 0:
                db.commit()
            try:
                import torch

                if torch.cuda.is_available():
                    used = torch.cuda.max_memory_allocated() / (1024 * 1024)
                    peak_gpu = max(peak_gpu or 0, used)
            except Exception:
                pass

        job.status = JobStatus.FINALIZING.value
        if not overlay_holder.get("done"):
            overlay_thread.join(timeout=8.0)
        _maybe_apply_overlay_clock()
        _publish_all_pending(captures_dir, best_by_track, overlay_clock)
        _sync_captures_index(captures_dir, best_by_track, overlay_clock)
        db.commit()
        _persist(
            db,
            job,
            vehicle_meta,
            best_by_track,
            storage_root,
            annotated_rel,
            annotated_path,
            settings,
            {
                "total_frames": meta.frame_count,
                "processed_frames": processed,
                "skipped_frames": skipped,
                "processing_fps": last_fps,
                "source_fps": source_fps,
                "average_frame_latency": sum(inference_times) / len(inference_times) if inference_times else None,
                "average_inference_latency": sum(inference_times) / len(inference_times) if inference_times else None,
                "vehicle_detection_count": len(vehicle_meta),
                "unique_vehicle_count": len(vehicle_meta),
                "plate_capture_count": len(best_by_track),
                "failed_frames": failed_frames,
                "peak_gpu_memory": peak_gpu,
                "ocr_enabled": False,
                "overlay_clock": overlay_clock,
            },
        )
        job.status = JobStatus.COMPLETED.value
        job.progress = 100
        job.completed_at = datetime.now(UTC)
        db.commit()
    except PipelineError as exc:
        _fail(db, job, exc.error_code, exc.message)
    except RuntimeError as exc:
        if "out of memory" in str(exc).lower():
            _handle_oom(db, job, settings)
        else:
            logger.exception("processing failed")
            _fail(db, job, "PROCESSING_FAILED", "Processing failed. See worker logs for details.")
    except Exception:
        logger.exception("processing failed")
        _fail(db, job, "PROCESSING_FAILED", "Processing failed. See worker logs for details.")
    finally:
        source.close()
        if renderer:
            renderer.close()


def _handle_oom(db: Session, job: ProcessingJob, settings: Settings) -> None:
    try:
        import torch

        torch.cuda.empty_cache()
    except Exception:
        pass
    message = (
        "CUDA ran out of memory. Reduce INFERENCE_IMAGE_SIZE, switch to the Performance profile, "
        "keep MAX_WORKERS=1, or enable AUTO_FALLBACK_TO_CPU."
    )
    if settings.auto_fallback_to_cpu:
        job.fallback_reason = "CUDA_OUT_OF_MEMORY"
        _fail(db, job, "CUDA_OUT_OF_MEMORY", message + " CPU fallback is enabled; retry the job.")
        return
    _fail(db, job, "CUDA_OUT_OF_MEMORY", message)


def _fail(db: Session, job: ProcessingJob, code: str, message: str) -> None:
    job.status = JobStatus.FAILED.value
    job.error_code = code
    job.error_message = message
    job.completed_at = datetime.now(UTC)
    db.commit()


def _persist(
    db: Session,
    job: ProcessingJob,
    vehicle_meta: dict[int, dict[str, Any]],
    best_by_track: dict[int, dict[str, Any]],
    storage_root: Path,
    annotated_rel: str,
    annotated_path: Path,
    settings: Settings,
    metrics: dict[str, Any],
) -> None:
    tracks: dict[int, VehicleTrack] = {}
    for track_id, info in vehicle_meta.items():
        track = VehicleTrack(
            processing_job_id=job.id,
            track_id=track_id,
            vehicle_type=info.get("type", "unknown"),
            first_frame=info.get("first_frame", 0),
            last_frame=info.get("last_frame", 0),
            first_seen_seconds=info.get("first_seen", 0.0),
            last_seen_seconds=info.get("last_seen", 0.0),
            detection_confidence=info.get("conf", 0.0),
        )
        db.add(track)
        db.flush()
        tracks[track_id] = track

    for track_id, capture in best_by_track.items():
        track = tracks.get(track_id)
        if not track:
            continue
        folder = storage_root / "evidence" / str(job.id) / f"track_{track_id}"
        folder.mkdir(parents=True, exist_ok=True)
        assets: dict[str, UUID] = {}
        for kind, image in (
            ("full_frame", capture.get("image_full")),
            ("vehicle_crop", capture.get("image_vehicle")),
            ("plate_crop", capture.get("image_plate")),
        ):
            if image is None or getattr(image, "size", 0) == 0:
                continue
            filename = f"{kind}_{uuid4().hex}.jpg"
            path = folder / filename
            quality = JPEG_PLATE_QUALITY if kind == "plate_crop" else JPEG_EVIDENCE_QUALITY
            save_jpeg(path, image, quality)
            rel = f"evidence/{job.id}/track_{track_id}/{filename}"
            atype = {
                "full_frame": AssetType.FULL_FRAME.value,
                "vehicle_crop": AssetType.VEHICLE_CROP.value,
                "plate_crop": AssetType.PLATE_CROP.value,
            }[kind]
            asset = MediaAsset(
                processing_job_id=job.id,
                asset_type=atype,
                storage_key=rel,
                mime_type="image/jpeg",
                file_size=path.stat().st_size,
            )
            db.add(asset)
            db.flush()
            assets[kind] = asset.id

        plate_conf = float(capture.get("plate_confidence") or 0.0)
        det = PlateDetection(
            vehicle_track_id=track.id,
            raw_ocr_text=None,
            normalized_plate_text=None,
            ocr_confidence=0.0,
            plate_detection_confidence=plate_conf,
            status=_plate_status(
                plate_conf,
                settings.high_confidence_threshold,
                settings.medium_confidence_threshold,
                settings.low_confidence_threshold,
            ),
            first_seen_seconds=float(capture.get("first_seen") or 0.0),
            last_seen_seconds=float(capture.get("last_seen") or 0.0),
            best_frame_number=int(capture.get("best_frame") or 0),
            consistency_score=1.0,
            full_frame_asset_id=assets.get("full_frame"),
            vehicle_crop_asset_id=assets.get("vehicle_crop"),
            plate_crop_asset_id=assets.get("plate_crop"),
        )
        db.add(det)
        db.flush()
        for obs in capture.get("observations") or []:
            db.add(
                Observation(
                    plate_detection_id=det.id,
                    frame_number=int(obs["frame_number"]),
                    timestamp_seconds=float(obs["timestamp"]),
                    raw_ocr_text=None,
                    normalized_plate_text=None,
                    ocr_confidence=0.0,
                    bounding_box=obs.get("bounding_box"),
                )
            )

    if annotated_path.exists():
        db.add(
            MediaAsset(
                processing_job_id=job.id,
                asset_type=AssetType.ANNOTATED_VIDEO.value,
                storage_key=annotated_rel,
                mime_type="video/mp4",
                file_size=annotated_path.stat().st_size,
            )
        )
    job.metrics = metrics
    job.vehicles_detected = len(vehicle_meta)
    job.plates_detected = len(best_by_track)
    db.flush()
