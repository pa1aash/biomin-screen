"""Final tier-1 ladder (v3) with the specified margins (block margins_v6 of the thresholds) and per-class verdicts.

    uv run python -m biomin_screen.pourbaix.ladder run       # writes results/pourbaix/ladder/

Margins are read from the generated entry margins_v6 of the shipped data/thresholds.md (never typed); the sha256 of the
file and of the extracted block are recorded, and the block is copied to margins_v6_block.yaml. Rule per reaction and
class: FALSIFIED if E_ub + m < inf(C); PASS only if E_lb >= sup(C) + m (E_lb is pending, so never); an incomplete budget or a
missing margin is undetermined; otherwise inconclusive.
"""
import argparse
import csv
import hashlib
import json
import textwrap

import yaml

from biomin_screen.pourbaix import oxidation_ladder as k
from biomin_screen.pourbaix import provenance
from biomin_screen.pourbaix.paths import rel

RUN_ID = "ladder"
OUT = k.POURBAIX_RESULTS / "ladder"
W51 = k.POURBAIX_RESULTS / "benchmark"
THRESHOLDS_FILE = "data/thresholds.md"
BEGIN, END = "# BEGIN generated margins_v6", "# END generated margins_v6"

COLUMNS = ["phase", "framing", "stage", "reaction_id", "route", "E_ub_V", "E_lb_V", "margin_V", "budget_status",
           "benchmark_status", "k1_class_lfp", "k1_class_42_43", "k1_class_44_45", "k1_verdict", "row_ids", "notes"]
CLASS_COLS = (("k1_class_lfp", "C_lo"), ("k1_class_42_43", "C_mid"), ("k1_class_44_45", "C_hi"))
PENDING = "pending"
ACP_REF_ROUTE = "crystalline reference row (beta-TCP value, not ACP)"
ACP_REF_NOTE = ("reference only: the crystalline beta-TCP value kept beside ACP; ACP itself is the amorphous slurry-stage row, "
                "undetermined because no amorphous thermochemistry exists")


def read_block(path=THRESHOLDS_FILE):
    """The margins_v6 entry as read-only data, with the sha256 of its source file and of the block."""
    raw = (k.REPO / path).read_bytes()
    lines = raw.decode("utf-8").splitlines()
    i0 = next(i for i, ln in enumerate(lines) if BEGIN in ln)
    i1 = next(i for i, ln in enumerate(lines) if END in ln)
    body = textwrap.dedent("\n".join(lines[i0 + 1:i1]))
    doc = yaml.safe_load(body)["margins_v6"]
    meta = {"file": path, "file_sha256": hashlib.sha256(raw).hexdigest(),
            "block_sha256": hashlib.sha256(body.encode("utf-8")).hexdigest()}
    return doc, body, meta


def cutoffs(block):
    """{class key: (inf, sup)} from the block's cutoff_classes."""
    cc = block["cutoff_classes"]
    return {key: (min(cc[key]["E_c_V"]), max(cc[key]["E_c_V"])) for _, key in CLASS_COLS}


def class_verdict(e_ub, m, complete, inf, sup, e_lb=None):
    """Specified rule for one reaction at one class."""
    if e_ub is None or m is None or not complete:
        return "undetermined"
    if e_ub + m < inf:
        return "falsified"
    if e_lb is not None and e_lb >= sup + m:
        return "pass"
    return "inconclusive"


def overall(classes):
    """Row verdict from the three class verdicts."""
    if all(c == "falsified" for c in classes):
        return "falsified"
    if any(c == "pass" for c in classes):
        return "pass"
    if any(c == "undetermined" for c in classes) and not any(c == "falsified" for c in classes):
        return "undetermined"
    return "inconclusive"


def gate_incomplete(classes, complete):
    """A row whose budget is incomplete cannot falsify: its falsified classes read undetermined."""
    return classes if complete else ["undetermined" if c == "falsified" else c for c in classes]


def aggregate_class(per_reaction):
    """Class verdict of a phase-framing: falsified iff some reaction is falsified. A reaction whose budget is
    incomplete is never falsified (gate_incomplete) and never rescues the phase; an undetermined one blocks the rest."""
    if any(v == "falsified" for v in per_reaction):
        return "falsified"
    if any(v == "undetermined" for v in per_reaction):
        return "undetermined"
    if per_reaction and all(v == "pass" for v in per_reaction):
        return "pass"
    return "inconclusive"


def _read_v2():
    lines = [ln for ln in (W51 / "ladder_v2.csv").read_text(encoding="utf-8").splitlines() if not ln.startswith("#")]
    return list(csv.DictReader(lines))


def _fnum(x):
    return None if x in ("", None) else float(x)


def _fmt(x):
    return "" if x is None else "%.4f" % x


F_KJ_PER_V = 96.485332


def direct_correction(block):
    """The block's direct Ca(PO3)2 glass-to-crystal correction entry (stored as ca_po3_2_glass_correction)."""
    m = block["m_K1_amorphous"]
    return m["ca_po3_2_glass_correction"] if "ca_po3_2_glass_correction" in m else m["decision_b"]


def staged_decision_b(block, e, role, coef=1.0):
    """The staged Ca(PO3)2 crystal (analogue vitrification enthalpy) is replaced by the direct
    glass-to-crystal value, as the block does for the Ca(PO3)2 crystal reference row. coef is the Ca(PO3)2 stoichiometry of the route. role 'reactant' raises E_ub with the more
    stable crystal, 'product' lowers it. Returns (E_ub, m, text)."""
    rb = direct_correction(block)
    sp = json.loads((W51 / "benchmark.json").read_text(encoding="utf-8"))["staged_products"]["values"]["Ca(PO3)2"]
    d_corr = rb["correction_kJ"] - sp["h_vit_kJ"]
    new_u = sp["u_kJ"] - sp["u_vit_kJ"] + rb["u_correction_kJ"] - rb["u_glass_kJ"]
    t = e["terms"]
    n_e = e["n_e"]
    m = (t["tabulated"] - coef * (sp["u_kJ"] - new_u) + t["entropy_bound"]) / (n_e * F_KJ_PER_V)
    e_ub = e["E_ub"] + coef * (d_corr if role == "reactant" else -d_corr) / (n_e * F_KJ_PER_V)
    return e_ub, m, ("direct glass-to-crystal correction applied to the staged Ca(PO3)2 crystal: the direct value %.2f +- %.2f kJ/mol replaces the "
                     "analogue %.2f +- %.2f kJ/mol; E_ub %.4f -> %.4f V, m %.4f -> %.4f V (block v6 value kept in the block copy)"
                     % (rb["correction_kJ"], rb["u_correction_kJ"], sp["h_vit_kJ"], sp["u_vit_kJ"], e["E_ub"], e_ub, e["m"], m))


def _reaction_rows(block):
    """{(phase, framing): [row dicts]} from m_K1.rows, with the direct-correction crystal row for Ca(PO3)2."""
    rb = direct_correction(block)["crystalline_reference_row"]
    out = {}
    for r in block["m_K1"]["rows"]:
        e = {"id": r["reaction"], "text": r["text"], "sink": r["sink"], "status": r["status"],
             "E_ub": r.get("E_ub_V"), "m": r.get("m_V"), "reason": r.get("reason", ""),
             "m_partial": r.get("m_V_partial"), "adopted": "", "n_e": r.get("n_e"), "terms": r.get("terms_kJ")}
        if r["phase"].startswith("Ca(PO3)2") and r["framing"] == "crystalline" and r["reaction"] == "r1":
            assert abs(e["E_ub"] - rb["was"]["E_ub_V"]) < 5e-4 and abs(e["m"] - rb["was"]["m_V"]) < 5e-4
            e["E_ub"], e["m"] = rb["E_ub_V"], rb["m_V"]
            e["adopted"] = ("direct Ca(PO3)2 glass-to-crystal value %.2f +- %.2f kJ/mol, E_ub %.4f -> %.4f V, "
                            "m %.4f -> %.4f V" % (direct_correction(block)["correction_kJ"],
                                                  direct_correction(block)["u_correction_kJ"],
                                                  rb["was"]["E_ub_V"], rb["E_ub_V"], rb["was"]["m_V"], rb["m_V"]))
        if r["phase"] == "Ca2P2O7" and r["framing"] == "crystalline" and r["reaction"] == "r1s":
            e["E_ub"], e["m"], e["adopted"] = staged_decision_b(block, e, "product")
        if r["phase"] == "brushite" and r["framing"] == "crystalline" and r["reaction"] == "r1s":
            e["E_ub"], e["m"], e["adopted"] = staged_decision_b(block, e, "product", coef=0.5)
        out.setdefault((r["phase"], r["framing"]), []).append(e)
    return out


def _bound_note(block, phase):
    for r in block["tier1_amorphous_by_bound"]:
        if r["phase"] == phase:
            c = r["classes"]
            return c if isinstance(c, str) else "; ".join("%s %s" % (a, b) for a, b in c.items())
    return None


SENS_EDGE_V = 4.0


def build(block, lfp_edge=None):
    cut = cutoffs(block)
    if lfp_edge is not None:
        cut["C_lo"] = (lfp_edge, lfp_edge)
    rx = _reaction_rows(block)
    v2 = _read_v2()
    rows = []
    for v in v2:
        if v["row_type"] == "conversion":
            rows.append(_conversion_row(v))
            continue
        if v["row_type"] == "matrix":
            rows.append(_flat(v, "matrix (tier 2 only)", "undetermined", "matrix-risk flag; never gating alone; "
                              "no tier 1 number for a polymer", "tier 2 gap"))
            continue
        phase, framing, stage = v["phase"], v["framing"], v["stage"]
        if v["phase"] == "Ca-modified aluminophosphate":
            rows.append(_flat(v, "not run", "undetermined", "not run: no Ca-Al phosphate thermochemistry", "not run"))
            continue
        reactions = rx.get((phase, framing), [])
        rows += _phase_rows(block, cut, v, reactions)
    return rows


def _flat(v, route, verdict, note, budget):
    cls = [verdict] * 3
    return {"phase": v["phase"], "framing": v["framing"] or "", "stage": v["stage"] or "", "reaction_id": "-",
            "route": route, "E_ub_V": "", "E_lb_V": PENDING, "margin_V": "", "budget_status": budget,
            "benchmark_status": "", "k1_class_lfp": cls[0], "k1_class_42_43": cls[1], "k1_class_44_45": cls[2],
            "k1_verdict": verdict, "row_ids": _ids(v), "notes": note}


def _ids(v):
    return "benchmark/ladder_v2.csv:%s|%s|%s|%s" % (v["row_type"], v["phase"], v["framing"], v["stage"])


def _conversion_row(v):
    return {"phase": v["phase"], "framing": "", "stage": "conversion", "reaction_id": v["step"], "route": "conversion step",
            "E_ub_V": "", "E_lb_V": "", "margin_V": "", "budget_status": "n/a (threshold, not an oxidation)",
            "benchmark_status": "", "k1_class_lfp": "n/a", "k1_class_42_43": "n/a", "k1_class_44_45": "n/a",
            "k1_verdict": "n/a", "row_ids": _ids(v),
            "notes": "a_w*=%s (range %s to %s); %s; lit T: %s" % (v["a_w_star"] or "undetermined", v["a_w_star_lo"] or "-",
                                                                  v["a_w_star_hi"] or "-", v["note"] or "no K1 verdict",
                                                                  v["lit_conversion_T"] or "pending")}


def _phase_rows(block, cut, v, reactions):
    phase, framing, stage = v["phase"], v["framing"], v["stage"]
    bench = v["dft_label"]
    if v["dft_mp_V"] or v["dft_janaf_V"]:
        bench += "; comparator only: MP %s V, JANAF %s V" % (v["dft_mp_V"] or "-", v["dft_janaf_V"] or "-")
    out, per = [], []
    acp_ref = phase == "ACP" and framing == "crystalline"
    glass_rule = framing == "amorphous"
    note_base = v["label"]
    if not reactions:
        if framing == "amorphous":
            reason = "amorphous margin symbolic (m_am = m_cr + u(DeltaG_g->c)/(n_e F), correction a gap): row undetermined"
            if "not specified" in v["label"]:
                reason = "amorphous framing not specified: undetermined"
            bound = _bound_note(block, phase)
            if bound:
                reason += "; block by-bound reading (margin symbolic, not a verdict basis): " + bound
        else:
            reason = "no specified reaction for this phase"
        if phase == "ACP":
            reason = "no amorphous ACP thermochemistry exists (single-paper grade-D solubility products only): ACP undetermined; " + reason
        r = _flat(v, "gap", "undetermined", reason + "; " + note_base, "gap")
        r["framing"], r["stage"], r["benchmark_status"] = framing, stage, bench
        return [r]
    for e in reactions:
        complete = e["status"] == "set"
        cls = [class_verdict(e["E_ub"], e["m"], complete, *cut[key]) for _, key in CLASS_COLS]
        cls = gate_incomplete(cls, complete)
        per.append(cls)
        note = []
        if acp_ref:
            note.append(ACP_REF_NOTE)
        if e["adopted"]:
            note.append(e["adopted"])
        if not complete:
            note.append("budget incomplete: " + e["reason"])
            if e["m_partial"] is not None:
                note.append("partial margin %.4f V (not a verdict basis)" % e["m_partial"])
        note.append(e["text"])
        route = "glass margin rule (own glass data)" if glass_rule else "expt route, m_K1, " + e["sink"]
        if acp_ref:
            route = ACP_REF_ROUTE + "; " + route
        out.append({"phase": phase, "framing": framing, "stage": stage, "reaction_id": e["id"], "route": route,
                    "E_ub_V": _fmt(e["E_ub"]), "E_lb_V": PENDING, "margin_V": _fmt(e["m"] if complete else None),
                    "budget_status": "complete" if complete else "incomplete" if e["E_ub"] is not None else "symbolic: " + e["reason"],
                    "benchmark_status": bench, "k1_class_lfp": cls[0], "k1_class_42_43": cls[1], "k1_class_44_45": cls[2],
                    "k1_verdict": overall(cls), "row_ids": _ids(v), "notes": "; ".join(note)})
    # aggregate row for the phase-framing
    agg = [aggregate_class([p[i] for p in per]) for i in range(3)]
    complete_all = all(e["status"] == "set" for e in reactions)
    by_complete = [i for i in range(3) if agg[i] == "falsified"]
    note_gate = ("budget incomplete in some reactions: falsified by a complete-budget reaction; incomplete rows cannot falsify "
                 "and never rescue a phase" if by_complete and not complete_all else None)
    done = [e for e in reactions if e["status"] == "set"]
    lim = min(done, key=lambda e: e["E_ub"] + e["m"]) if done else None
    note = [note_base]
    if acp_ref:
        note.insert(0, ACP_REF_NOTE)
    if note_gate:
        note.insert(0, note_gate)
    if lim:
        note.insert(0, "limiting %s: falsified above %.4f V (E_ub + m)" % (lim["id"], lim["E_ub"] + lim["m"]))
    out.append({"phase": phase, "framing": framing, "stage": stage, "reaction_id": "ALL",
                "route": ACP_REF_ROUTE + "; aggregate over reactions" if acp_ref else "aggregate over reactions",
                "E_ub_V": _fmt(lim["E_ub"]) if lim else "", "E_lb_V": PENDING, "margin_V": _fmt(lim["m"]) if lim else "",
                "budget_status": "complete" if complete_all else "incomplete",
                "benchmark_status": bench, "k1_class_lfp": agg[0], "k1_class_42_43": agg[1], "k1_class_44_45": agg[2],
                "k1_verdict": overall(agg), "row_ids": _ids(v), "notes": "; ".join(note)})
    return out


WINDOW_COLS = ["solid", "role", "al_level_M", "ph_lower", "ph_upper", "window", "film_phase_label", "source"]


def window_rows():
    d = json.loads((W51 / "al_window.json").read_text(encoding="utf-8"))
    rows = []
    for w in d["windows"]:
        if w["solid"] not in ("Al(OH)3 am", "boehmite", "gibbsite", "corundum"):
            continue
        role = {"Al(OH)3 am": "governing", "boehmite": "reference"}.get(w["solid"], "printed beside")
        up = ">10" if w.get("upper_clipped") else "%.2f" % w["upper"] if w["upper"] is not None else ""
        lo = "%.2f" % w["lower"] if w["lower"] is not None else ""
        win = "none" if not w.get("passive") else "pH %s to %s" % (lo, up)
        rows.append({"solid": w["solid"], "role": role, "al_level_M": "%g" % w["c_thr_M"], "ph_lower": lo if w.get("passive") else "",
                     "ph_upper": up if w.get("passive") else "", "window": win,
                     "film_phase_label": "film phase: inferred amorphous (al_film_phase_rt_water unsourced)"
                     if w["solid"] == "Al(OH)3 am" else "", "source": ",".join(w.get("sources", []))})
    order = {"Al(OH)3 am": 0, "boehmite": 1, "gibbsite": 2, "corundum": 3}
    rows.sort(key=lambda r: (order[r["solid"]], -float(r["al_level_M"])))
    return rows


def _write_csv(path, cols, rows):
    with path.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=cols, lineterminator="\n")
        w.writeheader()
        w.writerows(rows)


def sensitivity_line(rows, sens, lo):
    """README sentence on the 4.0 V sensitivity, from the two row lists."""
    cols = ("k1_class_lfp", "k1_class_42_43", "k1_class_44_45", "k1_verdict")
    changed = [(r["phase"], r["framing"], r["reaction_id"], [(r[c], q[c]) for c in cols if r[c] != q[c]])
               for r, q in zip(rows, sens) if any(r[c] != q[c] for c in cols)]
    cross = [(float(r["E_ub_V"]) + float(r["margin_V"]), r) for r in rows
             if r["reaction_id"] not in ("ALL", "-") and r["budget_status"] == "complete" and r["margin_V"]]
    cross = [(x, r) for x, r in cross if x > lo]
    carb = min(x for x, r in cross if r["phase"] == "CaCO3")
    phos_x, phos = min(((x, r) for x, r in cross if r["phase"] != "CaCO3"), key=lambda t: t[0])
    head = ("Sensitivity (ladder_sens40.csv): the same rows with 4.0 V as the lowest class edge; "
            + ("no verdict changes" if not changed else "verdicts change: " + "; ".join(
                "%s %s %s %s" % (a, b, c, d) for a, b, c, d in changed)))
    return head + " (carbonate crossover %.4f V, lowest phosphate crossover %.4f V, %s %s)." % (
        carb, phos_x, phos["phase"], phos["reaction_id"]), changed



def run():
    block, body, meta = read_block()
    OUT.mkdir(parents=True, exist_ok=True)
    rows = build(block)
    _write_csv(OUT / "ladder.csv", COLUMNS, rows)
    sens = build(block, SENS_EDGE_V)
    _write_csv(OUT / "ladder_sens40.csv", COLUMNS, sens)
    sens_line, _ = sensitivity_line(rows, sens, cutoffs(block)["C_lo"][0])
    (OUT / "margins_v6_block.yaml").write_text(body + "\n", encoding="utf-8")
    wrows = window_rows()
    _write_csv(OUT / "passivation_window_v3.csv", WINDOW_COLS, wrows)
    from biomin_screen.pourbaix import ladder_md
    (OUT / "ladder_README.md").write_text(ladder_md.readme(meta, block, sens_line), encoding="utf-8")
    doc = {"stage": RUN_ID, "generated_utc": provenance.utc_now(), "git_sha": provenance.code_version(),
           "margins_source": meta, "n_rows": len(rows), "columns": COLUMNS,
           "bracket": {"E_lb": PENDING, "status": "bracket pending (hydration_free_energy_clo4 is a gap; "
                                                   "Ca2+ and Al3+ transfer free energies to the cell solvent are gaps)"},
           "direct_correction": direct_correction(block)["crystalline_reference_row"],
           "a_al3_oxide": "unchanged: the governing and reference rows of the benchmark are adopted; no input moved"}
    (OUT / "ladder.json").write_text(json.dumps(doc, indent=1, default=float) + "\n", encoding="utf-8")
    print("wrote", rel(OUT / "ladder.csv"), len(rows), "rows")
    return rows, meta


def main(argv=None):
    ap = argparse.ArgumentParser(prog="python -m biomin_screen.pourbaix.ladder")
    ap.add_argument("cmd", choices=("run",))
    ap.parse_args(argv)
    run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
