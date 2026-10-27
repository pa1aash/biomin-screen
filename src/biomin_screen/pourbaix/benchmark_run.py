"""Benchmark run: every step after the formation-energy benchmark (outputs under results/pourbaix/benchmark/).

    uv run python -m biomin_screen.pourbaix.benchmark run

Step 2 writes al_window.json and a_al3_oxide.csv; steps 3 to 7 write ladder_v2.csv and benchmark.json; the
report benchmark.md summarises all of them. The formation-energy table (step 1) is read from the output
of `benchmark benchmark`.
"""
import csv
import json

from biomin_screen.pourbaix import oxidation_ladder as k
from biomin_screen.pourbaix import al_window as al
from biomin_screen.pourbaix import provenance
from biomin_screen.pourbaix.paths import rel

OUT = k.POURBAIX_RESULTS / "benchmark"
OUTPUTS = ("al_window.json", "a_al3_oxide.csv")


def _dump(path, doc):
    path.write_text(json.dumps(doc, indent=1, default=float) + "\n", encoding="utf-8")


def run_window(ctx=None):
    doc = al.run(ctx)
    doc = {"stage": "benchmark", "step": "2 Al-O-H passivation window", "generated_utc": provenance.utc_now(),
           "git_sha": provenance.code_version(), "evidence_table_sha256": k.evidence_sha256(), "params_sha": k.PARAMS_SHA,
           **doc}
    OUT.mkdir(parents=True, exist_ok=True)
    _dump(OUT / "al_window.json", doc)
    rows = doc["a_al3_rows"]
    with open(OUT / "a_al3_oxide.csv", "w", newline="", encoding="utf-8") as fh:
        fh.write("# a(Al3+) at the oxide-equilibrium state (slurry stage, route R1), 298.15 K, I = 0, log10 "
                 "activities. Governing film: Al(OH)3 am (TB-027, grade C); crystalline reference boehmite (TI-026 with "
                 "TI-022, grade A); gibbsite TB-028, corundum TB-029; hydrolysis TB-023..TB-026.\n")
        fh.write("# Polyphosphate complexation leaves a(Al3+) unchanged at fixed solid equilibrium and raises total Al "
                 "only; linear-chain constants are a gap (polyp_al_log_beta1_linear), so totals exclude it.\n")
        wr = csv.DictWriter(fh, fieldnames=list(rows[0]), lineterminator="\n")
        wr.writeheader()
        for r in rows:
            wr.writerow({c: ("%.2f" % v if c == "pH" else "%.4f" % v) for c, v in r.items()})
    print("wrote", rel(OUT / "al_window.json"), rel(OUT / "a_al3_oxide.csv"))
    return doc


# ------------------------------------------------------------------------------ steps 3 to 7: the ladder
LADDER_COLS = ["row_type", "phase", "stage", "role", "framing", "governs", "species", "E_ub_V", "E_lb_V", "bracket",
               "margin_V", "margin_complete", "limiting_reaction", "undetermined_reactions", "status_LFP-class",
               "status_4.2-4.3 V", "status_4.4-4.5 V", "d_3.65_V", "d_4.2_V", "d_4.3_V", "d_4.4_V", "d_4.5_V",
               "label", "gap_flag", "composition_based", "dft_janaf_V", "dft_mp_V", "dft_label", "step",
               "a_w_star", "a_w_star_lo", "a_w_star_hi", "lit_conversion_T", "note"]
CUTS = (3.65, 4.2, 4.3, 4.4, 4.5)


def _flat(r):
    out = dict(r)
    for c, s in (r.get("statuses") or {}).items():
        out["status_%s" % c] = s
    if r.get("E_ub_V") is not None:
        for e in CUTS:
            out["d_%g_V" % e] = r["E_ub_V"] - e
    if r.get("a_w_star_range"):
        out["a_w_star_lo"], out["a_w_star_hi"] = r["a_w_star_range"]
    if r["row_type"] != "conversion" and r.get("E_lb_V") is None:
        out["E_lb_V"] = "pending" if r.get("bracket", "").startswith("bracket pending") else ""
    return out


def write_ladder(rows, conv):
    with open(OUT / "ladder_v2.csv", "w", newline="", encoding="utf-8") as fh:
        fh.write("# Ladder v2, tier 1 only, vs Li+/Li at a_w = 1, a_OH = 1, 298.15 K. E_ub: solid-salt LiClO4 "
                 "sink (upper bound: 'below' stands, 'above (ub)' is not a pass). E_lb: bracket of the lower bound. margin_V is "
                 "PROVISIONAL (tier-1 budget recipe).\n")
        fh.write("# Framings: amorphous governs the in-situ routes, crystalline is the optimistic upper reference. "
                 "DFT columns are Materials Project 2026.09.28 comparators with the label of the benchmark.\n")
        wr = csv.DictWriter(fh, fieldnames=LADDER_COLS, extrasaction="ignore", lineterminator="\n")
        wr.writeheader()
        for r in rows + conv:
            f = _flat(r)
            wr.writerow({c: ("%.4f" % v if isinstance(v, float) and not c.startswith("a_w") else
                             ("%.4g" % v if isinstance(v, float) else ("" if v is None else v)))
                         for c, v in f.items() if c in LADDER_COLS})


def carbonate_f7(detail):
    import json as _json
    fixed = _json.loads(k.FIXED_SUMMARY.read_text(encoding="utf-8"))["phases"]["CaCO3"]["by_sink"]["LiClO4"]
    summ = detail["CaCO3"]["crystalline"]["summary"]
    return {"expt_V": summ["expt"]["onset_V"],
            "dft_2026_09_28_V": {s: summ[s]["onset_V"] for s in k.SCHEMES},
            "dft_fixed_2026_04_13_V": {s: fixed["oxidation_by_scheme"][s]["value_V"] for s in k.SCHEMES},
            "reading": "labelled extra so that every DFT column shares database 2026.09.28; the fixed production value "
                       "stays the control gate"}


def run_ladder(bench_rows, entries=None):
    import warnings

    from biomin_screen.pourbaix import benchmark
    from biomin_screen.pourbaix import ladder_v2 as lad
    warnings.simplefilter("ignore")
    if entries is None:
        entries, _, _ = benchmark.pooled()
    ctx = k.Ctx()
    g = k.gate(ctx)
    if not g["passed"]:
        raise SystemExit("BLOCKED: carbonate gate failed")
    lad.install()
    books = {"expt": lad.ExptBookW51(ctx)} | {s: lad.DftBookW51(s, ctx, entries) for s in k.SCHEMES}
    rows, conv, detail, bracket = lad.build(ctx, books, bench_rows)
    write_ladder(rows, conv)
    doc = {"stage": "benchmark", "steps": "3 to 7", "generated_utc": provenance.utc_now(), "git_sha": provenance.code_version(),
           "gate": g, "params_sha": k.PARAMS_SHA, "evidence_table_sha256": k.evidence_sha256(),
           "rule": "tier 1 only; E_ox = min over specified reactions; undetermined never passes; a DFT comparator never "
                   "turns an undetermined staged reaction into a determined one",
           "staged_products": {"values": books["expt"].extra, **books["expt"].extra_meta},
           "al_pmeta3_search": AL_PMETA3_SEARCH, "bracket": bracket, "carbonate_f7": carbonate_f7(detail),
           "ladder": rows, "conversions": conv, "detail": detail}
    _dump(OUT / "benchmark.json", doc)
    print("wrote", rel(OUT / "ladder_v2.csv"), rel(OUT / "benchmark.json"))
    return doc


# The search for Al(PO3)3 thermochemistry (attempts logged, nothing typed from it)
AL_PMETA3_SEARCH = {
    "result": "undetermined: no calorimetric DfH, DfG or S0 of Al(PO3)3 and no AlPO4 + P2O5 equilibrium data found",
    "attempts": [
        {"where": "Semantic Scholar API, 2 queries (Al(PO3)3 enthalpy of formation; AlPO4-P2O5 thermodynamics)",
         "outcome": "HTTP 429 rate limit, no result"},
        {"where": "web search: Al(PO3)3 standard enthalpy of formation",
         "outcome": "no value; nearest: AlH2P3O10.2H2O solution calorimetry (J. Chem. Thermodyn. 111, 27-30), a "
                    "different compound; a TGA onset of Al(PO3)3 -> AlPO4 + P2O5 near 1000 C (kinetic, not an "
                    "equilibrium)"},
        {"where": "web search: Al metaphosphate decomposition, P2O5 vapour pressure equilibrium",
         "outcome": "no equilibrium data; a P2O5 assessment (Jung and Hudon 2012) covers the P2O5 side only"},
        {"where": "pubs.rsc.org landing page f19726800259 (1972, title unread)", "outcome": "HTTP 403 (recorded as a gap)"},
    ],
    "outstanding": "dfh_al_pmeta3, dfg_al_pmeta3, s_al_pmeta3 stay gaps; a Knudsen-effusion or calorimetric source is the need",
}


OUTPUTS = OUTPUTS + ("ladder_v2.csv", "benchmark.json", "benchmark.md")


def run():
    import json as _json
    run_window()
    bench = _json.loads((OUT / "formation_benchmark_table.json").read_text(encoding="utf-8"))
    doc = run_ladder(bench["rows"])
    from biomin_screen.pourbaix import benchmark_md
    al_doc = _json.loads((OUT / "al_window.json").read_text(encoding="utf-8"))
    (OUT / "benchmark.md").write_text(benchmark_md.render(bench, al_doc, doc), encoding="utf-8")
    print("wrote", rel(OUT / "benchmark.md"))
    return 0
