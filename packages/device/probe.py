from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Optional


class DeviceError(Exception):
    def __init__(self, error_code: str, message: str) -> None:
        self.error_code = error_code
        self.message = message
        super().__init__(message)


@dataclass
class DeviceSelection:
    requested: str
    device: str
    cuda_available: bool
    gpu_name: Optional[str]
    total_memory_mb: Optional[float]
    available_memory_mb: Optional[float]
    torch_version: Optional[str]
    cuda_version: Optional[str]
    fp16_enabled: bool
    status: str
    fallback_reason: Optional[str] = None
    driver_info: Optional[str] = None

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def _torch_probe() -> dict[str, Any]:
    try:
        import torch
    except Exception:
        return {
            "torch_available": False,
            "cuda_available": False,
            "torch_version": None,
            "cuda_version": None,
            "gpu_name": None,
            "total_memory_mb": None,
            "available_memory_mb": None,
            "device_count": 0,
        }

    cuda_available = bool(torch.cuda.is_available())
    gpu_name = None
    total_memory_mb = None
    available_memory_mb = None
    if cuda_available:
        index = 0
        gpu_name = torch.cuda.get_device_name(index)
        props = torch.cuda.get_device_properties(index)
        total_memory_mb = round(props.total_memory / (1024 * 1024), 1)
        free, total = torch.cuda.mem_get_info(index)
        available_memory_mb = round(free / (1024 * 1024), 1)
    return {
        "torch_available": True,
        "cuda_available": cuda_available,
        "torch_version": torch.__version__,
        "cuda_version": getattr(torch.version, "cuda", None),
        "gpu_name": gpu_name,
        "total_memory_mb": total_memory_mb,
        "available_memory_mb": available_memory_mb,
        "device_count": torch.cuda.device_count() if cuda_available else 0,
    }


def select_device(
    processing_device: str = "auto",
    cuda_device: int = 0,
    use_half_precision: bool = True,
    auto_fallback_to_cpu: bool = False,
) -> DeviceSelection:
    mode = (processing_device or "auto").lower().strip()
    probe = _torch_probe()
    cuda_available = probe["cuda_available"]
    fp16 = False
    fallback_reason = None

    if mode == "cpu":
        device = "cpu"
        status = "cpu"
    elif mode == "cuda":
        if not cuda_available:
            raise DeviceError(
                "CUDA_UNAVAILABLE",
                "PROCESSING_DEVICE=cuda but CUDA is not available. Install a matching PyTorch CUDA wheel or use auto/cpu.",
            )
        device = f"cuda:{cuda_device}"
        status = "ready"
        fp16 = bool(use_half_precision)
    elif mode == "auto":
        if cuda_available:
            device = f"cuda:{cuda_device}"
            status = "ready"
            fp16 = bool(use_half_precision)
        else:
            device = "cpu"
            status = "cpu_fallback"
            fallback_reason = "CUDA_UNAVAILABLE"
    else:
        raise DeviceError("VALIDATION_ERROR", f"Unknown PROCESSING_DEVICE: {processing_device}")

    if device.startswith("cuda") and not cuda_available and auto_fallback_to_cpu:
        device = "cpu"
        status = "cpu_fallback"
        fallback_reason = "CUDA_UNAVAILABLE"
        fp16 = False

    return DeviceSelection(
        requested=mode,
        device=device,
        cuda_available=cuda_available,
        gpu_name=probe["gpu_name"] if device.startswith("cuda") else probe["gpu_name"],
        total_memory_mb=probe["total_memory_mb"],
        available_memory_mb=probe["available_memory_mb"],
        torch_version=probe["torch_version"],
        cuda_version=probe["cuda_version"],
        fp16_enabled=fp16 and device.startswith("cuda"),
        status=status if cuda_available or mode != "cuda" else "configuration_error",
        fallback_reason=fallback_reason,
    )


def probe_gpu(
    processing_device: str = "auto",
    cuda_device: int = 0,
    use_half_precision: bool = True,
) -> dict[str, Any]:
    try:
        selection = select_device(processing_device, cuda_device, use_half_precision)
        payload = selection.as_dict()
        payload["message"] = None
        return payload
    except DeviceError as exc:
        probe = _torch_probe()
        return {
            "requested": processing_device,
            "device": None,
            "cuda_available": probe["cuda_available"],
            "gpu_name": probe["gpu_name"],
            "total_memory_mb": probe["total_memory_mb"],
            "available_memory_mb": probe["available_memory_mb"],
            "torch_version": probe["torch_version"],
            "cuda_version": probe["cuda_version"],
            "fp16_enabled": False,
            "status": "configuration_error",
            "fallback_reason": exc.error_code,
            "message": exc.message,
            "error_code": exc.error_code,
        }
