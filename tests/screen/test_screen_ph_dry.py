"""Phosphate dry runs and the carbonate regression of the generalised chain; stage rows."""
import json
import shutil

import pytest

from biomin_screen.screen import mineral_dry, run, summary

ROOT = __import__("pathlib").Path(__file__).resolve().parents[2]
SMALL_DRAWS = 2048


@pytest.fixture(scope="module")
def out_dir():
    d = ROOT / run.DRYRUN_PH_DIR / "_pytest"
    d.mkdir(parents=True, exist_ok=True)
    yield d
    shutil.rmtree(d, ignore_errors=True)


@pytest.mark.parametrize("name", ["hap", "acp", "capoly"])
def test_dry_run_writes_a_schema_valid_document(name, out_dir):
    path, doc, stats = mineral_dry.run_mineral(ROOT, name, out_dir / name / "summary.json", allow_mock=True, k1_override=True,
                                          draws=SMALL_DRAWS)
    summary.validate(json.loads(path.read_text(encoding="utf-8")))
    rec = doc["extensions"]["screen"]["ph_screen"]
    assert doc["mock"] is True and rec["provisional"] is True
    assert set(rec) >= {"K1", "K2", "K3", "K4", "deletion_test", "gate", "mineral", "route_evaluators"}
    assert doc["schema_version"] == "5"
    assert rec["gate"]["proceeds"] is True and rec["dry_run"]["k1_gate_overridden"] is True
    assert rec["mineral"]["phase_state"] in ("crystalline", "amorphous")
    assert stats["seconds"] > 0 and stats["peak_mb"] > 0


def test_dry_run_proceeds_and_writes_stage_rows(out_dir):
    """An unresolved K1 proceeds without an override; HAp used as formed gets a slurry and a cell row."""
    _, doc, _ = mineral_dry.run_mineral(ROOT, "hap", out_dir / "gate" / "summary.json", allow_mock=True, draws=SMALL_DRAWS)
    rec = doc["extensions"]["screen"]["ph_screen"]
    assert rec["gate"]["proceeds"] and not rec["gate"]["overridden"] and rec["K3"]["verdict"] != "not run"
    assert rec["K1"]["passes_at"] == []
    rows = {r["stage"]: r for r in doc["stage_rows"]}
    assert set(rows) == {"slurry", "cell"} and rows["slurry"]["film_id"] == rows["cell"]["film_id"]
    assert "K1" not in rows["slurry"] and "K3" not in rows["cell"] and rows["cell"]["scope_class"] == "C_lo"
    assert rows["slurry"]["retained_mass"]["M_adm"] > 0


def test_dry_run_refuses_output_outside_dryrun_ph(tmp_path):
    with pytest.raises(mineral_dry.DryRunRefused):
        mineral_dry.run_mineral(ROOT, "hap", tmp_path / "summary.json", allow_mock=True, draws=SMALL_DRAWS)
    with pytest.raises(mineral_dry.DryRunRefused):
        mineral_dry.run_mineral(ROOT, "hap", ROOT / run.DRYRUN_DIR / "summary.json", allow_mock=True, draws=SMALL_DRAWS)


def test_dry_run_refuses_a_table_that_is_not_mock(out_dir):
    with pytest.raises(Exception):
        mineral_dry.run_mineral(ROOT, "hap", out_dir / "x" / "summary.json", params_path=ROOT / "data" / "params.yaml",
                           allow_mock=True, draws=SMALL_DRAWS)
    with pytest.raises(Exception):
        mineral_dry.run_mineral(ROOT, "hap", out_dir / "y" / "summary.json", allow_mock=False, draws=SMALL_DRAWS)


@pytest.mark.skip(reason="needs a git work tree and the .gitignore of the research repository; the shipped tree has no git history")
def test_dry_run_directory_is_git_ignored():
    assert (ROOT / run.DRYRUN_PH_DIR / ".gitignore").exists()
    import subprocess
    r = subprocess.run(["git", "check-ignore", "-q", str(run.DRYRUN_PH_DIR / "hap" / "summary.json")], cwd=ROOT)
    assert r.returncode == 0


def test_mock_tables_bind_mineral_keys_separately():
    from biomin_screen.screen import mineral, params_adapter
    ms = mineral.registry(run.load_config(ROOT))
    doc, _ = params_adapter.read_table(ROOT / mineral_dry.MOCK_TABLE, True)
    h = mineral_dry.bindings_for(doc, ms["hap"], ms)
    a = mineral_dry.bindings_for(doc, ms["acp"], ms)
    c = mineral_dry.bindings_for(doc, ms["capoly"], ms)
    assert h["K_sp"] == "log10_ksp_hap" and a["K_sp"] == "log10_ksp_acp" and "n_hyd" in a and "n_hyd" not in h
    assert "a_Ca" not in h and c["a_Ca"] == "a_ca_cameta"           # speciation supplies a_Ca for apatite, not for capoly
    ctl = mineral_dry.bindings_for(doc, ms["hap"], ms, drop=["gamma_sl0", "Gamma_s"], control=True)
    assert "gamma_sl" in ctl and "gamma_sl0" not in ctl and "Gamma_s" not in ctl


# ------------------------------------------------------------------ carbonate regression against the stored documents
@pytest.mark.skip(reason="the regression helper biomin_screen.screen.ph_regress and the stored table_adm and ignorance_adm summaries are not shipped")
@pytest.mark.parametrize("doc,prior_set,links", [
    ("results/screen/table_adm/summary.json", "table", {"speciation"}),
    ("results/screen/ignorance_adm/summary.json", "ignorance", {"anchor", "nucleate", "sequester", "speciation"})])
def test_carbonate_reproduces_the_stored_document(doc, prior_set, links):
    from biomin_screen.screen import ph_regress
    sid, rp, entry, cfg = ph_regress.primary_state(ROOT, doc, prior_set)
    res = ph_regress.compare(ph_regress.rerun(rp, entry, cfg), entry)
    assert set(res) == links
    bad = {(l, q): r for l, qs in res.items() for q, r in qs.items() if not r["within_tolerance"]}
    assert bad == {}
    assert max(r["max_rel_diff"] for qs in res.values() for r in qs.values()) < 1e-9
