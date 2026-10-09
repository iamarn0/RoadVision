"""Turn uploads from other computers into a video this system can play and decode.

Phones, CCTV recorders, and other PCs often produce HEVC, AVI, MKV, variable-frame-rate,
or rotated files. Browsers and OpenCV both stall on those. A browser-safe H.264 MP4
(yuv420p, square pixels, moov atom at the front) is the format both can start immediately.
"""

from __future__ import annotations

import json
import logging
import re
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


def ffmpeg_exe() -> str | None:
    """ffmpeg on PATH, or the binary shipped with imageio-ffmpeg."""
    found = shutil.which("ffmpeg")
    if found:
        return found
    try:
        import imageio_ffmpeg
    except ImportError:
        return None
    try:
        exe = imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return None
    return exe if exe and Path(exe).is_file() else None


def ffprobe_exe() -> str | None:
    found = shutil.which("ffprobe")
    if found:
        return found
    ffmpeg = ffmpeg_exe()
    if not ffmpeg:
        return None
    name = "ffprobe.exe" if Path(ffmpeg).suffix.lower() == ".exe" else "ffprobe"
    sibling = Path(ffmpeg).with_name(name)
    return str(sibling) if sibling.is_file() else None


def ffmpeg_available() -> bool:
    return ffmpeg_exe() is not None


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
    base = [ffmpeg_exe() or "ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-i", str(src), "-map", "0:v:0", "-an"]
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


def probe_from_ffmpeg_banner(text: str) -> VideoProbe:
    """Read codec and size from `ffmpeg -i` when ffprobe is not installed."""
    duration = None
    clock = re.search(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)", text)
    if clock:
        duration = int(clock.group(1)) * 3600 + int(clock.group(2)) * 60 + float(clock.group(3))
    stream = next((line for line in text.splitlines() if "Video:" in line), None)
    if not stream:
        raise VideoNormalizeError("No video stream found")
    codec_match = re.search(r"Video:\s*([A-Za-z0-9_]+)", stream)
    pix_match = re.search(r"\b(yuv[0-9a-z]+|nv12|nv21|rgb24|bgr24|gray)\b", stream, re.IGNORECASE)
    size_match = re.search(r"(\d{2,})x(\d{2,})", stream)
    fps_match = re.search(r"(\d+(?:\.\d+)?)\s+fps", stream)
    if not codec_match or not size_match:
        raise VideoNormalizeError("Could not read the video stream")
    fps = float(fps_match.group(1)) if fps_match else None
    frame_count = int(duration * fps) if duration and fps else None
    rotation = 0
    turned = re.search(r"rotation of (-?\d+(?:\.\d+)?)\s+degrees", text)
    if turned:
        rotation = int(float(turned.group(1))) % 360
    return VideoProbe(
        codec=codec_match.group(1),
        pix_fmt=pix_match.group(1) if pix_match else None,
        width=int(size_match.group(1)),
        height=int(size_match.group(2)),
        fps=fps,
        frame_count=frame_count,
        duration=duration,
        rotation=rotation,
        variable_frame_rate=False,
    )


def _probe_file(path: Path) -> VideoProbe:
    probe = ffprobe_exe()
    if probe:
        proc = subprocess.run(
            [
                probe,
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
    ffmpeg = ffmpeg_exe()
    if not ffmpeg:
        raise VideoNormalizeError("ffmpeg is not installed")
    proc = subprocess.run(
        [ffmpeg, "-hide_banner", "-i", str(path)],
        capture_output=True,
        text=True,
        check=False,
    )
    return probe_from_ffmpeg_banner(proc.stderr or proc.stdout or "")


def ensure_playable_mp4(path: Path) -> PlayableVideo:
    """Return an H.264 MP4 OpenCV and the browser can start. Leaves the original if ffmpeg is unavailable."""
    if not path.is_file():
        raise VideoNormalizeError(f"Video file is missing: {path}")
    if not ffmpeg_available():
        logger.warning("ffmpeg is not installed; the browser cannot play this video")
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


def playable_copy(path: Path) -> Path:
    """H.264 faststart file for the browser. Reuses a cached copy beside the source."""
    if not path.is_file() or path.suffix.lower() not in {".mp4", ".m4v", ".mov", ".mkv", ".avi", ".webm"}:
        return path
    dest = output_path(path)
    try:
        source_mtime = path.stat().st_mtime
        if dest.is_file() and dest.stat().st_size > 0 and dest.stat().st_mtime >= source_mtime:
            return dest
    except OSError:
        return path
    prepared = ensure_playable_mp4(path)
    return prepared.path if prepared.path.is_file() else path
