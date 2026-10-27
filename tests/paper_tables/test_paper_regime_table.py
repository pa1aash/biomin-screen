"""The generated regime table: reproducible, traceable, in the specified vocabulary, scope-clean.

The tests that read the stored tables in results/tables, or the production outputs they are made from,
compare with files that are regenerated from the current code and fail while those files are older.
"""
import csv
import hashlib
import json
import re
import shutil

import pytest

from biomin_screen.tables import paths, regime_table as rt
from paper_helpers import REPO

GEN = paths.generated(REPO)
FORBIDDEN = re.compile(r"\b(works|protects?|prevents?|self-heals?|outperforms?|nacre-type|falsified|fails at high voltage)\b", re.I)


@pytest.fixture(scope="module")
def rows():
    with (GEN / rt.OUT_CSV).open(encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def _cell(rows, rid, col):
    return [r for r in rows if r["row_id"] == rid and r["column"] == col][0]


def _tree(tmp_path):
    root = tmp_path / "repo"
    for rel in rt.INPUTS.values():
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(REPO / rel, root / rel)
    return root


def test_regeneration_is_byte_identical():
    assert rt.check(REPO) == []
    first, second = rt.generate(REPO), rt.generate(REPO)
    assert {p: t for p, t in first.items()} == {p: t for p, t in second.items()}
    assert (GEN / rt.OUT_CSV).read_bytes() == first[GEN / rt.OUT_CSV].encode("utf-8")


def test_every_cell_traces_to_a_file_and_its_sha256(rows):
    shas = {rel: hashlib.sha256((REPO / rel).read_bytes()).hexdigest() for rel in rt.INPUTS.values()}
    inputs = json.loads((GEN / rt.OUT_JSON).read_text(encoding="utf-8"))["inputs"]
    assert inputs == shas
    assert len(rows) == 5 * len(rt.ROWS)
    for r in rows:
        files, hashes = r["source_files"], r["source_sha256"]
        if r["words"]:
            assert files, (r["row_id"], r["column"])
            for f, h in zip(files.split("; "), hashes.split("; ")):
                assert shas[f] == h
        else:
            assert not files and r["text"] in ("--", "route criteria")


def test_planted_wrong_cell_fails(tmp_path):
    root = _tree(tmp_path)
    for p, text in rt.generate(root).items():
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8", newline="\n")
    assert rt.check(root) == []
    table = paths.generated(root) / rt.OUT_CSV
    table.write_text(table.read_text(encoding="utf-8").replace(",excluded,", ",open,", 1), encoding="utf-8", newline="\n")
    assert [p.name for p in rt.check(root)] == [rt.OUT_CSV]
    # a changed ladder no longer matches the hash the production outputs were made from
    ladder = root / rt.INPUTS["ladder"]
    ladder.write_text(ladder.read_text(encoding="utf-8").replace("HAp,crystalline,slurry,ALL", "HAp,crystalline,slurry,ALL ", 1),
                      encoding="utf-8", newline="\n")
    with pytest.raises(rt.RegimeTableError, match="sha256"):
        rt.generate(root)


def test_a_planted_class_verdict_that_contradicts_the_bracket_is_refused(tmp_path):
    root = _tree(tmp_path)
    docs, shas = rt.read_inputs(root)
    row = rt.ladder_row(docs["ladder"], "HAp", "crystalline", "slurry")
    row["k1_class_42_43"] = "inconclusive"
    with pytest.raises(rt.RegimeTableError, match="falsifies"):
        rt.k1_class(row, rt.LADDER_COL["C_mid"], rt.edges_of(docs["thresholds"])["C_mid"])


def test_no_forbidden_wording(rows):
    cells = " ".join(r["text"] + " " + r["row_label"] for r in rows)
    assert not FORBIDDEN.search(cells)


def test_the_cells_use_the_specified_vocabulary(rows):
    for r in rows:
        for w in filter(None, r["words"].split("; ")):
            assert w in rt.VOCAB, (r["row_id"], w)
        if "excluded" in r["text"]:
            assert r["column"] != "slurry"
    # an exclusion against dissolution (K2) is named as such, never as the tier-one exclusion
    for r in rows:
        if r["column"] == "acid" and "excluded" in r["text"]:
            assert "excluded against dissolution" in r["text"], r["row_id"]


def test_row_labels_match_the_specification(rows):
    labels = {r["row_id"]: r["row_label"] for r in rows}
    assert labels["aragonite"] == "aragonite (dissolution stability only; formation unsupported at slurry pH and room temperature)"
    assert labels["calcite"].startswith("calcite (suitable against dissolution, a necessary condition, in [") and labels["calcite"].endswith("])")
    # the passing region is named by its Ca_T bound, not by the box of the grid
    assert "Ca_T >= 1e-04 mol dm^-3, 216 cells, plus 2 cells at 1e-05" in labels["calcite"]
    assert "218 of 324 cells: Ca_T >= 1e-04" in _cell(rows, "calcite", "slurry")["text"]
    assert [r["row_id"] for r in rows if r["column"] == "slurry"] == [r[0] for r in rt.ROWS]
    assert labels["carbonate_ctl"] == "carbonate (K1 control)"
    assert "nacre-type" not in " ".join(labels.values()).lower()


def test_cells_follow_the_data_and_the_specified_rules(rows):
    assert _cell(rows, "brushite", "C_hi")["text"] == "excluded above 4.43 V"
    assert _cell(rows, "brushite", "C_mid")["text"] == "open"
    # a K2 cell whose control fails reads inconclusive, never open
    assert _cell(rows, "ocp", "slurry")["text"] == "inconclusive (control fails)" and _cell(rows, "ocp", "acid")["words"] == "inconclusive"
    for rid in ("brushite", "atcp", "li_ortho"):
        assert _cell(rows, rid, "slurry")["words"] == "undetermined"
    assert "[note b]" in _cell(rows, "brushite", "slurry")["text"] and "[note b]" not in _cell(rows, "li_ortho", "slurry")["text"]
    # below the first pass: excluded where every cell is falsified, open where none passes and some are inconclusive;
    # the lowest run is named by its grid pH values, never as "below pH x"
    below = "excluded against dissolution at pH 4.5 and 5.5 (every cell dissolves; lower passivation window, below the sourced range); "
    for rid, ph, lead in (("calcite", "6.5", below), ("aragonite", "6.5", below),
                          ("acc", "8.5", below + "inconclusive at pH 6.5 and 7.5; "), ("acp", "5.5", "inconclusive at pH 4.5; ")):
        c = _cell(rows, rid, "acid")
        assert c["marker"] == "split by pH (alternative b)" and "[split by pH (alternative b)]" in c["text"]
        assert c["text"].startswith(lead + "suitable against dissolution from pH %s up" % ph)
    for rid in ("hap", "btcp"):
        assert _cell(rows, rid, "acid")["text"].startswith("suitable against dissolution from pH 4.5")
    assert _cell(rows, "carbonate_ctl", "C_hi")["words"] == "excluded" and _cell(rows, "carbonate_ctl", "C_lo")["words"] == "open"
    assert _cell(rows, "hap", "C_mid")["words"] == "excluded; excluded"
    # edge rule of the sink: robust threshold and edge sensitivity within the tolerance
    for rid in ("hap", "btcp"):
        assert _cell(rows, rid, "C_mid")["text"].startswith(
            "crystalline: excluded at 4.3 V; edge-sensitive at 4.2 (crossover within 50 mV); amorphous: excluded (by the bound")
    assert _cell(rows, "atcp", "C_mid")["text"].startswith("crystalline: excluded; amorphous: excluded (by the bound")
    # pass counts above the first passing pH use the cells of those pH values
    assert "68 of 162 cells from that pH up" in _cell(rows, "calcite", "acid")["text"]
    assert _cell(rows, "ca_pyro", "slurry")["text"] == "route criteria"
    assert _cell(rows, "baked", "C_hi")["words"] == "undetermined"


def test_the_edge_tolerance_is_read_from_the_thresholds():
    docs = rt.read_inputs(REPO)[0]
    assert rt.edge_tolerance(docs) == pytest.approx(0.05)


def test_the_aluminium_salt_rows_are_taken_from_the_ladder():
    docs = rt.read_inputs(REPO)[0]
    rows = docs["al_salt"]
    assert len(rows) == 6 and {r["k1_verdict"] for r in rows} == {"undetermined"}
    assert {r["phase"] for r in rows} == set(rt.AL_PHASES)
    assert sum("expt route undetermined" in r["budget_status"] for r in rows) == 4


def test_cli_wiring():
    import argparse
    from biomin_screen import cli
    assert callable(cli._tables)
    ap = argparse.ArgumentParser()
    ap.add_argument("which", choices=("regime", "breakeven", "inputs"))
    assert ap.parse_args(["regime"]).which == "regime"


# ------------------------------------------------------------------ the amorphous cells of the calcium orthophosphates
AMORPHOUS_ROWS = {"acp": "ACP", "hap": "HAp", "btcp": "b-TCP", "atcp": "a-TCP"}
BOUND_LABEL = "excluded (by the bound dG_g-to-c >= 0, against the crystalline reference plus water)"


def test_amorphous_label_is_read_from_the_thresholds():
    import yaml
    copy = yaml.safe_load((REPO / rt.INPUTS["thresholds"]).read_text(encoding="utf-8"))
    assert copy["screen_ph"]["w36"]["regime_table"]["amorphous_rows"]["cell_word_excluded"] == BOUND_LABEL


def test_amorphous_cells_follow_the_crystalline_reference_row(rows):
    """Excluded by the bound at C_mid and C_hi where the crystalline row is excluded, undetermined at C_lo (ACP names it)."""
    for rid in AMORPHOUS_ROWS:
        for col in ("C_mid", "C_hi"):
            c = _cell(rows, rid, col)
            assert c["words"] == "excluded; excluded" and c["text"].count(BOUND_LABEL) == 1, (rid, col)
        assert BOUND_LABEL not in _cell(rows, rid, "C_lo")["text"]
    assert _cell(rows, "acp", "C_lo")["text"].endswith("amorphous: undetermined")


def test_every_changed_amorphous_cell_cites_its_crystalline_reference_row(rows):
    changed = [r for r in rows if BOUND_LABEL in r["text"]]
    assert sorted((r["row_id"], r["column"]) for r in changed) == sorted(
        (rid, col) for rid in AMORPHOUS_ROWS for col in ("C_mid", "C_hi"))
    ladder = rt.INPUTS["ladder"]
    for r in changed:
        assert "crystalline reference row %s, slurry (%s)" % (AMORPHOUS_ROWS[r["row_id"]], ladder) in r["note"], r["row_id"]
        assert ladder in r["source_files"].split("; ") and "dG_g-to-c >= 0 (same-composition bound)" in r["note"]
        assert "framing crystalline" in r["note"]           # the crystalline reading it was derived from


def test_other_amorphous_readings_are_not_changed_by_the_bound(rows):
    """Brushite, Ca2P2O7, OCP and the aluminium phosphates carry no excluded-by-bound word; the glass rows keep theirs."""
    for rid in ("brushite", "ocp", "ca_pyro", "ca_meta_glass", "al_ortho", "al_meta", "al_polyp", "lipo3n", "baked", "li_ortho"):
        for col in ("C_lo", "C_mid", "C_hi"):
            assert "by the bound" not in _cell(rows, rid, col)["text"], (rid, col)


def test_the_old_wording_is_gone(rows):
    assert not any("not yet specified" in r["text"] or "I17a" in r["text"] + r["note"] for r in rows)


def test_a_reference_row_that_is_not_excluded_gives_an_undetermined_amorphous_word():
    row = {"phase": "HAp", "E_ub_V": "4.0674", "margin_V": "0.1244", "k1_class_lfp": "inconclusive"}
    label = BOUND_LABEL
    assert rt.amorphous_word(row, "C_lo", [4.1], label, {"C_lo": "undetermined"}) == "undetermined"
    with pytest.raises(rt.RegimeTableError, match="disagrees"):
        rt.amorphous_word(row, "C_lo", [4.1], label, {"C_lo": "falsified (bound)"})


def test_every_amorphous_lowest_class_cell_reads_undetermined_explicitly(rows):
    for rid in ("hap", "btcp", "atcp"):
        assert _cell(rows, rid, "C_lo")["text"] == "crystalline: open; amorphous: undetermined"
    assert _cell(rows, "acp", "C_lo")["text"] == "beta-TCP reference: open; amorphous: undetermined"


def test_no_acid_cell_states_a_sharp_threshold_below_a_grid_point(rows):
    # the acid grid has points only at its pH values, so no cell says "below pH"
    assert not [r["row_id"] for r in rows if "below pH" in r["text"]]


def test_k1_row_count_comes_from_the_precision_map():
    """The number of K1 rows of the precision map, which the precision figure draws as one row."""
    pmap = json.loads((REPO / rt.INPUTS["precision"]).read_text(encoding="utf-8"))
    n = sum(1 for r in pmap["rows"] if r["id"].startswith("k1_"))
    gen = json.loads((GEN / rt.OUT_JSON).read_text(encoding="utf-8"))
    assert gen["numbers"]["precision"]["k1_rows"] == n > 1


@pytest.mark.skip(reason="the macro pipeline and the lint modules of the manuscript tooling are not part of the shipped package")
def test_the_macro_block_is_current_and_renders():
    raise AssertionError("not run")
