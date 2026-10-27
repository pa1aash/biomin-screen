"""Cell-regime supplement: the boehmite window, the corundum and CaCO3 windows confirmed, the remaining
sinks and the budget gaps. Additive: nothing earlier is rewritten.

Thermodynamic question: between which potentials vs Li+/Li are boehmite (gamma-AlOOH), corundum and
CaCO3 at equilibrium against lithiation and against oxidation that releases O2 (and CO2 or H2O), with
the cation taken up by the anion of each specified salt; which route governs each limit; and where a
limit is undetermined, why? Windows are thermodynamic; nothing here is a
rate, and no window says whether a decomposition happens.

Construction (as window.py and cell_window.py):
- Reduction: Li-open grand potential (MP energies, 0 K, MP2020). Boehmite's hull is Li-Al-O-H, from
  the supplement cache (entries local-only). The all-experimental cross-check re-evaluates the
  lithiation reaction with tabulated free energies where every product is tabulated; it governs
  where it exists (reduction rule of data/thresholds.md).
- Oxidation: phase + x LiA -> sink + O2 [+ CO2 | + H2O] + n Li under the janaf, mp and expt
  schemes. Water leaves as H2O(g) at 1 bar (the benchmark's gas standard state); H2O(l) at unit
  activity is a sensitivity, and the water-activity slope is reported, never applied.
- Sinks: Ca(ClO4)2 and, new here, Al(ClO4)3 enter through the exchange M + z LiClO4 -> M(ClO4)z +
  z Li with tabulated enthalpies (solid entropies of the exchange neglected, as every scheme neglects
  solid entropy). The BOB and PCP sinks have no open thermochemistry and stay undetermined.
- Verdicts: oxidation and reduction rules of data/thresholds.md. The expt route governs wherever its
  inputs exist; m_expt (window_margin_expt) belongs to the specified reaction only; any other
  reaction, and every reduction limit, needs its own budget key and is undetermined without one
  (never passes, never falsifies). The margin that would decide each verdict is reported instead.

    uv run python -m biomin_screen.pourbaix.supplement --config results/pourbaix/config/supplement.yaml
"""
import argparse
import json
import math
import sys
import warnings
from dataclasses import asdict

from scipy import constants

from biomin_screen.pourbaix import c5, cache, cell_window, inputs, provenance, salts
from biomin_screen.pourbaix import carbonate_run as R
from biomin_screen.pourbaix import gas as gasmod
from biomin_screen.pourbaix import supplement_cache as sc
from biomin_screen.pourbaix import window as w
from biomin_screen.pourbaix.entries import KJ_PER_MOL_PER_EV, entry_key, material_id
from biomin_screen.pourbaix.paths import POURBAIX_RESULTS, REPO, rel

RUN_ID = "carbonate-supplement"
OUT = sc.SUPP_DIR
K_B_EV = constants.k / constants.e
ORDER = c5.ORDER
SCHEMA_PATH = "configs/results_schema.json"
THRESHOLDS_PATH = "configs/thresholds.yaml"
WINDOW_NAME = {"CaCO3": "CaCO3", "Al2O3": "Al2O3", "AlHO2": "AlOOH"}  # document key per phase formula
AL_EXCHANGE = {"Al(ClO4)3": ("LiClO4", 3, "krivtsov1973_al_clo4_3")}


def _rel(p):
    try:
        return rel(p)
    except ValueError:
        return str(p)


# Keys read beyond the production snapshot: an additive snapshot beside it.
EXTRA_KEYS = ["dfg_h2o_l", "dfh_liclo4", "dfh_ca_clo4_2", "exchange_entropy_bound", "u_tab_dfh_liclo4",
              "electrolyte_water_content"]


def extra_snapshot_path(sha):
    return sc.SUPP_DIR / "inputs" / ("params_%s_extra.json" % sha[:7])


def load_params(sha, extra_keys):
    """Params over the shipped production snapshot plus the shipped additive extra snapshot."""
    base = inputs.load_snapshot(sha)
    path = extra_snapshot_path(sha)
    if not path.is_file():
        raise inputs.SnapshotError("no extra snapshot %s" % path)
    extra = json.loads(path.read_text(encoding="utf-8"))
    if extra["params"]["sha256"] != base["params"]["sha256"]:
        raise inputs.SnapshotError("extra snapshot %s is not for the parameter set of the production snapshot" % path)
    merged = dict(base, entries={**base["entries"], **extra["entries"]}, rows={**base["rows"], **extra["rows"]})
    merged["extra_snapshot"] = {"path": _rel(path), "absent_keys": extra["absent_keys"]}
    return inputs.Params(merged)


# ------------------------------------------------------------------------------- energy books
class D3Book:
    """One scheme's book (cell_window.books) with water, the Al(ClO4)3 exchange and, for expt, the
    tabulated boehmite and lithiation products added. Free energies in eV per formula unit."""

    def __init__(self, scheme, base, params, cfg, T, water_state="gas"):
        self.scheme, self.base, self.params, self.T = scheme, base, params, T
        self.p = {g: float(v) for g, v in cfg["gas_pressure_bar"].items() if g in ("O2", "CO2", "H2O")}
        self.extra = cfg["expt_extra"]
        self.water_state = water_state
        self.exchange = {}
        for salt, (li, n, rid) in AL_EXCHANGE.items():
            dh_salt, u_salt, loc_salt = sc.literature_dfh_kj(rid)
            dh_li, loc_li = salts.dfh_kj(li, T)
            self.exchange[salt] = (li, n, (dh_salt - n * dh_li) / KJ_PER_MOL_PER_EV,
                                   {"salt": loc_salt, "li_salt": loc_li, "u_salt_kJ_per_mol": u_salt,
                                    "temperature_note": "the quoted dfH is a standard enthalpy; its reference temperature "
                                                        "is not printed in the open text and is read as 298.15 K"})

    def energy_book(self):
        b = self.base.base
        return b if isinstance(b, w.EnergyBook) else None

    def water(self):
        T, p = self.T, self.p["H2O"]
        if self.scheme == "expt":
            if self.water_state == "liquid":
                key = self.extra["params"]["H2O_l"]
                return (float(self.params.value(key)) / 1000.0 / KJ_PER_MOL_PER_EV,
                        {"kind": "expt", "source": self.params.cite(key), "state": "H2O(l), unit activity"})
            g = gasmod.formation_free_energy_ev("H2O", T, sc.SUPP_CACHE) + K_B_EV * T * math.log(p)
            return g, {"kind": "expt", "source": gasmod.locator("H2O", T, sc.SUPP_CACHE), "state": "H2O(g)",
                       "pressure_bar": p}
        if self.water_state == "liquid":
            raise ValueError("the liquid-water sensitivity is evaluated in the expt scheme only")
        s = gasmod.entropy_ev_per_K("H2O", T, sc.SUPP_CACHE)
        if self.scheme == "janaf":
            dfh, basis = gasmod.formation_enthalpy_ev("H2O", T, sc.SUPP_CACHE), "dfH from NIST-JANAF H-064"
        else:
            dfh, _ = self.energy_book().solid("H2O")
            basis = "dfH from the MP H2O molecular solid (sublimation not included)"
        return dfh - T * s + K_B_EV * T * math.log(p), {
            "kind": "gas", "scheme": self.scheme, "dfH_eV": dfh, "S_eV_per_K": s, "pressure_bar": p,
            "basis": basis + "; S(T) from NIST-JANAF H-064", "locator": gasmod.locator("H2O", T, sc.SUPP_CACHE)}

    def expt_extra(self, formula):
        if formula in self.extra["elements_at_zero"]:
            return 0.0, {"kind": "reference", "basis": "element in its reference state"}
        if formula in self.extra["params"]:
            key = self.extra["params"][formula]
            if self.params.unit(key) != "J mol^-1":
                raise ValueError(key)
            return float(self.params.value(key)) / 1000.0 / KJ_PER_MOL_PER_EV, {"kind": "expt", "source": self.params.cite(key)}
        if formula in self.extra["janaf"]:
            r = gasmod.row_kj(formula, self.T, sc.SUPP_CACHE)
            return r["dfG_kJ_per_mol"] / KJ_PER_MOL_PER_EV, {"kind": "expt", "source": r["table"]}
        raise w.MissingPhase(formula)

    def __call__(self, formula):
        if formula == "H2O":
            return self.water()
        if formula in self.exchange:
            li, n, dh, loc = self.exchange[formula]
            g_li, meta = self(li)
            return n * g_li + dh, {"kind": "derived", "exchange_dH_eV": dh, "locator": loc, "li_salt": meta,
                                   "basis": "exchange Al + %d %s -> %s + %d Li: %d x G(%s) under this scheme plus the "
                                            "tabulated exchange enthalpy" % (n, li, formula, n, n, li)}
        try:
            return self.base(formula)
        except w.MissingPhase:
            if self.scheme != "expt":
                raise
            return self.expt_extra(formula)


def build_books(cfg, params, T):
    base, ex = cell_window.books(cfg, params, T)
    bks = {s: D3Book(s, b, params, cfg, T) for s, b in base.items()}
    liquid = D3Book("expt", base["expt"], params, cfg, T, water_state="liquid")
    return bks, liquid, ex


# ------------------------------------------------------------------------------------ limits
def reduction(phase, spec):
    """Li-open reduction limit; the boehmite hull comes from the supplement cache."""
    from pymatgen.analysis.phase_diagram import PhaseDiagram

    if spec["cache"] == "supplement":
        man = sc.manifest()
        rec = next(f for f in man["files"] if f["file"] == "mp_entries_cell_%s.json" % spec["lithiation_chemsys"])
        if not sc.path_of(rec).is_file():
            raise SystemExit("the local-only entries %s are absent; run `python -m biomin_screen.pourbaix.supplement_cache fetch`"
                             % rec["location"])
        if cache.sha256_bytes(sc.path_of(rec).read_bytes()) != rec["sha256"]:
            raise SystemExit("hash mismatch of %s" % rec["location"])
        ents = cache.load_entries(rec["file"], sc.path_of(rec).parent)
        excluded = cache.excluded_entries(rec["file"], sc.path_of(rec).parent)
    else:
        ents = cache.load_entries("mp_entries_cell_%s.json" % spec["lithiation_chemsys"])
        excluded = cache.excluded_entries("mp_entries_cell_%s.json" % spec["lithiation_chemsys"])
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        pd = PhaseDiagram(ents)
    pe = [e for e in ents if material_id(e) == spec["material_id"]]
    if not pe:
        raise w.MissingPhase(spec["material_id"])
    red, _, note = w.li_open_limits(pd, pe[0])
    note.update({"chemsys": spec["lithiation_chemsys"], "n_entries": len(ents), "excluded_by_licence": excluded,
                 "entry_id": entry_key(pe[0])})
    polymorphs = sorted(((material_id(e), float(pd.get_e_above_hull(e))) for e in ents
                         if e.composition.reduced_formula == pe[0].composition.reduced_formula), key=lambda x: x[1])
    note["polymorphs_e_above_hull_eV_per_atom"] = polymorphs[:6]
    return red, note


def limit_d(red):
    return {"status": "ok" if red.status == "finite" else "undetermined",
            "value_V": red.value if red.status == "finite" else None, "reaction": red.reaction,
            "reason": red.reason or "", "method": red.method, "delta_g_ev": red.delta_g_ev, "delta_n_li": red.delta_n_li}


def window_limit(d):
    """The schema v3 window_limit fields only."""
    keep = ("status", "value_V", "reaction", "reason", "method", "delta_g_ev", "delta_n_li")
    out = {k: d.get(k) for k in keep if k in d}
    out.setdefault("reason", "")
    out.setdefault("reaction", "")
    return out


def water_sensitivity(cands_expt, liquid_book, phase, spec, salt_id, salt):
    """Per expt candidate that releases water: the onset with H2O(l) at unit activity and the slope
    dE/d ln(a_w) = (n_H2O / n_Li) k T (V per unit of ln a_w)."""
    out = []
    lcands = {c.product: c for c in cell_window.oxidation(phase, spec, salt_id, salt, liquid_book)[1]}
    for c in cands_expt:
        if c.status != "finite" or "H2O" not in c.species:
            continue
        n_w, n_li = c.species["H2O"]["coefficient"], c.delta_n_li
        lc = lcands.get(c.product)
        out.append({"product": c.product, "onset_H2O_g_1bar_V": c.onset_V,
                    "onset_H2O_l_unit_activity_V": lc.onset_V if lc is not None and lc.status == "finite" else None,
                    "slope_V_per_ln_a_w": n_w / n_li * K_B_EV * 298.15,
                    "reading": "a water activity a_w < 1 (trace water) lowers the onset by the slope times |ln a_w|; "
                               "a_w is not a params key, so the shift is not applied"})
    return out


def margin_for(phase, sink, route, reaction, cfg, params):
    """(margin V or None, key list, reason) under thresholds C5c_ox margin_by_route."""
    if route == "expt":
        # the specified reaction: CaCO3 + 2 LiClO4 -> Ca(ClO4)2 + CO2 + 1/2 O2 + 2 Li (matched by phase, sink, product)
        if phase == "CaCO3" and sink == "LiClO4" and "Ca(ClO4)2" in reaction.split("->")[-1]:
            keys = cfg["m_expt"]["keys"]
            vals = [params.entry(k).get("value") for k in keys]
            if all(v is not None for v in vals):
                return sum(float(v) for v in vals), keys, "m_expt of the specified reaction"
            return None, keys, "m_expt key is a gap"
        return None, [], ("no budget key for this expt reaction (thresholds C5c_ox: an expt limit of any other "
                          "reaction or sink needs its own budget key; undetermined, never passes or falsifies)")
    if route == "benchmark-corrected DFT":
        key = cfg["window_margin"]["key"]
        return float(params.value(key)), [key], "m_E (DFT-decided where expt is missing)"
    return None, [], "no governing route"


def ox_verdict(vals, e_max, m, solid_salt):
    if not vals:
        return "inconclusive", "no governing value (undetermined never passes)"
    if m is None:
        return "inconclusive", "governing value exists but its budget key is absent (never passes, never falsifies)"
    v, _ = c5.verdict({"values_V": dict(enumerate(vals))}, e_max, m, solid_salt, "feasible")
    return v, ""


def red_verdict(e_red, e_min, m):
    if e_red is None:
        return "inconclusive", "reduction limit undetermined"
    if m is None:
        return "inconclusive", "no budget key for the reduction limit (thresholds C5c_red; never passes, never falsifies)"
    if e_red <= e_min - m:
        return "feasible", ""
    if e_red > e_min + m:
        return "falsified", ""
    return "inconclusive", "within the margin"


def budget_status(cfg, params):
    out = {}
    for kind, keys in cfg["budget_keys"].items():
        rec = {}
        for k in keys:
            if k in params.snap["entries"]:
                e = params.entry(k)
                rec[k] = {"exists": True, "status": e["status"], "value": e.get("value"), **params.cite(k)}
            else:
                rec[k] = {"exists": False, "status": "absent in the pinned parameter set"}
        usable = [k for k, v in rec.items() if v.get("exists") and v.get("value") is not None]
        out[kind] = {"keys": rec, "status": "found" if usable and len(usable) == len(rec) else "gap"}
    return out


# --------------------------------------------------------------------------------------- run
def run(raw, meta, params):
    cfg = raw["R-cell"]
    T = float(cfg["temperature_K"]["value"])
    if sc.verify() and [b for b in sc.verify() if not b.startswith("absent (local only)")]:
        raise SystemExit("supplement cache check failed: %s" % sc.verify())
    bks, liquid, ex = build_books(cfg, params, T)
    bench = json.loads((POURBAIX_RESULTS / "gas_reference.json").read_text(encoding="utf-8"))
    b2 = {s: x["error_V_per_electron"] for s, x in
          next(b for b in bench["result"]["benchmarks"] if b["id"] == "B2")["schemes"].items()}
    classes = c5.cathode_classes(params)
    sides = ("min", "value", "max")
    e_min_rng = params.range(cfg["E_min"]["key"])
    e_min_lo, e_min_hi = float(e_min_rng["min"]), float(e_min_rng["max"])
    budgets = budget_status(cfg, params)
    red_keys = {k: v for k, v in budgets["reduction"]["keys"].items() if v.get("exists") and v.get("value") is not None}

    phases = {}
    for phase, spec in cfg["phases"].items():
        red, hull = reduction(phase, spec)
        red_dft = limit_d(red)
        red_expt = cell_window.expt_reduction(phase, red, bks["expt"])
        gov_red = red_expt if red_expt["status"] == "ok" else red_dft
        gov_red_route = "expt" if red_expt["status"] == "ok" else "DFT (Li-open)"
        key = next((k for k in red_keys if WINDOW_NAME[phase].lower() in k or spec["name"] in k), None)
        m_red = float(red_keys[key]["value"]) if key else None
        e_red = gov_red["value_V"]
        rv = {s: red_verdict(e_red, x, m_red) for s, x in (("min", e_min_lo), ("max", e_min_hi))}
        reduction_out = {
            "governing_route": gov_red_route, "governing": gov_red, "dft_li_open": red_dft, "expt_crosscheck": red_expt,
            "li_open_hull": hull, "budget_key": key, "margin_V": m_red,
            "verdict": rv["min"][0] if rv["min"][0] == rv["max"][0] else "%s to %s" % (rv["min"][0], rv["max"][0]),
            "verdict_reason": rv["min"][1],
            "margin_that_would_decide_V": (e_min_lo - e_red) if e_red is not None else None,
            "E_cell_min_V": {"min": e_min_lo, "max": e_min_hi, "source": params.cite(cfg["E_min"]["key"])}}

        sinks = {}
        for group, sdefs in (("specified", cfg["salts"]),
                             ("comparator", {k: v for k, v in cfg["comparators"].items() if k != "note"})):
            for salt_id, salt in sdefs.items():
                by, cand_rec = {}, {}
                for s, bk in bks.items():
                    best, cands = cell_window.oxidation(phase, spec, salt_id, salt, bk)
                    by[s] = cell_window.limit_dict(best)
                    cand_rec[s] = [{"product": c.product, "status": c.status, "onset_V": c.onset_V, "reaction": c.reaction,
                                    "reason": c.reason,
                                    "species": {f: {k: v for k, v in sp.items() if k in (
                                        "coefficient", "G_eV", "kind", "material_id", "scheme", "source", "state",
                                        "exchange_dH_eV", "locator")} for f, sp in c.species.items()}} for c in cands]
                    if s == "expt":
                        expt_cands = cands
                gov, corr = c5.governing(by, b2)
                vals = list(gov["values_V"].values())
                m, mkeys, mwhy = margin_for(phase, salt_id, gov["route"], gov["reaction"], cfg, params)
                rec = {"group": group, "sink_kind": "solid_salt", "products": salt["products"][spec["cation"]],
                       "oxidation_by_scheme": by, "benchmark_corrected_V": corr, "governing_route": gov["route"],
                       "governing_V": gov["values_V"], "reaction": gov["reaction"], "reason": gov.get("reason", ""),
                       "status": "ok" if vals else "undetermined", "margin_V": m, "margin_keys": mkeys,
                       "margin_reason": mwhy, "candidates": cand_rec,
                       "water_sensitivity": water_sensitivity(expt_cands, liquid, phase, spec, salt_id, salt)
                       if "H2O" in spec["gases"] else []}
                if group == "specified":
                    per = {}
                    for cname, c in classes.items():
                        at = {sd: ox_verdict(vals, c["E_cell_max_V"][sd], m, True) for sd in sides}
                        ox = sorted({v for v, _ in at.values()}, key=ORDER.index)
                        comb = {sd: max([at[sd][0], reduction_out["verdict"].split(" to ")[-1]], key=ORDER.index) for sd in sides}
                        per[cname] = {"E_cell_max_V": c["E_cell_max_V"], "key": c.get("key"), "rows": c["rows"],
                                      "oxidation_verdict_at": {sd: at[sd][0] for sd in sides},
                                      "oxidation_verdict": ox[0] if len(ox) == 1 else "%s to %s" % (ox[0], ox[-1]),
                                      "verdict_at": comb,
                                      "reason": next((r for _, r in at.values() if r), ""),
                                      "margin_that_would_decide_V": (min(abs(c["E_cell_max_V"][sd] - v) for sd in ("min", "max")
                                                                         for v in vals) if vals else None)}
                    rec["by_cathode_class"] = per
                sinks[salt_id] = rec
        solv_gap = budgets["solvated"]["status"] == "gap"
        sinks["solvated"] = {"group": "specified", "sink_kind": "solvated", "status": "undetermined",
                             "governing_route": None, "governing_V": {},
                             "reason": cfg["solvated"]["reason"] if solv_gap else "keys present; not evaluated here",
                             "missing_keys": [params.cite(k) for k in cfg["solvated"]["keys"]],
                             "by_cathode_class": {cn: {"E_cell_max_V": c["E_cell_max_V"], "oxidation_verdict": "inconclusive",
                                                       "verdict_at": {sd: max(["inconclusive", reduction_out["verdict"].split(" to ")[-1]],
                                                                              key=ORDER.index) for sd in sides},
                                                       "reason": "undetermined never passes"} for cn, c in classes.items()}}
        chem = {}
        if phase == "CaCO3":
            for s, bk in bks.items():
                dg, text = w.chemical_decomposition(bk, "CaCO3", ["CaO", "CO2"])
                chem[s] = {"reaction": text, "delta_g_ev": dg}
        if phase == "AlHO2":
            for s, bk in list(bks.items()) + [("expt_H2O_l", liquid)]:
                dg, text = w.chemical_decomposition(bk, "AlHO2", ["Al2O3", "H2O"])
                n_w = 0.5
                thr = math.exp(-dg / (n_w * K_B_EV * T))
                chem[s] = {"reaction": text, "delta_g_ev_per_AlOOH": dg,
                           ("a_w_below_which_dehydration_is_favoured" if s == "expt_H2O_l" else
                            "p_H2O_bar_below_which_dehydration_is_favoured"): thr}
            chem["question"] = ("is boehmite stable against dehydration to corundum, 2 AlOOH -> Al2O3 + H2O, without "
                                "electrochemistry? Delta_G at the water standard state, and the water pressure (or "
                                "activity) below which dehydration is favoured: thermodynamics only, no rate")
        phases[phase] = {"name": spec["name"], "material_id": spec["material_id"], "role": spec["role"],
                         "identification": spec.get("identification"), "reduction": reduction_out, "by_sink": sinks,
                         "chemical_decomposition": chem}
    return phases, budgets, classes, b2, ex, bks


def compare_previous(phases, cfg):
    """The CaCO3 and corundum values against the scheme table of the C5 run (confirmation)."""
    prev = json.loads((REPO / cfg["previous"]["scheme_table"]).read_text(encoding="utf-8"))
    out = []
    for r in prev["table"]:
        ph = r["phase"]
        if ph not in phases or r["sink"] not in phases[ph]["by_sink"]:
            continue
        now = phases[ph]["by_sink"][r["sink"]]
        for s in ("expt", "janaf", "mp"):
            a = r.get("%s_V" % s)
            b = (now.get("oxidation_by_scheme") or {}).get(s, {}).get("value_V")
            out.append({"phase": ph, "sink": r["sink"], "scheme": s, "c5_V": a, "supplement_V": b,
                        "abs_diff_V": abs(a - b) if a is not None and b is not None else None,
                        "status_change": (a is None) != (b is None)})
    red = prev["phases"]
    for ph in ("CaCO3", "Al2O3"):
        a = red[ph]["reduction"]["value_V"]
        b = phases[ph]["reduction"]["dft_li_open"]["value_V"]
        out.append({"phase": ph, "sink": "reduction (Li-open)", "scheme": "DFT", "c5_V": a, "supplement_V": b,
                    "abs_diff_V": abs(a - b) if a is not None and b is not None else None, "status_change": False})
    return out


def sink_attempts(params):
    """Attempts to find thermochemistry for the remaining sinks (1b), with the earlier routes."""
    prior = {r["formula"]: r for r in cell_window.sink_attempts(params)}
    date = "2026-10-19"
    out = []
    al = dict(prior["Al(ClO4)3"])
    al["routes"] = list(al["routes"]) + [
        {"route": "Krivtsov, Nikitina, Rosolovskii, Bull. Acad. Sci. USSR Div. Chem. Sci. 22, 2560 (1973), "
                  "doi:10.1007/BF00926423, free abstract page (Conclusions)", "date": date,
         "result": "dfH of anhydrous Al(ClO4)3 printed; full text not open (no dfG, no S, reference temperature not printed)"},
        {"route": "Glushko, Thermal Constants of Substances (TKV) online, chem.msu.ru, entry 1109", "date": date,
         "result": "aqueous-solution rows only (water standard state); no crystalline row; not used (an aqueous value is "
                   "not a solid-salt sink)"},
        {"route": "TKV entries 1110-1112 (hydrates 6, 9, 15 H2O)", "date": date, "result": "melting points only"},
        {"route": "NBS Technical Note 270-3 (1968), Table 29 (Al), pp. 209-211, rendered and read", "date": date,
         "result": "no Al(ClO4)3 row"},
        {"route": "OpenAlex search 'aluminum perchlorate enthalpy' and the citing works", "date": date,
         "result": "only the 1973 paper; citing works not open and carry no new value"}]
    al["status"] = "dfH only (exchange route); single fetched source, not a params key"
    al["value"] = {"dfH_kJ_per_mol": sc.literature_dfh_kj("krivtsov1973_al_clo4_3")[0],
                   "u_kJ_per_mol": sc.literature_dfh_kj("krivtsov1973_al_clo4_3")[1],
                   "locator": sc.literature_dfh_kj("krivtsov1973_al_clo4_3")[2]}
    out.append(al)
    common = [
        {"route": "TKV online (chem.msu.ru) formula search", "date": date, "result": "no entry"},
        {"route": "NIST Chemistry WebBook formula search (C4BLiO8, C8LiN5, C8N5)", "date": date, "result": "formula not found"},
        {"route": "OpenAlex keyword searches (enthalpy of formation, calorimetry)", "date": date,
         "result": "electrolyte, structure and synthesis papers only; no thermochemistry"},
        {"route": "Semantic Scholar API", "date": date, "result": "HTTP 429; not completed"}]
    for formula, salt, name in (("CaB2C8O16", "LiBOB", "Ca(BOB)2"), ("AlB3C12O24", "LiBOB", "Al(BOB)3"),
                                ("Ca(C8N5)2", "LiPCP", "Ca(PCP)2"), ("Al(C8N5)3", "LiPCP", "Al(PCP)3")):
        r = dict(prior[formula])
        r["name"] = name
        r["routes"] = list(r["routes"]) + common + [
            {"route": "LiBOB calorimetry papers (Adv. Mater. Res. 455-456, 947; J. Electrochem. Soc. 169, 070523; "
                      "Thermochim. Acta 2007)" if salt == "LiBOB" else
                      "LiPCP/NaPCP electrolyte papers (e.g. PMC5220368); DETHERM lists a different cyanocarbon anion",
             "date": date, "result": "decomposition heats or hydrolysis energies only; no dfH of the Li salt or the sink"}]
        r["status"] = "undetermined"
        out.append(r)
    return out


# ------------------------------------------------------------------------------------ outputs
def provenance_v3(meta, params, raw):
    th = REPO / THRESHOLDS_PATH
    return {"git_sha": provenance.code_version(), "git_dirty": False, "config_hash": meta["config_hash"],
            "config_file": meta["path"], "config_file_hash": meta["file_hash"], "contract_sha": None,
            "params_sha": params.sha, "params_tag": None, "params_sha_at_tag": None,
            "thresholds_file": THRESHOLDS_PATH, "thresholds_hash": cache.sha256_bytes(th.read_bytes()),
            "thresholds_source_sha": None, "schema_sha": None,
            "run_label": "supplement"}


def lane_ext(params, meta):
    man = sc.manifest()
    janaf = sorted({f["request"]["url"] for f in cache.manifest()["files"] if f["kind"] == "janaf_table"} |
                   {f["request"]["url"] for f in man["files"] if f["kind"] == "janaf_table"})
    sources = [
        {"what": "Materials Project database %s (mp-api), GGA/GGA+U with MP2020 corrections; CC BY 4.0; Jain et al., "
                 "APL Materials 1, 011002 (2013), doi:10.1063/1.4812323; GNoME (CC BY-NC) excluded"
                 % cache.manifest()["mp_database_version"],
         "files": "results/pourbaix/cache/ (production, read only) and results/pourbaix/supplement/cache/ (Li-Al-O-H)"},
        {"what": "NIST-JANAF Thermochemical Tables", "urls": janaf},
        {"what": "NBS tables 1982 (Wagman et al., J. Phys. Chem. Ref. Data 11, Suppl. 2), OCR of the scanned pages",
         "files": "results/pourbaix/cache/nbs1982_ocr.json"},
        {"what": "Krivtsov, Nikitina, Rosolovskii (1973), dfH of anhydrous Al(ClO4)3, doi:10.1007/BF00926423 "
                 "(sourced value, not yet a params key)",
         "files": "results/pourbaix/supplement/cache/lit_krivtsov1973_al_clo4_3.json"},
        {"what": "data/params.yaml, pinned parameter snapshot (keys cited per value)", "params_sha": params.sha}]
    return {"stage": RUN_ID, "scope": R.SCOPE, "config": meta["path"], "supplement": True, "sources": sources,
            "provenance_pourbaix": {"cache_hash": cache.cache_hash(), "mp_database_version": cache.manifest()["mp_database_version"],
                                    "supplement_cache_hash": sc.cache_hash(),
                                    "supplement_local_only": [{k: f[k] for k in ("file", "location", "sha256", "bytes", "n",
                                                                                   "licences")} for f in man["files"]
                                                              if f.get("local_only")],
                                    "library_versions": provenance.lib_versions(),
                                    "params_snapshot": rel(inputs.snapshot_path(params.sha)),
                                    "params_extra_snapshot": params.snap.get("extra_snapshot"),
                                    "params_blob": params.snap["params"]["blob"]}}


def documents(phases, cfg, prov, ext, b2, T):
    files = []
    schemes = {"expt": {"role": "governing", "benchmark_error_V": None,
                        "source": "governs wherever its inputs exist"}}
    for s in ("janaf", "mp"):
        schemes[s] = {"role": "comparator", "benchmark_error_V": float(b2[s]),
                      "source": "results/pourbaix/gas_reference.json B2 (per electron, CO2-releasing reactions)"}
    for sink in list(cfg["salts"]) + ["solvated"]:
        windows = {}
        for phase, po in phases.items():
            rec = po["by_sink"][sink]
            red = po["reduction"]
            if sink == "solvated":
                und = {"status": "undetermined", "value_V": None, "reaction": "", "reason": rec["reason"]}
                by = {s: dict(und) for s in cfg["schemes"]}
                ox = dict(und)
            else:
                by = {s: window_limit(v) for s, v in rec["oxidation_by_scheme"].items()}
                if rec["status"] == "ok":
                    route = rec["governing_route"]
                    vals = rec["governing_V"]
                    v = vals.get("expt") if route == "expt" else min(vals.values())
                    ox = {"status": "ok", "value_V": v, "reaction": rec["reaction"], "reason": "",
                          "method": "governing route: %s" % route}
                else:
                    ox = {"status": "undetermined", "value_V": None, "reaction": rec["reaction"] or "",
                          "reason": rec["reason"] or "no governing route", "method": "governing route: none"}
            windows[WINDOW_NAME[phase]] = {
                "material_id": po["material_id"], "reduction": window_limit(red["governing"]), "oxidation": window_limit(ox),
                "oxidation_by_scheme": by,
                "reduction_by_scheme": {"DFT (Li-open)": window_limit(red["dft_li_open"]),
                                        "expt": window_limit(red["expt_crosscheck"])},
                "notes": ["%s (%s); reduction governed by %s" % (po["name"], po["material_id"], red["governing_route"]),
                          "oxidation: the governing route, not the lowest over the schemes",
                          "verdicts by cathode class, margins and budget gaps are in extensions.pourbaix"]}
        doc = {"schema_version": "3", "mock": False, "generated_utc": provenance.utc_now(), "provenance": prov,
               "stability": {"R-cell": {
                   "kind": "window", "reference_electrode": "Li+/Li", "temperature_K": T,
                   "convention": "E_window = Delta_G_r/(Delta_n_Li F_c); E_ox = min over Delta_n_Li > 0",
                   "sink_assumption": {"active": sink, "kind": "solvated" if sink == "solvated" else "solid_salt",
                                       "statement": (cfg["solvated"]["reason"] if sink == "solvated" else
                                                     "The cation leaves as the solid salt of the anion of %s; Li from %s is "
                                                     "plated at the Li+/Li reference. A solid-salt limit is an upper bound on "
                                                     "the true onset." % (sink, cfg["salts"][sink]["li_source"])),
                                       "switch": "one document per specified salt"},
                   "windows": windows, "schemes": schemes}},
               "extensions": {"pourbaix": {**ext, "question": cfg["question"], "sink": sink,
                                        "verdicts": {WINDOW_NAME[ph]: {"reduction": po["reduction"]["verdict"],
                                                                       "reduction_reason": po["reduction"]["verdict_reason"],
                                                                       "by_cathode_class": po["by_sink"][sink]["by_cathode_class"],
                                                                       "margin_V": po["by_sink"][sink].get("margin_V"),
                                                                       "margin_reason": po["by_sink"][sink].get("margin_reason",
                                                                                                               po["by_sink"][sink].get("reason"))}
                                                     for ph, po in phases.items()}}}}
        files.append(R._dump(OUT / "cell" / ("%s.json" % sink), doc))
    return files


def validate_v3(paths):
    return {_rel(p): provenance.validate_against(SCHEMA_PATH, json.loads(p.read_text(encoding="utf-8")))
            for p in paths}


def main(argv=None):
    ap = argparse.ArgumentParser(prog="python -m biomin_screen.pourbaix.supplement")
    ap.add_argument("--config", required=True)
    ap.add_argument("--trial", default=None, help="write to this directory instead of results/pourbaix/supplement")
    args = ap.parse_args(argv)
    global OUT
    if args.trial:
        from pathlib import Path
        OUT = Path(args.trial)
    if cache.verify():
        raise SystemExit("production cache check failed")
    raw, meta = R.load_config(args.config)
    keys = EXTRA_KEYS + [k for ks in raw["R-cell"]["budget_keys"].values() for k in ks]
    params = load_params(raw["params_sha"], keys)
    phases, budgets, classes, b2, ex, bks = run(raw, meta, params)
    cfg = raw["R-cell"]
    T = float(cfg["temperature_K"]["value"])
    prov = provenance_v3(meta, params, raw)
    ext = lane_ext(params, meta)
    docs = documents(phases, cfg, prov, ext, b2, T)
    checks = validate_v3(docs)
    attempts = sink_attempts(params)
    al_dfh = sc.literature_dfh_kj("krivtsov1973_al_clo4_3")
    sink_table = []
    for ph, po in phases.items():
        for sink, rec in po["by_sink"].items():
            if rec["group"] != "specified":
                continue
            sink_table.append({"phase": WINDOW_NAME[ph], "sink": sink, "status": "computed" if rec["status"] == "ok" else "undetermined",
                               "governing_route": rec.get("governing_route"), "governing_V": rec.get("governing_V"),
                               "margin_V": rec.get("margin_V"), "reason": rec.get("reason") or rec.get("margin_reason", ""),
                               "verdict_by_class": {c: v.get("verdict_at") for c, v in rec["by_cathode_class"].items()}})
    summary = {
        "stage": RUN_ID, "generated_utc": provenance.utc_now(), "provenance": prov, "extensions": ext,
        "question": cfg["question"], "scope": R.SCOPE, "temperature_K": T,
        "rule": "oxidation and reduction rules of data/thresholds.md: expt governs wherever its inputs exist; m_expt belongs to "
                "the specified reaction; any other reaction and every reduction limit needs its own budget key and is "
                "undetermined without one (never passes, never falsifies)",
        "params": {"params_sha": params.sha},
        "budgets": budgets, "cathode_classes": classes,
        "E_cell_min": params.cite(cfg["E_min"]["key"]),
        "water": cfg["water"], "phases": phases, "sink_table": sink_table, "sink_thermo_attempts": attempts,
        "confirmation_vs_c5": compare_previous(phases, cfg),
        "sourced_values_not_params_keys": [{
            "formula": "Al(ClO4)3", "state": "anhydrous crystalline solid", "quantity": "dfH (standard)",
            "dfH_kJ_per_mol": al_dfh[0], "u_kJ_per_mol": al_dfh[1], "doi": "10.1007/BF00926423",
            "citation": "N. V. Krivtsov, Z. K. Nikitina, V. Ya. Rosolovskii, Bull. Acad. Sci. USSR Div. Chem. Sci. 22(11), "
                        "2560-2561 (1973)",
            "locator": al_dfh[2], "cache_file": _rel(sc.SUPP_CACHE / "lit_krivtsov1973_al_clo4_3.json"),
            "converted_with": "thermochemical calorie (scipy.constants.calorie, J per cal = kJ per kcal)",
            "status": "sourced (one fetched value); not yet a params key",
            "used_for": "the Al(ClO4)3 sink of corundum and boehmite through the exchange Al + 3 LiClO4 -> Al(ClO4)3 + 3 Li",
            "limits": ["single source, seen in the free abstract only (full text not open)",
                       "reference temperature not printed; read as 298.15 K",
                       "no dfG or S: the exchange entropy is neglected and has no bound key for Al",
                       "the Al onsets it gives have no budget key and decide no verdict"],
            "key_request": "add dfh_al_clo4_3 (and its uncertainty) from doi:10.1007/BF00926423, and a budget key "
                              "for the expt route of the Al(ClO4)3 sink if the onsets are to decide a verdict"}],
        "boehmite_dehydration": {
            "reaction": "2 AlOOH -> Al2O3 + H2O (no electrochemistry)",
            "reading": "a threshold, not a verdict: dehydration of boehmite to corundum is favoured below the water "
                       "partial pressure (or liquid-referenced activity) given per scheme; the governing value is the expt "
                       "route. The water activity in the electrolyte is not a sourced key (electrolyte_water_content is a "
                       "mass fraction and gives no activity without a solvation model), so the threshold is not compared "
                       "with any state of the cell.",
            "by_scheme": phases["AlHO2"]["chemical_decomposition"]},
        "exchange_tables": {**{k: {"li_salt": v[0], "count": v[1], "dH_eV": v[2], "locators": v[3]} for k, v in ex.items()},
                            **{k: {"li_salt": v[0], "count": v[1], "dH_eV": v[2], "locators": v[3]}
                               for k, v in bks["expt"].exchange.items()}},
        "limitations": [
            "The electrolyte's own anodic limit (anion or solvent oxidation) is not assessed; it may lie below every "
            "limit here.",
            "Solid entropies are neglected in every scheme; for the Al(ClO4)3 exchange there is no entropy bound key "
            "(the exchange_entropy_bound key is stated for Ca(ClO4)2).",
            "The Al(ClO4)3 dfH is one fetched value from a free abstract page; it is not a params key, and its reference "
            "temperature is not printed (read as 298.15 K).",
            "Water released by boehmite is taken at 1 bar; trace water in the electrolyte lowers the onsets "
            "(water_sensitivity), by an amount that needs a water activity that is not a params key.",
            "Reduction limits use 0 K energies (Li-open); the expt cross-check governs where every product is tabulated."],
        "documents": [_rel(p) for p in docs]}
    spath = R._dump(OUT / "cell_supplement_summary.json", summary)
    cpath = R._dump(OUT / "cell_schema_checks.json", checks)
    bad = [k for k, v in checks.items() if not v.get("valid")]
    print("cell supplement: %d documents, schema v3 invalid: %d" % (len(docs), len(bad)))
    for r in sink_table:
        print("  %-6s %-9s %-12s %-6s %s" % (r["phase"], r["sink"], r["status"], r["governing_route"],
                                            {c: v for c, v in r["verdict_by_class"].items()}))
    for ph, po in phases.items():
        rd = po["reduction"]
        print("  %-6s reduction %s %.3f V (%s), verdict %s" % (WINDOW_NAME[ph], rd["governing_route"],
                                                              rd["governing"]["value_V"] or float("nan"),
                                                              rd["governing"]["reaction"], rd["verdict"]))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
