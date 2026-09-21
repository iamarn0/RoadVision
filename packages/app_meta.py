"""RoadVision product version metadata.

Source of truth: the repository root VERSION file (MAJOR.MINOR.PATCH).
"""

from __future__ import annotations

import os
import re
from pathlib import Path

_SEMVER = re.compile(r"^\d+\.\d+\.\d+$")


def _version_candidates() -> list[Path]:
    here = Path(__file__).resolve()
    repo_root = here.parents[1]
    return [
        Path("/app/VERSION"),
        repo_root / "VERSION",
        Path.cwd() / "VERSION",
        Path("VERSION"),
    ]


def read_app_version() -> str:
    seen: set[Path] = set()
    for candidate in _version_candidates():
        try:
            resolved = candidate.resolve()
        except OSError:
            continue
        if resolved in seen or not candidate.is_file():
            continue
        seen.add(resolved)
        text = candidate.read_text(encoding="utf-8").strip()
        if not text:
            continue
        version = text.splitlines()[0].strip()
        if _SEMVER.match(version):
            return version
    return "unknown"


def read_git_commit() -> str:
    raw = os.environ.get("GIT_COMMIT", "").strip()
    if not raw or raw.lower() in {"unknown", "none", "null"}:
        return "unknown"
    return raw[:12]
