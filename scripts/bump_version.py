"""Bump the RoadVision product version in the root VERSION file."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
VERSION_FILE = REPO_ROOT / "VERSION"
SEMVER = re.compile(r"^(\d+)\.(\d+)\.(\d+)$")


def next_version(current: str, bump: str) -> str:
    match = SEMVER.match(current.strip())
    if not match:
        raise ValueError(f"VERSION must be MAJOR.MINOR.PATCH, got {current!r}")
    major, minor, patch = (int(part) for part in match.groups())
    if bump == "major":
        return f"{major + 1}.0.0"
    if bump == "minor":
        return f"{major}.{minor + 1}.0"
    if bump == "patch":
        return f"{major}.{minor}.{patch + 1}"
    raise ValueError(f"Unknown bump type: {bump}")


def bump_version_file(path: Path, bump: str) -> str:
    current = path.read_text(encoding="utf-8").strip().splitlines()[0].strip()
    updated = next_version(current, bump)
    path.write_text(f"{updated}\n", encoding="utf-8")
    return updated


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Bump RoadVision VERSION (SemVer).")
    parser.add_argument("bump", choices=("patch", "minor", "major"))
    args = parser.parse_args(argv)
    try:
        updated = bump_version_file(VERSION_FILE, args.bump)
    except (OSError, ValueError) as exc:
        print(exc, file=sys.stderr)
        return 1
    print(updated)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
