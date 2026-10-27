"""The generated break-even table of the saturated-sink exclusions: pinned input, every row.

Tests that read the stored table in results/tables compare with a file that is regenerated from the current code.
"""
import csv
import json
import shutil

import pytest

from biomin_screen.tables import breakeven_table as bt
from biomin_screen.tables import paths
from paper_helpers import REPO

GEN = paths.generated(REPO)


def _csv_rows():
    with (REPO / bt.INPUTS["breakeven"]).open(encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def test_committed_outputs_are_a_fresh_generation():
    assert bt.check(REPO) == []


def test_the_input_is_the_recorded_file():
    assert bt.sha256(REPO / bt.INPUTS["breakeven"]) == bt.BREAKEVEN_SHA256
    recorded = json.loads((GEN / bt.OUT_JSON).read_text(encoding="utf-8"))["inputs"]
    assert recorded[bt.INPUTS["breakeven"]] == bt.BREAKEVEN_SHA256


def test_a_changed_input_is_refused(tmp_path):
    root = tmp_path / "r"
    for rel in bt.INPUTS.values():
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(REPO / rel, root / rel)
    p = root / bt.INPUTS["breakeven"]
    p.write_text(p.read_text(encoding="utf-8").replace("3.73408", "3.73409"), encoding="utf-8")
    with pytest.raises(bt.BreakevenTableError, match="recorded"):
        bt.read_inputs(root)


def test_every_row_of_the_file_is_in_the_table_with_its_values():
    """An independent read of the CSV against the numbers the table writes, row by row."""
    rows = _csv_rows()
    assert len(rows) == 26
    numbers = json.loads((GEN / bt.OUT_JSON).read_text(encoding="utf-8"))["numbers"]["breakeven"]
    docs = bt.read_inputs(REPO)[0]
    for r in rows:
        stem = bt.PHASES[r["phase"]][1]
        edge = bt._edge_stem(r["class"], float(r["E_c"]), docs["edges"])
        assert numbers["cutoff"][edge] == float(r["E_c"])
        node = numbers[stem][edge]
        assert node["headroom_V"] == float(r["headroom_V"]), r
        if r["r_star"] == bt.NOT_EXCLUDED:
            assert "r_star" not in node and float(r["headroom_V"]) < 0
        else:
            assert node["r_star"] == float(r["r_star"]), r


def test_the_one_negative_headroom_row_keeps_its_words():
    rows = [r for r in _csv_rows() if r["r_star"] == bt.NOT_EXCLUDED]
    assert [(r["phase"], r["E_c"]) for r in rows] == [("brushite", "4.4")]


def test_every_phase_of_the_file_has_a_table_entry():
    assert {r["phase"] for r in _csv_rows()} <= set(bt.PHASES)


@pytest.mark.skip(reason="checks the table setting and the reading sentences in the manuscript sections, which are not shipped")
def test_results_and_si_set_the_table_and_state_the_reading():
    raise AssertionError("not run")
