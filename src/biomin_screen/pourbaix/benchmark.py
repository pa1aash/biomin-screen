"""Phosphate benchmark, Al-O-H passivation window and the tier-1 ladder v2 with framings and stages.

Outputs under results/pourbaix/benchmark/. The carbonate outputs and the oxidation-ladder outputs are only
read. Materials Project numbers come from database 2026.09.28 (the phosphate cache plus the benchmark
additions) and are comparators only.

    uv run python -m biomin_screen.pourbaix.benchmark benchmark   # step 1: formation-energy benchmark
    uv run python -m biomin_screen.pourbaix.benchmark run         # every step: benchmark, aluminium window, ladder v2, report
"""
import argparse
import json
import sys
import warnings

from biomin_screen.pourbaix import cache, gasref, provenance
from biomin_screen.pourbaix import oxidation_ladder as k
from biomin_screen.pourbaix import formation_benchmark as bm
from biomin_screen.pourbaix import phosphate_extra_cache as wc
from biomin_screen.pourbaix import window as w
from biomin_screen.pourbaix.paths import rel

RUN_ID = "benchmark"
OUT = wc.W51_DIR


def pooled():
    warnings.simplefilter("ignore")
    entries, excluded = wc.load_entries()
    ew = w.EnergyBook(entries, k.T0, gasref.SCHEMES["janaf"], cache.CACHE_DIR)
    return entries, excluded, ew


def _dump(path, doc):
    path.write_text(json.dumps(doc, indent=1, default=float) + "\n", encoding="utf-8")


def run_benchmark(entries=None, ew=None):
    if entries is None:
        entries, _, ew = pooled()
    bench, summary = bm.run(entries, ew)
    OUT.mkdir(parents=True, exist_ok=True)
    bm.write_csv(bench, OUT / "formation_benchmark_table.csv")
    _dump(OUT / "formation_benchmark_table.json", {"stage": RUN_ID, "step": "1 phosphate benchmark",
                                       "generated_utc": provenance.utc_now(), "git_sha": provenance.code_version(),
                                       "inputs": bm.inputs_record(), "summary": summary, "rows": bench})
    print("wrote", rel(OUT / "formation_benchmark_table.csv"))
    return bench, summary


def main(argv=None):
    ap = argparse.ArgumentParser(prog="python -m biomin_screen.pourbaix.benchmark")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("benchmark")
    sub.add_parser("run")
    args = ap.parse_args(argv)
    if args.cmd == "benchmark":
        run_benchmark()
        return 0
    run_benchmark()
    from biomin_screen.pourbaix import benchmark_run
    return benchmark_run.run()


if __name__ == "__main__":
    sys.exit(main())
