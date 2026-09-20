"""RoadVision API package."""

from __future__ import annotations

import sys
from pathlib import Path

# Monorepo: services/api/app/__init__.py → repo root is parents[3].
# Docker: /app/app/__init__.py → project root is parents[1].
_here = Path(__file__).resolve()
_parents = _here.parents
_API_ROOT = _parents[1]
_REPO_ROOT = _parents[3] if len(_parents) > 3 else _API_ROOT
for _path in (str(_REPO_ROOT), str(_API_ROOT)):
    if _path not in sys.path:
        sys.path.insert(0, _path)

APP_VERSION = "0.1.0"
