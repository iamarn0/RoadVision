from packages.device.probe import DeviceError, select_device


def test_cpu_mode_always_cpu() -> None:
    selection = select_device("cpu", 0, True, False)
    assert selection.device == "cpu"
    assert selection.fp16_enabled is False


def test_cuda_mode_fails_when_unavailable() -> None:
    try:
        import torch

        if torch.cuda.is_available():
            selection = select_device("cuda", 0, True, False)
            assert selection.device.startswith("cuda")
            return
    except Exception:
        pass
    try:
        select_device("cuda", 0, True, False)
        raised = False
    except DeviceError as exc:
        raised = True
        assert exc.error_code == "CUDA_UNAVAILABLE"
    assert raised
