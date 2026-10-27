"""Inputs of the stability evaluators: the Pourbaix baseline of the slurry regime and the scheme table of the
cell regime.

Slurry regime. Dissolution of calcite is judged from Omega_bulk (measured Ksp, carbonate speciation) by the
screen. This module supplies:
- the Pourbaix diagram as the competing-phase and Al-phase baseline at fixed C(IV), with its DFT
  tolerance (the stability-criterion edge from formation_energy_mae), over the design axes a_Ca, C_T and total
  dissolved Al: one schema v2 document per (a_Ca, C_T, total Al) under c5/slurry/;
- the calcite offset of that diagram stated (its solubility bias and the edge's shift), so it is
  read as context and never as the dissolution test;
- the Omega test fixture (omega_control.json, biomin_screen.pourbaix.omega_control);
- the carbon-redox sensitivity: the fraction of the region where calcite lies above its edge when
  carbon redox is allowed.

Cell regime. Where an all-experimental thermochemical route exists for a reaction, it
governs; DFT-based schemes, corrected by their benchmark error, apply only where experimental data
are missing; the uncorrected janaf and mp schemes are comparators. Every scheme goes in one table,
and the verdict per phase is given as a function of E_cell_max over the cathode classes (the
per-class keys of the e_cell_max design axis, or the evidence rows of e_cell_max when the snapshot has
no per-class keys). The margin follows the governing route: m_expt (key window_margin_expt) for the
all-experimental route, m_E (window_margin) for the benchmark-corrected DFT schemes and the DFT
reduction limit. While a margin key is a gap it is 0 and the margin that would flip each verdict is
reported instead.

    python -m biomin_screen.pourbaix.c5 --config results/pourbaix/config/c5.yaml
"""
import argparse
import json
import re
import sys

import numpy as np

from biomin_screen.pourbaix import cache, cell_window, inputs, omega_control, provenance
from biomin_screen.pourbaix import carbonate_run as R
from biomin_screen.pourbaix.entries import KJ_PER_MOL_PER_EV
from biomin_screen.pourbaix.paths import POURBAIX_RESULTS, rel

RUN_ID = "carbonate-c5"
OUT = POURBAIX_RESULTS / "c5"
ORDER = ["feasible", "inconclusive", "falsified"]

# Cathode classes of the e_cell_max rows, read from the phase field of each row's conditions.
CLASS_PATTERNS = [("LNMO", r"LNMO"), ("LFP", r"LFP"), ("NCA", r"\bNCA\b"), ("LCO", r"LiCoO2|\bLCO\b"),
                  ("NMC", r"NMC|NCM")]


# =============================================================================== slurry regime
def slurry_inputs(raw, meta, params):
    summary, outs = R.run_slurry(raw, meta, params, out=OUT, stage=RUN_ID, al_axis=True, compact=True)
    pts = summary["points"]
    frac = [p["carbon_redox_sensitivity"]["fraction_above_edge"] for p in pts]
    ctl = summary["falsifiability_control"]["calcite_undersaturated"]
    bias = summary["implied_constants"]["calcite_solubility_bias_log10"]
    baseline = {
        "role": "competing-phase and Al-phase baseline at fixed C(IV); not the dissolution test",
        "dft_tolerance": {"edge_calcite_eV_per_atom": summary["edges"]["calcite_eV_per_atom"],
                          "edge_ACC_eV_per_atom": summary["edges"]["ACC_eV_per_atom"],
                          "source": summary["edges"]["e_form"], "rule": summary["edges"]["rule"]},
        "calcite_offset_stated": {
            "proxy_minus_measured_log10_ksp": bias,
            "edge_shift_log10": ctl["detection_threshold_log10_omega"] - bias,
            "proxy_reports_calcite_above_edge_only_below_log10_omega": ctl["detection_threshold_log10_omega"],
            "reading": "the Pourbaix proxy holds calcite more stable than the measured Ksp by the bias, and its "
                       "edge adds the shift; it is therefore context for the Ca phases, and Omega_bulk decides"},
        "competing_phases": {p["id"]: {"domains_in_region": p["domains_in_region"],
                                       "cross_compounds_stable": p["cross_compounds_stable"],
                                       "calcite_on_hull_fraction": p["calcite"]["stable_fraction"],
                                       "calcite_within_edge_everywhere": p["calcite"]["within_edge_everywhere"]}
                             for p in pts},
        "al_phase_baseline": summary["native_oxide_baseline"]["by_total_Al"],
        "documents": sorted({d for p in pts for d in p["documents"]}),
    }
    redox = {"question": "With carbon redox allowed (reduced carbon in the hull), on what fraction of the (pH, E) "
                         "region does calcite lie above its edge? A labelled sensitivity, never the decision.",
             "fraction_above_edge": {"min": min(frac), "max": max(frac),
                                     "by_point": {p["id"]: p["carbon_redox_sensitivity"]["fraction_above_edge"]
                                                  for p in pts}},
             "max_dec_eV_per_atom": max(p["carbon_redox_sensitivity"]["calcite_max_dec_eV_per_atom"] for p in pts),
             "reading": "thermodynamics only; carbonate reduction at these potentials is not a rate claim"}
    return summary, outs, baseline, redox


# ================================================================================= cell regime
def cathode_classes(params):
    """E_cell_max per cathode class: the per-class keys of the e_cell_max design axis when the snapshot
    has them, otherwise read from the evidence rows of e_cell_max (row ids carried)."""
    opts = (params.entry("e_cell_max").get("prior") or {}).get("options") or []
    if opts:
        classes = {}
        for o in opts:
            e = params.entry(o["key"])
            classes[o["label"]] = {"key": o["key"], "rows": list(e.get("sources") or []), "status": e["status"],
                                   "lower_bound": False, "E_cell_max_V": {"min": float(e["range"]["min"]),
                                                                          "value": float(e["value"]),
                                                                          "max": float(e["range"]["max"])}}
        return dict(sorted(classes.items(), key=lambda kv: (kv[1]["E_cell_max_V"]["min"],
                                                            kv[1]["E_cell_max_V"]["max"])))
    classes = {}
    for rid in params.entry("e_cell_max")["sources"]:
        row = params.row(rid)
        phase = row["conditions"].split("phase=")[1] if "phase=" in row["conditions"] else row["conditions"]
        names = [n for n, pat in CLASS_PATTERNS if re.search(pat, phase)] or ["other"]  # a row may name several
        txt = row["value"].strip()
        lower_bound = txt.startswith(">")
        v = float(txt.lstrip("><= "))
        for name in names:
            if name == "LCO" and lower_bound:
                name = "LCO, high-voltage"
            c = classes.setdefault(name, {"rows": [], "values_V": [], "lower_bound": False})
            c["rows"].append(rid)
            c["values_V"].append(v)
            c["lower_bound"] = c["lower_bound"] or lower_bound
    for c in classes.values():
        c["E_cell_max_V"] = {"min": min(c["values_V"]), "max": max(c["values_V"])}
    return dict(sorted(classes.items(), key=lambda kv: kv[1]["E_cell_max_V"]["min"]))


def releases_co2(reaction):
    return bool(re.search(r"\bCO2\b", reaction.split("->")[-1])) if reaction else False


def governing(by_scheme, b2):
    """The experimental route governs where it exists; otherwise the benchmark-corrected DFT schemes."""
    expt = by_scheme.get("expt")
    corrected = {}
    for s in ("janaf", "mp"):
        lim = by_scheme.get(s)
        if lim and lim["status"] == "ok" and releases_co2(lim["reaction"]):
            corrected[s] = lim["value_V"] - b2[s]
    if expt and expt["status"] == "ok":
        return {"route": "expt", "values_V": {"expt": expt["value_V"]}, "reaction": expt["reaction"]}, corrected
    if corrected and len(corrected) == 2:
        return {"route": "benchmark-corrected DFT", "values_V": corrected,
                "reaction": by_scheme["janaf"]["reaction"]}, corrected
    why = sorted({(l or {}).get("reason") or "" for l in by_scheme.values()} - {""})
    return {"route": None, "values_V": {}, "reaction": "", "reason": "; ".join(why) or "no route"}, corrected


def m_expt_provisional(cands, reaction, params):
    """Provisional uncertainty of an expt onset (V): the sourced range half-widths of the keys in the
    reaction, summed linearly with their coefficients, per transferred electron. Species from tables
    without a stated uncertainty (JANAF, NBS via the exchange enthalpy) are listed as unbudgeted."""
    cand = next((c for c in cands if c["reaction"] == reaction and c["status"] == "finite"), None)
    if cand is None:
        return None, []
    dn = cand["species"]["Li"]["coefficient"]
    half, unbudgeted = 0.0, []
    for f, sp in cand["species"].items():
        src = sp.get("source")
        if isinstance(src, dict) and src.get("key"):
            r = params.range(src["key"])
            half += abs(sp["coefficient"]) * (float(r["max"]) - float(r["min"])) / 2.0 / 1000.0 / KJ_PER_MOL_PER_EV
        elif sp.get("kind") in ("expt", "derived"):
            unbudgeted.append(f)
    return half / abs(dn), sorted(unbudgeted)


def verdict(gov, e_max, m, solid_salt, red_verdict):
    """Verdict on the governing route: a falsification must hold for every governing value; a solid-salt
    pass is inconclusive; an undetermined limit never passes. Combined with the reduction verdict."""
    vals = list(gov["values_V"].values())
    if not vals:
        ox = "inconclusive"
    elif max(vals) < e_max - m:
        ox = "falsified"
    elif min(vals) >= e_max + m:
        ox = "inconclusive" if solid_salt else "feasible"
    else:
        ox = "inconclusive"
    return max([ox, red_verdict], key=ORDER.index), ox


def cell_inputs(raw, meta, params):
    prov = R.w4_provenance(meta, params.sha)
    ext = R.stage_extension(params, meta, stage=RUN_ID)
    outs = cell_window.run_cell(raw, meta, params, prov, ext, out=OUT, stage=RUN_ID)
    summ = json.loads((OUT / "cell_summary.json").read_text(encoding="utf-8"))
    bench = json.loads((POURBAIX_RESULTS / "gas_reference.json").read_text(encoding="utf-8"))
    b2 = {s: x["error_V_per_electron"] for s, x in
          next(b for b in bench["result"]["benchmarks"] if b["id"] == "B2")["schemes"].items()}
    m_key = raw["R-cell"]["m_expt"]["keys"]
    m_entries = {k: params.entry(k) for k in m_key}
    gaps = [k for k, e in m_entries.items() if e.get("value") is None]
    m_expt = 0.0 if gaps else sum(float(e["value"]) for e in m_entries.values())
    md_key = raw["R-cell"]["m_dft"]["key"]
    m_dft = float(params.value(md_key)) if params.value(md_key) is not None else 0.0
    m_route = {"expt": m_expt, "benchmark-corrected DFT": m_dft, None: 0.0}
    classes = cathode_classes(params)
    sides = [s for s in ("min", "value", "max") if all(s in c["E_cell_max_V"] for c in classes.values())]
    e_min = float(params.value("e_cell_min"))
    table, by_phase = [], {}
    for phase, po in summ["phases"].items():
        red = po["reduction"]
        red_verdict = ("feasible" if red["status"] == "ok" and red["value_V"] <= e_min - m_dft else
                       "falsified" if red["status"] == "ok" and red["value_V"] > e_min + m_dft else "inconclusive")
        per_sink = {}
        for sink, rec in po["by_sink"].items():
            if rec["group"] != "specified":
                continue
            solvated = sink == "solvated"
            by = {} if solvated else rec["oxidation_by_scheme"]
            gov, corr = governing(by, b2) if not solvated else (
                {"route": None, "values_V": {}, "reaction": "", "reason": rec["reason"]}, {})
            row = {"phase": phase, "sink": sink, "sink_kind": "solvated" if solvated else "solid_salt",
                   "governing_route": gov["route"], "governing_V": gov["values_V"],
                   "expt_V": None if solvated else by["expt"]["value_V"],
                   "janaf_V": None if solvated else by["janaf"]["value_V"],
                   "mp_V": None if solvated else by["mp"]["value_V"],
                   "janaf_corrected_V": corr.get("janaf"), "mp_corrected_V": corr.get("mp"),
                   "benchmark_error_V_per_electron": b2,
                   "reaction": gov["reaction"] or (by.get("expt") or {}).get("reaction", ""),
                   "status": "ok" if gov["values_V"] else "undetermined",
                   "reason": gov.get("reason", "")}
            m_prov, unbudgeted = (m_expt_provisional(rec["candidates"]["expt"], gov["reaction"], params)
                                  if gov["route"] == "expt" else (None, []))
            m = m_route[gov["route"]]
            row["margin_V"] = m
            row["margin_key"] = {"expt": m_key, "benchmark-corrected DFT": [md_key]}.get(gov["route"], [])
            row["m_expt_provisional_V"] = m_prov
            row["m_expt_unbudgeted_species"] = unbudgeted
            per_class = {}
            for cname, c in classes.items():
                at = {s: verdict(gov, c["E_cell_max_V"][s], m, not solvated, red_verdict) for s in sides}
                v_lo, ox_lo = at["min"]
                v_hi, ox_hi = at["max"]
                vals = list(gov["values_V"].values())
                per_class[cname] = {
                    "E_cell_max_V": c["E_cell_max_V"], "key": c.get("key"), "rows": c["rows"],
                    "lower_bound": c["lower_bound"],
                    "verdict": max([v_lo, v_hi], key=ORDER.index) if v_lo == v_hi else "%s to %s" % (v_lo, v_hi),
                    "oxidation_verdict": ox_lo if ox_lo == ox_hi else "%s to %s" % (ox_lo, ox_hi),
                    "verdict_at": {s: at[s][0] for s in sides},
                    "margin_to_flip_V": (min(abs(c["E_cell_max_V"][s] - v) for s in ("min", "max") for v in vals)
                                         if vals else None)}
                if m_prov is not None:
                    pv = [verdict(gov, c["E_cell_max_V"][s], m_prov, True, red_verdict)[0] for s in ("min", "max")]
                    per_class[cname]["verdict_at_provisional_m_expt"] = pv[0] if pv[0] == pv[1] else "%s to %s" % tuple(pv)
            row["by_cathode_class"] = per_class
            vals = list(gov["values_V"].values())
            row["cutoff_dependence"] = (
                {"falsified_for_E_cell_max_above_V": max(vals) + m,
                 "inconclusive_between_V": [min(vals) - m, max(vals) + m],
                 "solid_salt_pass_inconclusive_for_E_cell_max_at_or_below_V": min(vals) - m}
                if vals else {"undetermined": True})
            per_sink[sink] = row
            table.append(row)
        reg = [r for k, r in per_sink.items()]
        by_phase[phase] = {
            "reduction": red, "reduction_verdict": red_verdict, "by_sink": per_sink,
            "by_cathode_class": {c: {"worst_over_specified_sinks": max([r["by_cathode_class"][c]["verdict"].split(" to ")[-1]
                                                                       for r in reg], key=ORDER.index),
                                     "best_over_specified_sinks": min([r["by_cathode_class"][c]["verdict"].split(" to ")[0]
                                                                      for r in reg], key=ORDER.index)}
                                 for c in classes}}
    rule = ("where an all-experimental thermochemical route exists for a reaction it governs; DFT-based "
            "schemes corrected by their benchmark error (B2, CaCO3 -> Ca + CO2 + 1/2 O2, per electron) apply only where "
            "experimental data are missing and only to CO2-releasing reactions; janaf and mp uncorrected are comparators. "
            "Verdict on the governing route (a falsification must hold for every governing value; a solid-salt "
            "pass is inconclusive; undetermined never passes), combined with the reduction verdict.")
    doc = {"stage": RUN_ID, "generated_utc": provenance.utc_now(), "provenance": prov, "params_sha": params.sha,
           "question": "Per phase and specified sink, what is the oxidation onset vs Li+/Li under the governing route "
                       "of the governing-route rule, how do the comparator schemes compare, and what is the verdict for each "
                       "cathode class's charge cut-off? (thermodynamic windows; no rates)",
           "rule": rule, "sequence_disclosure": "The cell-regime onsets were computed before the scheme rule was "
                                               "proposed; the rule is therefore not independent of them.",
           "m_expt": {"keys": [params.cite(k) for k in m_key], "value_used_V": m_expt, "gaps": gaps,
                      "status": "gap" if gaps else "sourced",
                      "reading": "the margin of rows governed by the all-experimental route; while any key is a gap "
                                 "m_expt = 0 is used and margin_to_flip_V says how large it would have to be to change "
                                 "each class verdict"},
           "m_dft": {**params.cite(md_key), "value_used_V": m_dft,
                     "reading": "the margin of rows governed by the benchmark-corrected DFT schemes and of the DFT "
                                "reduction limit; the key states it for the specified reaction (other reactions scale by "
                                "their uncancelled atoms per electron)"},
           "solvated_sink": {"status": "gap" if any(params.entry(k).get("value") is None for k in
                                                    raw["R-cell"]["solvated"]["keys"]) else "available",
                             "keys": [params.cite(k) for k in raw["R-cell"]["solvated"]["keys"]],
                             "reading": "no solvated-sink onset is computed while the Ca2+ and Al3+ transfer free "
                                        "energies relative to Li+ are gaps; no cell-regime pass can count",
                             "water_analogs": {
                                 "keys": [params.cite(k) for k in raw["R-cell"]["solvated"].get("analog_keys", [])
                                          if k in params.snap["entries"]],
                                 "status": "not converted",
                                 "reason": raw["R-cell"]["solvated"].get("analog_reason", "")}},
           "cathode_classes": classes, "E_cell_min": params.cite("e_cell_min"),
           "table": table, "phases": by_phase,
           "undetermined_sinks": sorted({"%s/%s" % (r["phase"], r["sink"]) for r in table if r["status"] != "ok"})}
    path = R._dump(OUT / "cell_scheme_table.json", doc)
    return doc, outs + [path]


# ================================================================================== main
def main(argv=None):
    ap = argparse.ArgumentParser(prog="python -m biomin_screen.pourbaix.c5")
    ap.add_argument("--config", required=True)
    ap.add_argument("--regime", choices=["R-slurry", "R-cell", "both"], default="both")
    args = ap.parse_args(argv)
    if cache.verify():
        raise SystemExit("cache check failed")
    raw, meta = R.load_config(args.config)
    params = inputs.Params(inputs.load_snapshot(raw["params_sha"]))
    prov = R.w4_provenance(meta, params.sha)
    if args.regime in ("R-slurry", "both"):
        summary, outs, baseline, redox = slurry_inputs(raw, meta, params)
        fixture = omega_control.build(params)
        fpath = omega_control.OUT
        fpath.write_text(json.dumps(fixture, indent=1, sort_keys=True) + "\n", encoding="utf-8")
        doc = {"stage": RUN_ID, "generated_utc": provenance.utc_now(), "provenance": prov,
               "params_sha": params.sha, "question": raw["R-slurry"]["question"], "scope": R.SCOPE,
               "decision": "slurry-regime dissolution is judged from Omega_bulk; the Pourbaix diagram is the "
                         "competing-phase and Al-phase baseline and context, with its calcite offset stated",
               "design_axes": summary["design_axes"], "baseline": baseline, "carbon_redox_sensitivity": redox,
               "omega_control_fixture": rel(fpath), "summary": rel(OUT / "slurry_summary.json")}
        ipath = R._dump(OUT / "slurry_c5_inputs.json", doc)
        checks = R.validate([p for p in outs if p.parent.name == "slurry"])
        cpath = R._dump(OUT / "slurry_schema_checks.json", checks)
        allouts = outs + [fpath, ipath, cpath]
        bad = [k for k, v in checks.items() if not v.get("valid")]
        print("slurry regime: %d documents, schema v2 invalid: %d; carbon-redox fraction above edge %.3f to %.3f"
              % (len(checks), len(bad), redox["fraction_above_edge"]["min"], redox["fraction_above_edge"]["max"]))
    if args.regime in ("R-cell", "both"):
        doc, outs = cell_inputs(raw, meta, params)
        checks = R.validate([p for p in outs if p.parent.name == "cell"])
        cpath = R._dump(OUT / "cell_schema_checks.json", checks)
        bad = [k for k, v in checks.items() if not v.get("valid")]
        print("cell regime: %d documents, schema v2 invalid: %d" % (len(checks), len(bad)))
        for r in doc["table"]:
            print("  %-6s %-9s %-24s %s" % (r["phase"], r["sink"], r["governing_route"],
                                          {c: v["verdict"] for c, v in r["by_cathode_class"].items()}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
