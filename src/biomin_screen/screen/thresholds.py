"""Thresholds and the decision rule of the screen.

data/thresholds.md is the threshold authority. Its fenced ``thresholds`` block is copied
verbatim into configs/thresholds.yaml under a comment header; equal() checks the two agree (as
parsed YAML and as text). A change to either file is made in both.

The per-link evaluators and the study-level decision rule (biomin_screen.screen.decision)
implement the rule as written in that block; load_thresholds raises ThresholdsNotFixed
while the copy is missing, so no verdict can come from an unfixed rule.
"""
import re
from pathlib import Path

import yaml

THEORY = Path("data") / "thresholds.md"
COPY = Path("configs") / "thresholds.yaml"
_FENCE = re.compile(r"^(?P<fence>```+|~~~+)[ \t]*(?P<info>[^\n`]*)\n(?P<body>.*?)^(?P=fence)[ \t]*$",
                    re.MULTILINE | re.DOTALL)
_SHA = re.compile(r"^# source-sha: ([0-9a-f]{40})$", re.MULTILINE)


class ThresholdsNotFixed(RuntimeError):
    """Raised by every evaluator call until configs/thresholds.yaml exists."""


class ThresholdsMismatch(ValueError):
    """The copy and data/thresholds.md disagree, or the source has no unique block."""


_MESSAGE = "per-link thresholds are not fixed: configs/thresholds.yaml, the copy of data/thresholds.md, is missing"


def extract_block(markdown):
    """Text of the single fenced code block whose info string names ``thresholds``."""
    blocks = [m.group("body") for m in _FENCE.finditer(markdown)
              if "thresholds" in m.group("info").replace(",", " ").split()]
    if len(blocks) != 1:
        raise ThresholdsMismatch("data/thresholds.md must hold exactly one fenced `thresholds` block, found %d"
                                 % len(blocks))
    return blocks[0]


def split_copy(text):
    """(source sha or None, block text) of a thresholds.yaml copy: the comment header is dropped."""
    m = _SHA.search(text)
    lines = text.splitlines(keepends=True)
    i = 0
    while i < len(lines) and lines[i].startswith("#"):
        i += 1
    return (m.group(1) if m else None), "".join(lines[i:])


def equal(markdown, copy_text):
    """Raise ThresholdsMismatch unless the copy's block equals the source block (text and YAML)."""
    block = extract_block(markdown)
    _, body = split_copy(copy_text)
    if body != block:
        raise ThresholdsMismatch("thresholds.yaml text differs from the fenced block of data/thresholds.md")
    if yaml.safe_load(body) != yaml.safe_load(block):
        raise ThresholdsMismatch("thresholds.yaml parses differently from the fenced block")
    return True


def load_thresholds(path=COPY):
    """Parsed thresholds block: {"source_sha": ..., "rule": {...}} (source_sha is None without a header line)."""
    path = Path(path)
    if not path.exists():
        raise ThresholdsNotFixed(_MESSAGE)
    text = path.read_text(encoding="utf-8")
    sha, body = split_copy(text)
    return {"source_sha": sha, "rule": yaml.safe_load(body)}
