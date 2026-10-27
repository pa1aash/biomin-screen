"""The generated input tables: parameter table, benchmark table, reaction, database and conversion tables.

Tests that read the stored tables in results/tables compare with files that are regenerated from the current code.
"""
import csv
import re

import pytest
import yaml

from biomin_screen.tables import input_tables as it
from biomin_screen.tables import paths
from paper_helpers import REPO

GEN = paths.generated(REPO)


def _rows():
    with (GEN / it.OUT_CSV).open(encoding="utf-8", newline="") as fh:
        return list(csv.reader(fh))[1:]


def _table(name):
    return [r for r in _rows() if r[0] == name]


def test_committed_outputs_are_a_fresh_generation():
    assert it.check(REPO) == []


def test_the_tables_are_plain_text():
    for r in _rows():
        assert not re.search(r"\\|\$", " ".join(r)), r


def test_the_parameter_table_carries_the_dissolution_inputs_with_cited_sources():
    keys = [k for _t, members in it.PARAM_GROUPS for _j, k, _s in members]
    rows = _table("parameters")
    assert len(keys) == 17 and len(rows) == len(keys)
    for r in rows:
        assert len(r) == 8 and (r[7] == "--" or re.match(r"10\.\d{4,9}/", r[7].split(", ")[0])), r


def test_the_benchmark_table_names_the_governing_reaction_or_why_there_is_none():
    rows = _table("benchmark")
    assert rows and all("->" in r[4] or r[4].startswith("undetermined:") for r in rows)
    names = [r[2] for r in rows]
    assert "calcium carbonate (control)" in names and not [n for n in names if "(comparator)" in n]


def test_speciation_follows_the_specified_acid_constants():
    p = yaml.safe_load((REPO / it.INPUTS["params"]).read_text(encoding="utf-8"))["params"]
    k2 = p["pk2_carbonic"]["value"]
    a3 = p["pka3_h3po4"]["value"]
    lo = p["ph_slurry"]["range"]["min"]
    nums = {n.name: n.value for n in it.speciation(it.read_inputs(REPO)[0])}
    # the leading term alone: CO3^2- / (CO3^2- + HCO3-) and PO4^3- / (PO4^3- + HPO4^2-)
    assert abs(nums["NumSpecCarbonateLow"] - 100 / (1 + 10 ** (k2 - lo))) < 0.1
    assert abs(nums["NumSpecPhosphateLow"] - 100 / (1 + 10 ** (a3 - lo))) < 0.01
    assert nums["NumSpecCarbonateLow"] > nums["NumSpecPhosphateLow"]
    assert nums["NumSpecPhosphateMid"] > 100 * nums["NumSpecPhosphateLow"] / 100


def test_carbonate_rows_read_the_ksp_keys_that_k2_binds():
    """Every carbonate row of the parameter table reads the K_sp key that the dissolution test binds in screen.yaml,
    and the generator refuses a row that does not."""
    import copy

    from biomin_screen.screen import k2_carbonate
    docs, _ = it.read_inputs(REPO)
    bound = k2_carbonate.ksp_keys(docs["screen"])
    assert bound["aragonite"] == "log10_ksp_aragonite_25c_i0"
    table = {pkey for _t, members in it.PARAM_GROUPS for _j, pkey, _s in members}
    assert set(bound.values()) <= table and "log10_ksp_aragonite" not in table
    it.check_k2_keys(docs["screen"])
    stale = copy.deepcopy(docs["screen"])
    stale["bindings"]["R-slurry"]["by_framing"]["aragonite"]["K_sp"] = "log10_ksp_aragonite"
    with pytest.raises(it.InputTableError, match="aragonite"):
        it.check_k2_keys(stale)
    row = next(r for r in _table("parameters") if r[2] == "solubility product, aragonite")
    assert "uniform" in row and "C" in row and "fixed" not in row and "10.3133/ofr91183" in row[-1]


@pytest.mark.skip(reason="checks the placement of the tables and the sources cited in the manuscript sections and bibliography, which are not shipped")
def test_methods_set_the_tables_and_cite_the_tabulated_data_sources():
    raise AssertionError("not run")
