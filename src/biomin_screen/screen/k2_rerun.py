"""The rerun of the phosphate K2 with updated K_sp keys (new directories <run>_ph2/, beside the fixed runs).

The grid is that of the phosphate K2 of biomin_screen.screen.k2_grid (Ca_T and P_T crossed on a common decade grid; k2_grid.phosphate_cells), the phases add
the K_sp keys of configs/screen_ph2.yaml, and the supersaturated control is a rule: the grid cell of maximum
median Omega of the phase in the wet slurry state. Fixed outputs are read, never written.
"""
import json
import time
from pathlib import Path

import numpy as np
import yaml

from biomin_screen.screen import k2_grid, params_adapter, provenance_guard, run, summary

CONFIG = Path("configs") / "screen_ph2.yaml"
RUN_ID = "k2_rerun"
SUFFIX = "_decade"


def load(root):
    return yaml.safe_load((Path(root) / CONFIG).read_text(encoding="utf-8"))


def phases_of(cfg, ph2):
    """{name: spec} in the order of the rerun: the fixed specs of screen.yaml plus the specs of screen_ph2.yaml."""
    allp = {**cfg["k2_phases"], **ph2["k2_phases_ph2"]}
    return {n: allp[n] for n in ph2["phase_order"]}


def max_omega_control(recs, state="slurry"):
    """Control record of the rule: the cell of maximum median Omega in the given state, with its verdict in that state."""
    best, bid = None, None
    for cid, r in recs.items():
        m = (r.get("omega_median_by_state") or {}).get(state)
        if m is not None and np.isfinite(m) and (best is None or m > best):
            best, bid = float(m), cid
    if bid is None:
        return {"verdict": "undetermined", "gap": "no finite Omega in any cell", "control_cell": None, "omega_median": None}
    r = recs[bid]
    v = (r.get("by_state") or {}).get(state, r["verdict"])
    return dict(k2_grid.brief(dict(r, verdict=v)), control_cell=bid, omega_median=best)


def ksp_value(resolver, key):
    return None if key is None else float(resolver.value(key))


def part(ctx, ph2, grid):
    """K2 of every phase on one grid: 'alkaline' (specified slurry grid, drying states) or 'acid' (pH 4.5 to 8.5, wet slurry)."""
    phases = phases_of(ctx.cfg, ph2)
    if grid == "alkaline":
        cfg, states = ctx.cfg, ("slurry", "drying")
        cells = k2_grid.phosphate_cells(cfg, ctx.resolver, "pH", drying=True)
    else:
        cfg, states = k2_grid.acid_cfg(ctx.cfg), ("slurry",)
        cells = k2_grid.phosphate_cells(cfg, ctx.resolver, "pH_acid_adjusted", drying=False)
    out = {}
    for name in phases:
        rec = k2_grid.eval_phosphate(ctx.params_path, cfg, ctx.resolver, name, cells, ctx.p, ctx.minerals, states,
                                     ctx.allow_mock, None, supersaturated_from=max_omega_control, phases=phases)
        reg = phases[name].get("ksp_key_specified") or phases[name].get("ksp")
        rec["specified_ksp_key"] = reg
        rec["log10_ksp_read"] = ksp_value(ctx.resolver, reg)
        out[name] = rec
    return {"grid": {"cells": len(cells), "axes": "Ca_T x P_T (independent decade grid) x a_w(drying) x pH x I"
                     if grid == "alkaline" else "Ca_T x P_T (independent decade grid) x pH x I, wet slurry"},
            "state": grid, "phases": out}


def rows_of(body, doc):
    rows = []
    for grid, blk in body["states"].items():
        for name, rec in blk["phases"].items():
            keys = ((rec["ksp_key"],) if rec["ksp_key"] else ()) + k2_grid.PHOSPHATE_INPUTS
            ev = k2_grid.evidence_of(doc, keys)
            if not rec["ksp_key"]:
                ev["K_sp"] = "gap"
            state = "specified alkaline slurry grid" if grid == "alkaline" else "acid-adjusted (incumbent phosphoric-acid pH control)"
            rows.append(k2_grid._k2_row("k2:%s:%s:ph2" % (name, grid), "k2_%s" % name, rec["formula"],
                                        "candidate" if grid == "alkaline" else "comparator", rec["ladder_phase"],
                                        ["rerun with updated keys, rule-based supersaturated control"], rec, ev,
                                        {"state": state}))
    return rows


def run_ph2(root, out_path, grids, dry=False, label=None):
    """Write one rerun document (production: a new directory <run>_ph2). Returns (path, doc, stats)."""
    root, out_path = Path(root), Path(out_path)
    t0 = time.perf_counter()
    if not dry:
        provenance_guard.check_fixed(root)
        if not run._inside(out_path, root / run.SCREEN_DIR) or not out_path.parent.name.endswith(SUFFIX):
            raise run.ProductionRefused("production output belongs in a new directory %s/<run>%s/" % (run.SCREEN_DIR, SUFFIX))
        if out_path.exists() or out_path.parent.name in (r + "_ph" for r in ("k2_grid", "phosphate_films")):
            raise run.ProductionRefused("%s exists or is a fixed directory" % out_path)
    ctx = k2_grid.Context(root)
    ph2 = load(root)
    states = {g: part(ctx, ph2, g) for g in grids}
    body = {"run_id": RUN_ID, "p_cred": ctx.p, "start_draws": k2_grid.START_DRAWS, "half_width_max": k2_grid.HALF_WIDTH_MAX,
            "seed": int(ctx.cfg["propagation"]["seed"]), "fixed_runs": ph2["fixed_runs"],
            "config_ph2_file": CONFIG.as_posix(), "config_ph2_hash": provenance_guard.tagged(provenance_guard.sha256_file(root / CONFIG)),
            "supersaturated_control": ph2["supersaturated_control"], "states": states}
    stats = k2_grid.stats_of(body)
    stats.update(seconds=time.perf_counter() - t0, peak_mb=k2_grid.peak_mb())
    body["run"] = stats
    prov = run._provenance(root, ctx.cfg, root / run.CONFIG, [params_adapter.RegimePriors("R-slurry", None, {}, str(ctx.params_path),
                           run._sha256_file(ctx.params_path), False)], run.THRESHOLDS, dry)
    prov["run_label"] = label or out_path.parent.name
    doc = summary.build(None, prov, mock=dry or ctx.doc["mock"], extensions={"screen": {"k2_rerun": body}},
                        stage_rows=rows_of(body, ctx.doc))
    path = summary.write(doc, out_path)
    return path, doc, stats
