from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator, Optional

import numpy as np


@dataclass
class VideoMetadata:
    width: int
    height: int
    fps: float
    frame_count: int
    duration: Optional[float]
    codec: Optional[str]
    source_id: str
    source_type: str = "uploaded_video"


@dataclass
class Frame:
    index: int
    timestamp: float
    image: np.ndarray


class VideoSource(ABC):
    @abstractmethod
    def open(self) -> VideoMetadata:
        ...

    @abstractmethod
    def read(self) -> Optional[Frame]:
        ...

    def frames(self) -> Iterator[Frame]:
        while True:
            frame = self.read()
            if frame is None:
                break
            yield frame

    @abstractmethod
    def close(self) -> None:
        ...

    def __enter__(self) -> "VideoSource":
        self.open()
        return self

    def __exit__(self, *args) -> None:
        self.close()


class UploadedFileSource(VideoSource):
    def __init__(self, path: str | Path, source_id: str | None = None) -> None:
        self.path = Path(path)
        self.source_id = source_id or self.path.name
        self._cap = None
        self._meta: Optional[VideoMetadata] = None
        self._index = 0

    def open(self) -> VideoMetadata:
        import cv2

        if not self.path.exists():
            raise FileNotFoundError(self.path)
        self._cap = cv2.VideoCapture(str(self.path))
        if not self._cap.isOpened():
            raise ValueError(f"Unable to open video: {self.path}")
        width = int(self._cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
        height = int(self._cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
        fps = float(self._cap.get(cv2.CAP_PROP_FPS) or 0) or 25.0
        frame_count = int(self._cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        fourcc = int(self._cap.get(cv2.CAP_PROP_FOURCC) or 0)
        codec = "".join([chr((fourcc >> 8 * i) & 0xFF) for i in range(4)]).strip() or None
        duration = frame_count / fps if fps else None
        self._meta = VideoMetadata(
            width=width,
            height=height,
            fps=fps,
            frame_count=frame_count,
            duration=duration,
            codec=codec,
            source_id=self.source_id,
            source_type="uploaded_video",
        )
        self._index = 0
        return self._meta

    def read(self) -> Optional[Frame]:
        if self._cap is None:
            raise RuntimeError("VideoSource is not open")
        ok, image = self._cap.read()
        if not ok or image is None:
            return None
        fps = self._meta.fps if self._meta else 25.0
        frame = Frame(index=self._index, timestamp=self._index / fps if fps else 0.0, image=image)
        self._index += 1
        return frame

    def grab(self, count: int) -> int:
        """Advance without decoding. Used to sample looks instead of every source frame."""
        if self._cap is None:
            raise RuntimeError("VideoSource is not open")
        grabbed = 0
        for _ in range(max(0, int(count))):
            if not self._cap.grab():
                break
            self._index += 1
            grabbed += 1
        return grabbed

    def close(self) -> None:
        if self._cap is not None:
            self._cap.release()
            self._cap = None


class RTSPSource(VideoSource):
    def open(self) -> VideoMetadata:
        raise NotImplementedError("RTSP is not implemented in v0.1.0")

    def read(self) -> Optional[Frame]:
        raise NotImplementedError("RTSP is not implemented in v0.1.0")

    def close(self) -> None:
        return None


class WebcamSource(VideoSource):
    def open(self) -> VideoMetadata:
        raise NotImplementedError("Webcam is not implemented in v0.1.0")

    def read(self) -> Optional[Frame]:
        raise NotImplementedError("Webcam is not implemented in v0.1.0")

    def close(self) -> None:
        return None


class IPCameraSource(VideoSource):
    def open(self) -> VideoMetadata:
        raise NotImplementedError("IP camera is not implemented in v0.1.0")

    def read(self) -> Optional[Frame]:
        raise NotImplementedError("IP camera is not implemented in v0.1.0")

    def close(self) -> None:
        return None
