"""Command line of the screen.

    python -m biomin_screen.screen production --out O [--prior-set S] [--control C ...] [--convention K=V ...]
                                     [--bind SYM=KEY ...] [--independence] [--no-sensitivity]
                                                              production screen of the carbonate chain (priors from data/params.yaml)
    python -m biomin_screen.screen k2-grid --out O [--parts carbonate acid phosphate] [--dry] [--stride N] [--label L]
                                                              K2 over the specified grid, the controls and the acid-adjusted state
    python -m biomin_screen.screen k2-rerun --out O [--grids alkaline acid] [--label L]
                                                              phosphate K2 rerun (updated keys, max-Omega control)
    python -m biomin_screen.screen k2-ratio-grid --out O [--grids alkaline acid] [--label L]
                                                              phosphate K2 on a Ca:P ratio grid
    python -m biomin_screen.screen k2-perph | k2-perph-ratio  per-pH minimum doses of the crossed and of the ratio grid
    python -m biomin_screen.screen breakeven                  break-even ratio of the saturated-sink exclusions
    python -m biomin_screen.screen nucleation-numbers         nucleation numbers from the production draws
    python -m biomin_screen.screen ph-production --out O [--dry] [--stride N] [--label L]
                                                              phosphate films (stage rows, K2 maps, K3 and K4 gaps, route layer, baselines)
    python -m biomin_screen.screen ph-precision --out O [--dry]
                                                              required-precision map and flip values

The scripts k2_ratio_grid, k2_perph, k2_perph_ratio, breakeven and nucleation_numbers also run as
``python -m biomin_screen.screen.<module>``. Documents are written under results/screen/<run>/.
"""
import argparse
import sys
from pathlib import Path

from biomin_screen._util import repo_root
from biomin_screen.screen import (breakeven, k2_grid, k2_perph, k2_perph_ratio, k2_ratio_grid, k2_rerun, nucleation_numbers,
                                  phosphate_films, precision_map, provenance_guard, run)
from biomin_screen.screen.priors import MockPriorsRefused

REFUSED = (run.ProductionRefused, provenance_guard.Fixed, run.params_adapter.PriorFileError)


def build_parser():
    ap = argparse.ArgumentParser(prog="python -m biomin_screen.screen", description="Command line of the screen. Documents are written under results/screen/<run>/.",
                                 epilog=__doc__.split("\n\n", 1)[1],
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    pr = sub.add_parser("production", help="production screen of the carbonate chain (priors from data/params.yaml)")
    pr.add_argument("--out", default=str(run.SCREEN_DIR / "summary.json"))
    pr.add_argument("--prior-set", default="table", choices=("table", "ignorance", "analog"),
                    help="prior set of the unmeasured interfacial energies (labelled in the output)")
    pr.add_argument("--untruncated", action="store_true", help="run gamma_sl0 untruncated (labelled sensitivity)")
    pr.add_argument("--truncation-sensitivity", action="store_true",
                    help="also rerun the decisions untruncated and list the verdicts that change")
    pr.add_argument("--stability", help="document with the R-slurry Pourbaix section")
    pr.add_argument("--cell", action="append", default=[], help="R-cell Pourbaix document (one per sink; repeatable)")
    pr.add_argument("--decision-draws", type=int, help="draws per state of the decision layer")
    pr.add_argument("--draws", type=int, help="draws per state of the sensitivity propagation")
    pr.add_argument("--control", action="append", default=[],
                    help="deletion-test control of screen.yaml controls (repeatable): bare_oxide, PVDF")
    pr.add_argument("--convention", action="append", default=[], metavar="KEY=VALUE",
                    help="sweep override of a specified convention (table key), labelled in the output")
    pr.add_argument("--bind", action="append", default=[], metavar="SYMBOL=KEY",
                    help="override an R-slurry binding (a labelled sensitivity)")
    pr.add_argument("--no-sensitivity", action="store_true", help="skip the Sobol and Shapley analysis (sweeps)")
    pr.add_argument("--label", help="run label recorded in the provenance")
    pr.add_argument("--mechanism", action="store_true",
                    help="write the admitted and refused draws of the admissibility rule (report-only diagnostic)")
    pr.add_argument("--independence", action="store_true", help="drop the stated correlations (dependence sweep)")
    kg = sub.add_parser("k2-grid", help="K2 over the specified grid, controls and the acid-adjusted state")
    kg.add_argument("--out", required=True)
    kg.add_argument("--parts", nargs="+", default=["carbonate", "acid"], choices=("carbonate", "acid", "phosphate"))
    kg.add_argument("--dry", action="store_true", help="dry run: output under results/screen/dryrun_ph/")
    kg.add_argument("--stride", type=int, default=1, help="dry run only: every N-th cell of a grid")
    kg.add_argument("--label")
    k2 = sub.add_parser("k2-rerun", help="phosphate K2 rerun with the updated keys and the rule-based control")
    k2.add_argument("--out", required=True)
    k2.add_argument("--grids", nargs="+", default=["alkaline", "acid"], choices=("alkaline", "acid"))
    k2.add_argument("--label")
    kr = sub.add_parser("k2-ratio-grid", help="phosphate K2 on a Ca:P ratio grid beside the crossed grid")
    kr.add_argument("--out", required=True)
    kr.add_argument("--grids", nargs="+", default=["alkaline", "acid"], choices=("alkaline", "acid"))
    kr.add_argument("--label")
    sub.add_parser("k2-perph", help="per-pH minimum doses of the crossed K2 grid (fixed and rerun cells)")
    sub.add_parser("k2-perph-ratio", help="per-pH minimum doses of the Ca:P ratio grid beside the crossed grid")
    sub.add_parser("breakeven", help="break-even ratio of the saturated-sink exclusions (arithmetic over the K1 ladder)")
    sub.add_parser("nucleation-numbers", help="nucleation numbers from the production draws")
    pp = sub.add_parser("ph-production", help="phosphate films: stage rows, K2 maps, K3 and K4 gaps, route layer")
    pp.add_argument("--out", required=True)
    pp.add_argument("--dry", action="store_true")
    pp.add_argument("--stride", type=int, default=1)
    pp.add_argument("--label")
    pm = sub.add_parser("ph-precision", help="required-precision map and flip values")
    pm.add_argument("--out", required=True)
    pm.add_argument("--dry", action="store_true")
    return ap


def _report(root, path, stats):
    print("wrote %s  (%.1f s, peak %.0f MB, %d cells, %d capped)" % (path.relative_to(root), stats["seconds"], stats["peak_mb"],
                                                                     stats["cells"], stats["capped_cells"]))


def main(argv=None):
    args = build_parser().parse_args(argv)
    root = repo_root()
    if args.cmd == "k2-grid":
        def log(cid, rec):
            print("  %-4s %-12s %s" % (rec.get("draws"), rec.get("verdict"), cid[:100]), flush=True)
        try:
            path, doc, stats = k2_grid.run_k2_grid(root, root / args.out, tuple(args.parts), args.dry, label=args.label,
                                                   log=log if args.dry else None, stride=args.stride)
        except REFUSED as exc:
            print("refused: %s" % exc, file=sys.stderr)
            return 2
        _report(root, path, stats)
        return 0
    if args.cmd == "k2-rerun":
        try:
            path, doc, stats = k2_rerun.run_ph2(root, root / args.out, tuple(args.grids), label=args.label)
        except REFUSED as exc:
            print("refused: %s" % exc, file=sys.stderr)
            return 2
        _report(root, path, stats)
        return 0
    if args.cmd == "k2-ratio-grid":
        try:
            path, doc, stats = k2_ratio_grid.run_ph3(root, root / args.out, tuple(args.grids), label=args.label)
        except REFUSED as exc:
            print("refused: %s" % exc, file=sys.stderr)
            return 2
        _report(root, path, stats)
        return 0
    if args.cmd in ("k2-perph", "k2-perph-ratio", "breakeven", "nucleation-numbers"):
        script = {"k2-perph": k2_perph, "k2-perph-ratio": k2_perph_ratio, "breakeven": breakeven,
                  "nucleation-numbers": nucleation_numbers}[args.cmd]
        try:
            script.main(root)
        except REFUSED as exc:
            print("refused: %s" % exc, file=sys.stderr)
            return 2
        return 0
    if args.cmd == "ph-precision":
        try:
            path, doc = precision_map.run_map(root, root / args.out if not Path(args.out).is_absolute() else args.out, args.dry,
                                             log=lambda m: print(" ", m, flush=True))
        except REFUSED as exc:
            print("refused: %s" % exc, file=sys.stderr)
            return 2
        print("wrote %s (%d rows)" % (path, len(doc["rows"])))
        return 0
    if args.cmd == "ph-production":
        try:
            path, doc, stats = phosphate_films.run_phosphate(root, root / args.out, args.dry, args.label, args.stride)
        except REFUSED as exc:
            print("refused: %s" % exc, file=sys.stderr)
            return 2
        _report(root, path, stats)
        return 0
    try:
        kw = dict(prior_set=args.prior_set, truncation=not args.untruncated, controls=args.control,
                  conventions={k: float(v) for k, v in (c.split("=", 1) for c in args.convention)} or None,
                  bind=dict(b.split("=", 1) for b in args.bind) or None, sensitivity=not args.no_sensitivity,
                  run_label=args.label, mechanism=args.mechanism,
                  truncation_sensitivity=args.truncation_sensitivity,
                  stability_path=(root / args.stability) if args.stability else None,
                  cell_paths=[root / c for c in args.cell], decision_draws=args.decision_draws,
                  overrides={"propagation": {"draws_per_regime": args.draws}} if args.draws else None)
        path, _ = run.run(root, root / args.out, dry_run=False, independence=args.independence, **kw)
    except (MockPriorsRefused, *REFUSED) as exc:
        print("refused: %s" % exc, file=sys.stderr)
        return 2
    print("wrote %s" % path.relative_to(root))
    return 0


if __name__ == "__main__":
    sys.exit(main())
