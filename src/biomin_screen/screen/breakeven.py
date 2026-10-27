"""Break-even ratio r* of the saturated-sink exclusions, from the ladder and the thresholds copy.

For every (phase, framing, stage) of ladder.csv with an ALL row, and every specified cutoff edge E_c of the classes C_mid and
C_hi (configs/thresholds.yaml, screen_ph.margins_v6.cutoff_classes), r* = exp[(E_c - E_ub - m_expt) / (2 R T / F)] from
biomin_screen.physics.sink.breakeven_ratio. E_ub and m_expt are the ALL row's (the limiting complete-budget reaction, ladder README), read, never typed; T is the ladder's 298.15 K. A (row, class) is listed when at least one edge of the class is excluded
(non-negative headroom); an edge of a listed class with negative headroom is listed as "not excluded without correction".
Writes results/screen/breakeven_ph/{breakeven.csv, breakeven.md, provenance.json}.
"""
import csv
import json
from pathlib import Path

import yaml

from biomin_screen.physics import sink
from biomin_screen.physics.bindings import DEFAULT_T
from biomin_screen.screen import kscreen, params_adapter, provenance_guard, run

RUN_ID = "breakeven"
OUT = Path("results") / "screen" / "breakeven_ph"
CLASSES = ("C_mid", "C_hi")
COLUMNS = ("phase", "class", "E_c", "E_ub", "m_expt", "headroom_V", "r_star")
NOTE_ALL = "ALL"


def cutoff_edges(root):
    """{class: [E_c, ...]} for C_mid and C_hi from the thresholds copy."""
    doc = yaml.safe_load((Path(root) / "configs" / "thresholds.yaml").read_text(encoding="utf-8"))
    cc = doc["screen_ph"]["margins_v6"]["cutoff_classes"]
    return {c: sorted(float(e) for e in cc[c]["E_c_V"]) for c in CLASSES}


def limiting_reaction_complete(group, e_ub, margin):
    """True if a complete-budget reaction row of the group carries the ALL row's E_ub and margin (the aggregate's falsifying row)."""
    return any(r["E_ub"] == e_ub and r["margin"] == margin and r["budget_status"] == "complete" for r in group)


def rows(root):
    """The table rows (dicts with COLUMNS plus framing and stage) and the omitted (row, why) pairs."""
    root = Path(root)
    edges = cutoff_edges(root)
    table = kscreen.read_k1(root / provenance_guard.LADDER)
    by_group = {}
    for r in table.reactions:
        by_group.setdefault((r["phase"], r["framing"], r["stage"]), []).append(r)
    out, omitted = [], []
    with (root / provenance_guard.LADDER).open(encoding="utf-8", newline="") as fh:
        for rec in csv.DictReader(ln for ln in fh if ln.strip() and not ln.startswith("#")):
            if rec["reaction_id"].strip() != NOTE_ALL:
                continue
            e_ub, m = (float(rec[c]) if rec[c].strip() else None for c in ("E_ub_V", "margin_V"))
            key = (rec["phase"], rec["framing"], rec["stage"])
            if e_ub is None or m is None:
                continue
            if not limiting_reaction_complete(by_group.get(key, []), e_ub, m):
                omitted.append((key, "no complete-budget reaction carries the aggregate E_ub and margin"))
                continue
            for cls in CLASSES:
                head = [e - e_ub - m for e in edges[cls]]
                if not any(h >= 0 for h in head):
                    continue
                for e_c, h in zip(edges[cls], head):
                    out.append({"phase": rec["phase"], "class": cls, "E_c": e_c, "E_ub": e_ub, "m_expt": m,
                                "headroom_V": round(h, 6), "r_star": sink.breakeven_ratio(e_c, e_ub, m, DEFAULT_T),
                                "framing": rec["framing"], "stage": rec["stage"]})
    return out, omitted


def _fmt(v):
    return "%.6g" % v if isinstance(v, float) else str(v)


def write_csv(path, data):
    with Path(path).open("w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh, lineterminator="\n")
        w.writerow(COLUMNS)
        for r in data:
            w.writerow([r["phase"], r["class"], r["E_c"], r["E_ub"], r["m_expt"], r["headroom_V"],
                        "%.6g" % r["r_star"] if isinstance(r["r_star"], float) else r["r_star"]])


def markdown(data, omitted, prov):
    L = ["# Break-even ratio r* of the saturated-sink exclusions", "",
         "r* = exp[(E_c - E_ub - m_expt) / (2 R T / F)], T = %g K, nu_salt = 1: the exclusion of a row at a cutoff edge E_c stands while "
         "a_pm,sat / a_pm < r* (m_sink = 2 nu (R T / F) ln(a_pm,sat / a_pm)). One decade of the ratio "
         "costs 2 ln10 R T / F = %.1f mV of headroom. E_ub and m_expt are the ALL row of ladder.csv." % (
             DEFAULT_T, 1000 * 2 * 2.302585092994046 * 8.314462618 * DEFAULT_T / 96485.33212), "",
         "| phase | framing | stage | class | E_c (V) | E_ub (V) | m_expt (V) | headroom (mV) | r* |", "|---|---|---|---|---|---|---|---|---|"]
    for r in data:
        L.append("| %s | %s | %s | %s | %g | %g | %g | %.1f | %s |" % (
            r["phase"], r["framing"], r["stage"], r["class"], r["E_c"], r["E_ub"], r["m_expt"], 1000 * r["headroom_V"],
            "%.3g" % r["r_star"] if isinstance(r["r_star"], float) else r["r_star"]))
    if omitted:
        L += ["", "Omitted: " + "; ".join("%s (%s)" % ("/".join(k), why) for k, why in omitted) + "."]
    L += ["", "Provenance: code sha %s%s; ladder sha256 %s; thresholds copy sha256 %s." % (
        prov["code_sha"], " (dirty tree)" if prov["git_dirty"] else "", prov["ladder_sha256"], prov["thresholds_copy_sha256"])]
    return "\n".join(L) + "\n"


def main(root):
    root = Path(root)
    out = root / OUT
    if out.exists():
        raise run.ProductionRefused("%s exists" % out)
    provenance_guard.check_fixed(root)
    data, omitted = rows(root)
    params = root / params_adapter.PRODUCTION_PARAMS
    ctx_prov = run._provenance(root, run.load_config(root), root / run.CONFIG,
                               [params_adapter.RegimePriors("R-slurry", None, {}, str(params), run._sha256_file(params), False)],
                               run.THRESHOLDS, False)
    prov = {"run_id": RUN_ID, "code_sha": ctx_prov["git_sha"], "git_dirty": ctx_prov["git_dirty"],
            "ladder_file": provenance_guard.LADDER.as_posix(), "ladder_sha256": provenance_guard.sha256_file(root / provenance_guard.LADDER),
            "thresholds_copy_file": "configs/thresholds.yaml",
            "thresholds_copy_sha256": provenance_guard.sha256_file(root / "configs" / "thresholds.yaml"),
            "temperature_K": DEFAULT_T, "nu_salt": 1, "classes": list(CLASSES), "edges": cutoff_edges(root), "n_rows": len(data)}
    out.mkdir(parents=True)
    write_csv(out / "breakeven.csv", data)
    (out / "breakeven.md").write_text(markdown(data, omitted, prov), encoding="utf-8")
    (out / "provenance.json").write_text(json.dumps(prov, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    return data


if __name__ == "__main__":
    import argparse
    from biomin_screen._util import repo_root
    argparse.ArgumentParser(prog="python -m biomin_screen.screen.breakeven", description="Break-even ratio of the saturated-sink exclusions, arithmetic over the K1 ladder; writes results/screen/breakeven_ph/.").parse_args()
    main(repo_root())
