from app.api.media import media_content_type


def test_mp4_is_served_as_video_even_when_the_uploader_sent_no_type() -> None:
    assert media_content_type("upload.mp4", "application/octet-stream") == "video/mp4"
    assert media_content_type("upload.MP4", None) == "video/mp4"
    assert media_content_type("clip.mov", None) == "video/quicktime"
    assert media_content_type("clip.webm", "video/webm") == "video/webm"
