"""Per-pH minimum doses, the dose qualifier, the nucleation numbers and the ratio-grid run of the regime table.

Tests that read the stored tables in results/tables compare with files that are regenerated from the current code.
"""
import csv
import json
import re
import shutil

import pytest

from biomin_screen.tables import paths, regime_table as rt
from paper_helpers import REPO

GEN = paths.generated(REPO)
HIGH_TEXT = "at or above 0.01 mol dm^-3"          # the plain form of the dose threshold, as the CSV prints it


@pytest.fixture(scope="module")
def rows():
    with (GEN / rt.OUT_CSV).open(encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


@pytest.fixture(scope="module")
def docs():
    return rt.read_inputs(REPO)[0]


@pytest.fixture(scope="module")
def numbers():
    return json.loads((GEN / rt.OUT_JSON).read_text(encoding="utf-8"))["numbers"]


def test_per_ph_table_has_every_phase_at_every_acid_ph(docs):
    rows_ = rt.perph_rows_parts(docs)
    assert len(rows_) == len(rt.PERPH_ROWS) * len(rt.perph_phs(docs, "acid")) == 8 * 5
    labels = [r[0] for r in rows_ if r[0]]
    assert len(labels) == 8


def test_per_ph_numbers_are_the_file_numbers(docs, numbers):
    with (REPO / rt.INPUTS["perph"]).open(encoding="utf-8", newline="") as fh:
        src = [r for r in csv.DictReader(fh) if r["grid"] == "acid" and r["phase"] == "HAp" and r["source"] == "fixed"]
    assert len(src) == 5
    for r in src:
        base = numbers["perph"]["hap"]["%g" % float(r["pH"])]
        assert base["n_pass"] == int(r["n_passing"])
        assert base["fraction"] == pytest.approx(float(r["passing_fraction"]))
    assert numbers["perph"]["ph"]["4.5"] == 4.5


def test_every_first_pass_entry_names_its_minimum_dose(rows):
    for rid in ("calcite", "aragonite", "acc", "hap", "acp", "btcp"):
        text = [r for r in rows if r["row_id"] == rid and r["column"] == "acid"][0]["text"]
        assert re.search(r"suitable against dissolution from pH [0-9.]+", text)
        assert "lowest passing Ca_T" in text and re.search(r"Ca_T [0-9.e+-]+", text), rid
        if rid in ("hap", "acp", "btcp"):
            assert "lowest passing" in text and "P_T" in text and "mol dm^-3" in text
        # at 0.01 mol dm^-3 or above the entry says so
        nums = [float(x) for x in re.findall(r"(?:Ca_T|P_T) ([0-9.]+e[+-][0-9]+)", text)]
        assert nums and (max(nums) >= rt.HIGH_DOSE) == (HIGH_TEXT in text), rid


def test_high_dose_rule_on_the_per_ph_rows(docs):
    rows_ = rt.perph_rows_parts(docs)
    phs = rt.perph_phs(docs, "acid")
    expect = []
    for key, csvname, _label, src in rt.PERPH_ROWS:
        for ph in phs:
            r = rt.perph_row(docs, "acid", src, csvname, ph)
            expect.append("--" if not r["n_pass"] else ("yes" if max(v for v in (r["ca"], r["p"]) if v is not None) >= 0.01 else "no"))
    got = [r[8][0] if isinstance(r[8], list) else r[8] for r in rows_]
    assert got == expect and "yes" in got and "no" in got


def test_nucleation_numbers_are_the_file_numbers(numbers):
    f3 = json.loads((REPO / rt.INPUTS["f3"]).read_text(encoding="utf-8"))
    gsl = f3["gamma_sl_J_m2"]["admitted_draws"]
    nuc = numbers["nucleation"]
    assert nuc["gsl_q05"] == pytest.approx(gsl["q05"] * 1000)
    assert nuc["gsl_q50"] == pytest.approx(gsl["q50"] * 1000)
    assert nuc["gsl_max"] == pytest.approx(gsl["max"] * 1000)
    assert round(nuc["mass_sourced_pct"], 2) == 0.29 and round(nuc["mass_design_max_pct"], 1) == 3.4
    assert (nuc["c3_falsified"], nuc["c3_designs"], nuc["c3_inconclusive"]) == (24, 36, 12)
    assert round(numbers["sobol"]["half_width"], 3) == 0.098 and numbers["sobol"]["target"] == pytest.approx(0.02)


def test_rerun_and_control_numbers(numbers):
    rerun = numbers["rerun"]["brushite"]
    assert rerun["acid"]["rerun"] == 85 and rerun["acid"]["cells"] == 540 and rerun["alkaline"]["rerun"] == 3
    ctl = numbers["control"]
    assert ctl["cells_moved"] == 0 and ctl["ph_from"] == 12 and ctl["ph_to"] == pytest.approx(7.65)


def test_planted_disagreement_between_fixed_and_rerun_rows_is_refused(tmp_path, docs):
    root = tmp_path / "repo"
    for rel in rt.INPUTS.values():
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(REPO / rel, root / rel)
    perph = root / rt.INPUTS["perph"]
    lines = perph.read_text(encoding="utf-8").splitlines()
    k = [i for i, l in enumerate(lines) if l.startswith("acid,rerun,HAp,4.5,")][0]
    cols = lines[k].split(",")
    cols[5] = str(int(cols[5]) + 1)
    lines[k] = ",".join(cols)
    perph.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    with pytest.raises(rt.RegimeTableError, match="differ"):
        rt.generate(root)


# ---------------------------------------------------------------- ratio grid

def _mant_exp(v):
    import math
    e = math.floor(math.log10(v))
    return round(v / 10 ** e, 1), e


def _ratio_csv():
    with (REPO / rt.INPUTS["perph3"]).open(encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def test_second_column_group_is_the_ratio_grid_file(docs, numbers):
    rows_ = rt.perph_rows_parts(docs)
    assert all(len(r) == 13 for r in rows_)
    src = {(r["grid"], r["source"], r["phase"], float(r["pH"])): r for r in _ratio_csv()}
    for key, phase, ratio in (("hap", "HAp", "1.67"), ("btcp", "b-TCP", "1.5"), ("brushite", "brushite", "1")):
        for ph in rt.perph_phs(docs, "acid"):
            r = src[("acid", "ratio_" + ratio, phase, ph)]
            base = numbers["perph"][key]["%g" % ph]
            assert base["stoich_ca"] == pytest.approx(float(r["min_passing_Ca_T_mol_dm3"]), rel=0.5)
            assert _mant_exp(base["stoich_p"]) == _mant_exp(float(r["min_passing_P_T_mol_dm3"]))
    for r in rows_:
        if r[0] in ("calcite", "aragonite", "ACC", "ACP") or r[0].startswith("OCP"):
            assert [c[0] for c in r[9:]] == ["--"] * 4


def test_own_ratio_minima_are_the_stated_doses(numbers):
    want = {("hap", "alkaline"): (1e-05, 6.0e-06, 10.0), ("hap", "acid"): (1e-04, 6.0e-05, 8.5),
            ("btcp", "alkaline"): (1e-04, 6.7e-05, 10.0), ("btcp", "acid"): (1e-03, 6.7e-04, 7.5),
            ("brushite", "alkaline"): (1e-01, 1.0e-01, 10.0), ("brushite", "acid"): (1e-02, 1.0e-02, 5.5)}
    for (key, grid), (ca, p, ph) in want.items():
        got = numbers["ratio"]["own"][key][grid]
        assert got["ca"] == pytest.approx(ca, rel=1e-3) and float("%.1e" % got["p"]) == pytest.approx(p, rel=1e-3), (key, grid, got)
        assert got["ph"] == ph
    assert numbers["perph"]["ph"]["4.5"] == 4.5


def test_first_pass_cells_name_both_doses(rows):
    for rid, ratio in (("hap", "1.67"), ("btcp", "1.5")):
        text = [r for r in rows if r["row_id"] == rid and r["column"] == "acid"][0]["text"]
        assert "on the crossed grid" in text and "at its own Ca:P of " + ratio + ", lowest passing Ca_T" in text, text
        assert text.count("lowest passing Ca_T") == 2 and text.count("P_T") == 2 and HIGH_TEXT in text
    acp = [r for r in rows if r["row_id"] == "acp" and r["column"] == "acid"][0]["text"]
    assert "own Ca:P" not in acp


def test_planted_ratio_grid_disagreement_is_refused(tmp_path):
    root = tmp_path / "repo"
    for rel in rt.INPUTS.values():
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(REPO / rel, root / rel)
    path = root / rt.INPUTS["perph3"]
    lines = path.read_text(encoding="utf-8").splitlines()
    k = [i for i, l in enumerate(lines) if l.startswith("acid,crossed,HAp,4.5,")][0]
    cols = lines[k].split(",")
    cols[5] = str(int(cols[5]) + 1)
    lines[k] = ",".join(cols)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    with pytest.raises(rt.RegimeTableError, match="differs from the per-pH table"):
        rt.generate(root)


@pytest.mark.skip(reason="checks sentences of the manuscript text (results, methods and the supplementary information), which is not shipped")
def test_manuscript_wording_of_the_dose_and_nucleation_statements():
    raise AssertionError("not run")
