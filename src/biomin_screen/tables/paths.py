"""Locations of the generated tables."""
from pathlib import Path


def generated(root):
    return Path(root) / "results" / "tables"
