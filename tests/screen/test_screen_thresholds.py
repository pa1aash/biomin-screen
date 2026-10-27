"""Thresholds copy: configs/thresholds.yaml equals the block of data/thresholds.md."""
from pathlib import Path

import pytest

from biomin_screen.screen import provenance_guard
from biomin_screen.screen import thresholds as thr

ROOT = Path(__file__).resolve().parents[2]
SHA = "a" * 40
HEADER = "# Machine-readable copy of the fenced `thresholds` block of data/thresholds.md.\n"
SOURCE = """# Thresholds

Prose that is not copied.

```yaml
not: this one
```

```thresholds
links:
  nucleate:
    quantity: f_theta
    edges: [0.5, 0.8]
```

More prose.
"""


def _copy(source, sha=None):
    """A thresholds.yaml text for a source: a comment header (with the optional source line) and the block."""
    return HEADER + ("# source-sha: %s\n" % sha if sha else "") + thr.extract_block(source)


def test_block_is_extracted_and_copied_verbatim_under_a_header():
    text = _copy(SOURCE, SHA)
    sha, body = thr.split_copy(text)
    assert sha == SHA
    assert body == "links:\n  nucleate:\n    quantity: f_theta\n    edges: [0.5, 0.8]\n"
    assert thr.equal(SOURCE, text)
    assert thr.split_copy(_copy(SOURCE))[0] is None and thr.equal(SOURCE, _copy(SOURCE))


@pytest.mark.parametrize("source", [SOURCE.replace("```thresholds", "```yaml"),
                                    SOURCE + "\n```thresholds\nx: 1\n```\n"])
def test_source_must_hold_exactly_one_thresholds_block(source):
    with pytest.raises(thr.ThresholdsMismatch, match="exactly one"):
        thr.extract_block(source)


def test_an_edited_copy_is_detected():
    text = _copy(SOURCE, SHA).replace("0.8", "0.85")
    with pytest.raises(thr.ThresholdsMismatch):
        thr.equal(SOURCE, text)


def test_loader_returns_the_rule_and_its_source(tmp_path):
    p = tmp_path / "thresholds.yaml"
    p.write_text(_copy(SOURCE, SHA), encoding="utf-8")
    t = thr.load_thresholds(p)
    assert t["source_sha"] == SHA and t["rule"]["links"]["nucleate"]["edges"] == [0.5, 0.8]
    with pytest.raises(thr.ThresholdsNotFixed):
        thr.load_thresholds(tmp_path / "missing.yaml")


def test_committed_copy_equals_thresholds_document():
    text = (ROOT / thr.COPY).read_text(encoding="utf-8")
    assert thr.equal((ROOT / thr.THEORY).read_text(encoding="utf-8"), text)
    rule = thr.load_thresholds(ROOT / thr.COPY)["rule"]
    assert rule["version"] == provenance_guard.THRESHOLDS_BLOCK_VERSION
