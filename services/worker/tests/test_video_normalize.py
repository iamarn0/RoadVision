from pathlib import Path

from packages.video_normalize import (
    VideoProbe,
    ensure_playable_mp4,
    ffmpeg_command,
    is_faststart_mp4,
    normalize_action,
    probe_from_ffmpeg_banner,
    probe_from_ffprobe,
    video_filter,
)


def _probe(**overrides) -> VideoProbe:
    data = dict(
        codec="h264",
        pix_fmt="yuv420p",
        width=1280,
        height=720,
        fps=25.0,
        frame_count=100,
        duration=4.0,
        rotation=0,
        variable_frame_rate=False,
    )
    data.update(overrides)
    return VideoProbe(**data)


def _box(kind: bytes, payload: bytes = b"") -> bytes:
    return (8 + len(payload)).to_bytes(4, "big") + kind + payload


def test_faststart_requires_moov_before_mdat(tmp_path: Path) -> None:
    ftyp = _box(b"ftyp", b"isom\x00\x00\x00\x00")
    moov = _box(b"moov")
    mdat = _box(b"mdat", b"\x00\x00")
    ready = tmp_path / "ready.mp4"
    ready.write_bytes(ftyp + moov + mdat)
    late = tmp_path / "late.mp4"
    late.write_bytes(ftyp + mdat + moov)
    assert is_faststart_mp4(ready) is True
    assert is_faststart_mp4(late) is False
    assert is_faststart_mp4(tmp_path / "clip.avi") is False


def test_phone_and_cctv_files_are_transcoded() -> None:
    assert normalize_action(Path("clip.mp4"), _probe(codec="hevc"), True) == "transcode"
    assert normalize_action(Path("clip.avi"), _probe(), False) == "remux"
    assert normalize_action(Path("clip.mov"), _probe(rotation=90), False) == "transcode"
    assert normalize_action(Path("clip.mp4"), _probe(variable_frame_rate=True), True) == "transcode"
    assert normalize_action(Path("clip.mp4"), _probe(pix_fmt="yuv422p"), True) == "transcode"
    assert normalize_action(Path("clip.mp4"), _probe(), False) == "remux"
    assert normalize_action(Path("clip.mp4"), _probe(), True) == "skip"


def test_probe_reads_rotation_and_vfr() -> None:
    probe = probe_from_ffprobe(
        {
            "streams": [
                {
                    "codec_type": "video",
                    "codec_name": "hevc",
                    "pix_fmt": "yuv420p",
                    "width": 1920,
                    "height": 1080,
                    "avg_frame_rate": "30/1",
                    "r_frame_rate": "120/1",
                    "nb_frames": "60",
                    "duration": "2.0",
                    "side_data_list": [{"rotation": -90}],
                }
            ]
        }
    )
    assert probe.codec == "hevc"
    assert probe.rotation == 270
    assert probe.variable_frame_rate is True
    assert probe.frame_count == 60


def test_transcode_command_bakes_rotation_and_drops_audio() -> None:
    probe = _probe(rotation=90)
    cmd = ffmpeg_command("transcode", Path("in.mov"), Path("out.mp4"), probe)
    assert "libx264" in cmd
    assert "yuv420p" in cmd
    assert "+faststart" in cmd
    assert "-an" in cmd
    assert "transpose=1" in video_filter(probe)
    remux = ffmpeg_command("remux", Path("in.mp4"), Path("out.mp4"), _probe())
    assert "copy" in remux
    assert "libx264" not in remux


def test_ffmpeg_banner_reads_mpeg4_stream() -> None:
    probe = probe_from_ffmpeg_banner(
        "Duration: 00:00:12.50, start: 0.000000, bitrate: 800 kb/s\n"
        "Stream #0:0: Video: mpeg4 (Simple Profile) (mp4v / 0x7634706D), yuv420p, 960x540, 508 kb/s, 8 fps, 8 tbr\n"
    )
    assert probe.codec == "mpeg4"
    assert probe.pix_fmt == "yuv420p"
    assert (probe.width, probe.height) == (960, 540)
    assert probe.fps == 8.0
    assert probe.duration == 12.5
    assert normalize_action(Path("job.mp4"), probe, False) == "transcode"


def test_missing_ffmpeg_keeps_the_uploaded_file(tmp_path: Path, monkeypatch) -> None:
    src = tmp_path / "from-other-pc.mov"
    src.write_bytes(b"camera")
    monkeypatch.setattr("packages.video_normalize.ffmpeg_available", lambda: False)
    result = ensure_playable_mp4(src)
    assert result.path == src
    assert result.replaced_path is None
    assert src.is_file()
