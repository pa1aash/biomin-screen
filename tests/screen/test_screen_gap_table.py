"""The gap-resolution table covers every unsourced input with one allowed treatment ."""
from pathlib import Path

import pytest
import yaml

from biomin_screen.screen import gaps

ROOT = Path(__file__).resolve().parents[2]
TABLE = ROOT / gaps.GAP_TABLE
PARAMS = ROOT / "data" / "params.yaml"


@pytest.fixture(scope="module")
def table():
    return gaps.load(TABLE)


@pytest.fixture(scope="module")
def params():
    return yaml.safe_load(PARAMS.read_text(encoding="utf-8"))


def test_every_unsourced_key_has_a_treatment(table, params):
    """Keys of data/params.yaml for the phosphate screen are accounted for by the phosphate
    skeleton (configs/gap_resolution_ph.yaml), not by this carbonate table."""
    ph = gaps.covered_ph(gaps.load_ph(ROOT / gaps.PH_TABLE))
    assert [p for p in gaps.check(table, params) if not ph(p.split(":")[0])] == []


def test_table_names_its_treatments(table):
    assert table["version"] == 1
    assert {"gaps", "controls", "admissibility"} <= set(table)


def test_analog_keys_are_flagged_table_keys(table, params):
    for gap, key in gaps.analog_keys(table).items():
        assert key in params["params"], gap


def test_an_incomplete_table_is_reported(table, params):
    cut = dict(table, gaps={k: v for k, v in table["gaps"].items() if k != "patch_area"})
    assert any(p.startswith("patch_area") for p in gaps.check(cut, params))


def test_an_unknown_treatment_is_reported(table, params):
    bad = dict(table, gaps=dict(table["gaps"], patch_area={"treatment": "point value"}))
    assert any("not one of" in p for p in gaps.check(bad, params))


def test_ignorance_bounds_name_their_authority(table, params):
    bad = dict(table, gaps=dict(table["gaps"], gamma_op=dict(table["gaps"]["gamma_op"], bound_from="judgement")))
    assert any("ignorance_priors.md" in p for p in gaps.check(bad, params))
