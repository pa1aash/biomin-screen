"""Helpers shared by the table tests."""
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]


def write(path, text):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path
