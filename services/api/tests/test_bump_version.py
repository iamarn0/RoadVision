"""Unit tests for scripts/bump_version.py."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "scripts" / "bump_version.py"


def _load_bump_module():
    spec = importlib.util.spec_from_file_location("bump_version", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_semver_bumps() -> None:
    bump = _load_bump_module()
    assert bump.next_version("0.1.0", "patch") == "0.1.1"
    assert bump.next_version("0.1.1", "minor") == "0.2.0"
    assert bump.next_version("0.9.0", "major") == "1.0.0"
    assert bump.next_version("1.5.3", "major") == "2.0.0"


def test_bump_writes_only_version_file(tmp_path: Path) -> None:
    bump = _load_bump_module()
    version_file = tmp_path / "VERSION"
    version_file.write_text("0.1.0\n", encoding="utf-8")
    assert bump.bump_version_file(version_file, "patch") == "0.1.1"
    assert version_file.read_text(encoding="utf-8") == "0.1.1\n"


def test_invalid_version_rejected() -> None:
    bump = _load_bump_module()
    with pytest.raises(ValueError):
        bump.next_version("v0.1.0", "patch")
