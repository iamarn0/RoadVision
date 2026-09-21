"""Turn uploads from other computers into a video this system can play and decode.

Phones, CCTV recorders, and other PCs often produce HEVC, AVI, MKV, variable-frame-rate,
or rotated files. Browsers and OpenCV both stall on those. A browser-safe H.264 MP4
(yuv420p, square pixels, moov atom at the front) is the format both can start immediately.
"""

from __future__ import annotations

import json
import logging
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger("roadvision.video")


class VideoNormalizeError(Exception):
    pass


@dataclass
class VideoProbe:
    codec: str | None
    pix_fmt: str | None
    width: int
    height: int
    fps: float | None
    frame_count: int | None
    duration: float | None
    rotation: int
    variable_frame_rate: bool


@dataclass
class PlayableVideo:
    path: Path
    replaced_path: Path | None = None
    width: int | None = None
    height: int | None = None
    fps: float | None = None
    frame_count: int | None = None
    duration: float | None = None
    codec: str | None = None


def ffmpeg_available() -> bool:
    return shutil.which("ffmpeg") is not None and shutil.which("ffprobe") is not None


def parse_rate(value: str | None) -> float | None:
    if not value or value in {"0/0", "N/A"}:
        return None
    try:
        if "/" in value:
            num, den = value.split("/", 1)
            den_f = float(den)
            if den_f == 0:
                return None
            return float(num) / den_f
        return float(value)
    except ValueError:
        return None


def is_faststart_mp4(path: Path) -> bool:
    """True when the moov atom comes before mdat, so playback can start without the whole file."""
    try:
        with path.open("rb") as handle:
            header = handle.read(12)
            if len(header) < 12 or header[4:8] != b"ftyp":
                return False
            handle.seek(0)
            scanned = 0
            limit = 32 * 1024 * 1024
            while scanned < limit:
                box = handle.read(8)
                if len(box) < 8:
                    return False
                size = int.from_bytes(box[:4], "big")
                kind = box[4:8]
                header_len = 8
                if size == 1:
                    ext = handle.read(8)
                    if len(ext) < 8:
                        return False
                    size = int.from_bytes(ext, "big")
                    header_len = 16
                elif size == 0:
                    return False
                if kind == b"moov":
                    return True
                if kind == b"mdat":
                    return False
                if size < header_len:
                    return False
                handle.seek(size - header_len, 1)
                scanned += size
    except OSError:
        return False
    return False


def _rotation(stream: dict) -> int:
    tags = stream.get("tags") or {}
    raw = tags.get("rotate")
    if raw is not None:
        try:
            return int(float(raw)) % 360
        except (TypeError, ValueError):
            pass
    for side in stream.get("side_data_list") or []:
        if "rotation" not in side:
            continue
        try:
            return int(side["rotation"]) % 360
        except (TypeError, ValueError):
            continue
    return 0


def _is_vfr(stream: dict) -> bool:
    avg = parse_rate(stream.get("avg_frame_rate"))
    rate = parse_rate(stream.get("r_frame_rate"))
    if not avg or not rate or avg <= 0:
        return False
    return rate > avg * 1.08


def probe_from_ffprobe(data: dict) -> VideoProbe:
    streams = data.get("streams") or []
    video = next((stream for stream in streams if stream.get("codec_type") == "video"), None)
    if not video:
        raise VideoNormalizeError("No video stream found")
    fps = parse_rate(video.get("avg_frame_rate")) or parse_rate(video.get("r_frame_rate"))
    frame_count = None
    raw_frames = video.get("nb_frames")
    if raw_frames not in (None, "N/A"):
        try:
            frame_count = int(raw_frames)
        except (TypeError, ValueError):
            frame_count = None
    duration = None
    raw_duration = video.get("duration") or (data.get("format") or {}).get("duration")
    if raw_duration not in (None, "N/A"):
        try:
            duration = float(raw_duration)
        except (TypeError, ValueError):
            duration = None
    if frame_count is None and duration and fps:
        frame_count = int(duration * fps)
    return VideoProbe(
        codec=(video.get("codec_name") or None),
        pix_fmt=(video.get("pix_fmt") or None),
        width=int(video.get("width") or 0),
        height=int(video.get("height") or 0),
        fps=fps,
        frame_count=frame_count,
        duration=duration,
        rotation=_rotation(video),
        variable_frame_rate=_is_vfr(video),
    )


def normalize_action(path: Path, probe: VideoProbe, faststart: bool) -> str:
    codec = (probe.codec or "").lower()
    h264 = codec in {"h264", "avc"}
    yuv420 = (probe.pix_fmt or "").lower() == "yuv420p"
    upright = probe.rotation % 360 == 0
    steady = not probe.variable_frame_rate
    if h264 and yuv420 and upright and steady and path.suffix.lower() == ".mp4" and faststart:
        return "skip"
    if h264 and yuv420 and upright and steady:
        return "remux"
    return "transcode"


def video_filter(probe: VideoProbe) -> str:
    parts: list[str] = []
    rotation = probe.rotation % 360
    if rotation == 90:
        parts.append("transpose=1")
    elif rotation == 180:
        parts.append("transpose=1,transpose=1")
    elif rotation == 270:
        parts.append("transpose=2")
    parts.append("scale=trunc(iw/2)*2:trunc(ih/2)*2")
    parts.append("setsar=1")
    return ",".join(parts)


def ffmpeg_command(action: str, src: Path, dest: Path, probe: VideoProbe) -> list[str]:
    base = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-i", str(src), "-map", "0:v:0", "-an"]
    if action == "remux":
        return [*base, "-c:v", "copy", "-movflags", "+faststart", str(dest)]
    return [
        *base,
        "-c:v",
        "libx264",
        "-pix_fmt",
        "yuv420p",
        "-profile:v",
        "high",
        "-preset",
        "veryfast",
        "-crf",
        "20",
        "-vf",
        video_filter(probe),
        "-vsync",
        "cfr",
        "-movflags",
        "+faststart",
        str(dest),
    ]


def output_path(src: Path) -> Path:
    if src.suffix.lower() == ".mp4":
        return src.with_name(f"{src.stem}.playable.mp4")
    return src.with_suffix(".mp4")


def _run(cmd: list[str]) -> None:
    proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if proc.returncode != 0:
        detail = (proc.stderr or proc.stdout or "ffmpeg failed").strip()
        raise VideoNormalizeError(detail[-800:])


def _probe_file(path: Path) -> VideoProbe:
    proc = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-print_format",
            "json",
            "-show_format",
            "-show_streams",
            str(path),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        detail = (proc.stderr or "ffprobe failed").strip()
        raise VideoNormalizeError(detail[-800:])
    try:
        data = json.loads(proc.stdout or "{}")
    except json.JSONDecodeError as exc:
        raise VideoNormalizeError("ffprobe returned invalid JSON") from exc
    return probe_from_ffprobe(data)


def ensure_playable_mp4(path: Path) -> PlayableVideo:
    """Return an H.264 MP4 OpenCV and the browser can start. Leaves the original if ffmpeg is unavailable."""
    if not path.is_file():
        raise VideoNormalizeError(f"Video file is missing: {path}")
    if not ffmpeg_available():
        logger.warning("ffmpeg is not installed; playing the original file as uploaded")
        return PlayableVideo(path=path)
    try:
        probe = _probe_file(path)
        action = normalize_action(path, probe, is_faststart_mp4(path))
    except VideoNormalizeError:
        logger.exception("could not inspect %s; using the original file", path.name)
        return PlayableVideo(path=path)
    if action == "skip":
        return PlayableVideo(path=path, codec=probe.codec, width=probe.width, height=probe.height, fps=probe.fps)
    dest = output_path(path)
    if dest.exists():
        dest.unlink()
    logger.info("normalizing %s (%s %s) via %s", path.name, probe.codec, probe.pix_fmt, action)
    try:
        _run(ffmpeg_command(action, path, dest, probe))
        prepared = _probe_file(dest)
    except VideoNormalizeError:
        logger.exception("could not normalize %s; using the original file", path.name)
        if dest.exists():
            dest.unlink()
        return PlayableVideo(path=path)
    if dest.stat().st_size <= 0:
        dest.unlink(missing_ok=True)
        return PlayableVideo(path=path)
    return PlayableVideo(
        path=dest,
        replaced_path=path,
        width=prepared.width or probe.width,
        height=prepared.height or probe.height,
        fps=prepared.fps or probe.fps,
        frame_count=prepared.frame_count or probe.frame_count,
        duration=prepared.duration or probe.duration,
        codec="h264",
    )
