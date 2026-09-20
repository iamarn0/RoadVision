"""RoadVision ANPR worker package."""

from __future__ import annotations

import sys
from pathlib import Path

_here = Path(__file__).resolve()
_parents = _here.parents
_WORKER_ROOT = _parents[1]
_REPO_ROOT = _parents[3] if len(_parents) > 3 else _WORKER_ROOT
for _path in (str(_REPO_ROOT), str(_WORKER_ROOT)):
    if _path not in sys.path:
        sys.path.insert(0, _path)

APP_VERSION = "0.1.0"
