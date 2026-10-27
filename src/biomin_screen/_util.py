"""Helpers shared by the command line and the table and figure builders."""
import json
import os
from datetime import datetime, timezone
from pathlib import Path

_PKG_ROOT = Path(__file__).resolve().parents[2]
ROOT_ENV = "BIOMIN_SCREEN_ROOT"
_MARKER = "pyproject.toml"


def repo_root(start=None):
    """The repository root: $BIOMIN_SCREEN_ROOT, else the nearest parent of `start` (or of the working
    directory) that holds pyproject.toml and src/biomin_screen, else the directory that holds this checkout."""
    if os.environ.get(ROOT_ENV):
        return Path(os.environ[ROOT_ENV]).resolve()
    here = Path(start).resolve() if start else Path.cwd().resolve()
    for p in [here, *here.parents]:
        if (p / _MARKER).is_file() and (p / "src" / "biomin_screen").is_dir():
            return p
    return _PKG_ROOT


def read_json(path):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def utc_now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
