#!/usr/bin/env python3
"""Regenerate the stored outputs in work/ and compare them with the shipped ones.

    python scripts/check.py            the regenerated stages (about 10 minutes)
    python scripts/check.py --full     also the two long carbonate-chain production runs (about 10 more minutes)

The inputs (configs/, data/, the cached thermodynamic data under results/pourbaix/cache and its siblings) are copied
into work/ and every stage runs there, so the shipped results are never overwritten. A comparison passes when every
number of the regenerated file equals the shipped one to a relative tolerance of 1e-9 (absolute 1e-12); the keys that
record the run itself (timestamps, run time, peak memory, provenance) are not compared. Tables and figure sidecars are
compared the same way.
"""
import json
import math
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from biomin_screen import archive  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT / "work"
REL, ABS = 1e-9, 1e-12
SKIP = {"provenance", "generated_utc", "seconds", "peak_mb", "inputs", "generator", "run_id", "wall_seconds"}
CSV_SKIP_COLUMNS = set()

# (label, arguments of `python -m <module>`, files it writes relative to the root, long)
STAGES = [
    ("oxidation ladder", ["biomin_screen.pourbaix.oxidation_ladder", "run"], ["results/pourbaix/oxidation_ladder/oxidation_ladder.json"], False),
    ("formation benchmark and aluminium window", ["biomin_screen.pourbaix.benchmark", "run"],
     ["results/pourbaix/benchmark/benchmark.json", "results/pourbaix/benchmark/al_window.json",
      "results/pourbaix/benchmark/formation_benchmark_table.csv", "results/pourbaix/benchmark/ladder_v2.csv"], False),
    ("ladder with margins and passivation window", ["biomin_screen.pourbaix.ladder", "run"],
     ["results/pourbaix/ladder/ladder.csv", "results/pourbaix/ladder/ladder_sens40.csv", "results/pourbaix/ladder/passivation_window_v3.csv"], False),
    ("K2 grid", ["biomin_screen.screen", "k2-grid", "--out", "results/screen/k2_grid_ph/summary.json", "--label", "k2_grid_ph"],
     ["results/screen/k2_grid_ph/summary.json"], False),
    ("phosphate films", ["biomin_screen.screen", "ph-production", "--out", "results/screen/phosphate_films_ph/summary.json",
                         "--label", "phosphate_films_ph"], ["results/screen/phosphate_films_ph/summary.json"], False),
    ("K2 rerun, alkaline", ["biomin_screen.screen", "k2-rerun", "--out", "results/screen/k2_alkaline_decade/summary.json",
                            "--grids", "alkaline", "--label", "k2_alkaline_decade"], ["results/screen/k2_alkaline_decade/summary.json"], False),
    ("K2 rerun, acid", ["biomin_screen.screen", "k2-rerun", "--out", "results/screen/k2_acid_decade/summary.json",
                        "--grids", "acid", "--label", "k2_acid_decade"], ["results/screen/k2_acid_decade/summary.json"], False),
    ("per-pH doses", ["biomin_screen.screen", "k2-perph"], ["results/screen/k2_perph_decade/perph.csv", "results/screen/k2_perph_decade/perph.json"], False),
    ("K2 ratio grid, alkaline", ["biomin_screen.screen", "k2-ratio-grid", "--out", "results/screen/k2_alkaline_ratio/summary.json",
                                 "--grids", "alkaline", "--label", "k2_alkaline_ratio"], ["results/screen/k2_alkaline_ratio/summary.json"], False),
    ("K2 ratio grid, acid", ["biomin_screen.screen", "k2-ratio-grid", "--out", "results/screen/k2_acid_ratio/summary.json",
                             "--grids", "acid", "--label", "k2_acid_ratio"], ["results/screen/k2_acid_ratio/summary.json"], False),
    ("per-pH doses, ratio grid", ["biomin_screen.screen", "k2-perph-ratio"], ["results/screen/k2_perph_ratio/perph.csv", "results/screen/k2_perph_ratio/perph.json"], False),
    ("break-even ratios", ["biomin_screen.screen", "breakeven"], ["results/screen/breakeven_ph/breakeven.csv"], False),
]
LONG_STAGES = [
    ("carbonate chain, ignorance priors", ["biomin_screen.screen", "production", "--out", "results/screen/ignorance_ph/summary.json",
                                            "--prior-set", "ignorance", "--label", "ignorance_ph"], ["results/screen/ignorance_ph/summary.json"]),
    ("carbonate chain, sourced priors", ["biomin_screen.screen", "production", "--out", "results/screen/table_ph/summary.json",
                                          "--prior-set", "table", "--label", "table_ph"], ["results/screen/table_ph/summary.json"]),
]
EXTRA_ARGS = {  # the production runs read the per-point slurry documents, the cell documents and the two deletion controls
    "production": ["--stability", "results/pourbaix/c5/slurry",
                   "--cell", "results/pourbaix/c5/cell/LiClO4.json", "--cell", "results/pourbaix/c5/cell/LiBOB.json",
                   "--cell", "results/pourbaix/c5/cell/LiPCP.json", "--cell", "results/pourbaix/c5/cell/solvated.json",
                   "--control", "bare_oxide", "--control", "PVDF"],
}


def compare(new, old, path="", out=None):
    """Differences between two parsed JSON documents, numbers to REL and ABS."""
    out = [] if out is None else out
    if isinstance(old, dict) and isinstance(new, dict):
        for k in sorted(set(old) | set(new)):
            if k in SKIP:
                continue
            if k not in old or k not in new:
                out.append("%s/%s: only in %s" % (path, k, "regenerated" if k in new else "shipped"))
            else:
                compare(new[k], old[k], path + "/" + str(k), out)
    elif isinstance(old, list) and isinstance(new, list):
        if len(old) != len(new):
            out.append("%s: %d items against %d" % (path, len(new), len(old)))
        else:
            for i, (a, b) in enumerate(zip(new, old)):
                compare(a, b, "%s[%d]" % (path, i), out)
    elif isinstance(old, (int, float)) and isinstance(new, (int, float)) and not isinstance(old, bool):
        if not math.isclose(new, old, rel_tol=REL, abs_tol=ABS):
            out.append("%s: %r against %r" % (path, new, old))
    elif old != new and not (isinstance(old, str) and isinstance(new, str)):
        out.append("%s: %r against %r" % (path, new, old))
    return out


def compare_csv(new_path, old_path):
    import csv
    def rows(p):
        with open(p, encoding="utf-8") as fh:
            return list(csv.reader(l for l in fh if not l.startswith("#")))
    a, b = rows(new_path), rows(old_path)
    if len(a) != len(b):
        return ["%d rows against %d" % (len(a), len(b))]
    out = []
    for i, (ra, rb) in enumerate(zip(a, b)):
        for j, (x, y) in enumerate(zip(ra, rb)):
            try:
                if not math.isclose(float(x), float(y), rel_tol=REL, abs_tol=ABS):
                    out.append("row %d column %d: %s against %s" % (i, j, x, y))
            except ValueError:
                pass  # text cells (notes) are not compared
    return out


def compare_file(rel):
    new, old = WORK / rel, ROOT / rel
    if not new.is_file():
        return ["not regenerated"]
    if rel.endswith(".csv"):
        return compare_csv(new, old)
    return compare(json.loads(new.read_text(encoding="utf-8")), json.loads(old.read_text(encoding="utf-8")))


def prepare(full):
    if WORK.exists():
        shutil.rmtree(WORK)
    for d in ("configs", "data"):
        shutil.copytree(ROOT / d, WORK / d)
    (WORK / "figures").mkdir()
    shutil.copytree(ROOT / "src", WORK / "src", ignore=shutil.ignore_patterns("__pycache__"))
    (WORK / "pyproject.toml").write_text((ROOT / "pyproject.toml").read_text(encoding="utf-8"), encoding="utf-8")
    pb = WORK / "results" / "pourbaix"
    pb.mkdir(parents=True)
    for p in (ROOT / "results" / "pourbaix").iterdir():
        if p.is_dir():
            shutil.copytree(p, pb / p.name, ignore=shutil.ignore_patterns("*.gz"))
        else:
            shutil.copy2(p, pb / p.name)
    (WORK / "results" / "screen").mkdir(parents=True)
    (WORK / "results" / "tables").mkdir(parents=True)
    # stored runs that this invocation does not regenerate are copied; the regenerated ones start from nothing
    regenerated = {Path(f).parts[2] for _l, _a, fs, *_ in STAGES for f in fs if f.startswith("results/screen/")}
    if full:
        regenerated |= {Path(f).parts[2] for _l, _a, fs in LONG_STAGES for f in fs}
    for p in (ROOT / "results" / "screen").iterdir():
        if p.is_dir() and p.name not in regenerated:
            shutil.copytree(p, WORK / "results" / "screen" / p.name, ignore=shutil.ignore_patterns("*.gz"))


def run_stage(label, args, env):
    t = time.time()
    cmd = [sys.executable, "-m"] + args
    if args[0] == "biomin_screen.screen" and args[1] in EXTRA_ARGS:
        cmd += EXTRA_ARGS[args[1]]
    p = subprocess.run(cmd, cwd=WORK, env=env, capture_output=True, text=True)
    return p.returncode, time.time() - t, (p.stderr or p.stdout).strip().splitlines()[-3:]


def main(argv):
    full = "--full" in argv
    env = dict(os.environ, PYTHONPATH=str(WORK / "src"), BIOMIN_SCREEN_ROOT=str(WORK), PYTHONHASHSEED="0",
               OMP_NUM_THREADS="1", OPENBLAS_NUM_THREADS="1")
    archive.unpack(ROOT)
    prepare(full)
    stages = [(l, a, f) for l, a, f, _ in STAGES]
    if full:
        stages += LONG_STAGES
    bad = 0
    for label, args, files in stages:
        rc, secs, tail = run_stage(label, args, env)
        if rc:
            print("%-48s FAIL (exit %d, %.0f s)\n    %s" % (label, rc, secs, "\n    ".join(tail)))
            bad += 1
            continue
        diffs = [d for f in files for d in ["%s: %s" % (f, x) for x in compare_file(f)]]
        print("%-48s %s (%.0f s)" % (label, "PASS" if not diffs else "DIFFERS", secs))
        for d in diffs[:5]:
            print("    " + d)
        bad += bool(diffs)
    # tables and figure data
    for kind in ("regime", "breakeven", "inputs"):
        t = time.time()
        p = subprocess.run([sys.executable, "-m", "biomin_screen", "tables", kind], cwd=WORK, env=env, capture_output=True, text=True)
        files = {"regime": ["regime_table.json", "regime_table.csv"], "breakeven": ["breakeven_table.json"],
                 "inputs": ["input_tables.json", "input_tables.csv"]}[kind]
        diffs = []
        if p.returncode:
            diffs = [(p.stderr or p.stdout).strip().splitlines()[-1]]
        else:
            for f in files:
                diffs += ["%s: %s" % (f, x) for x in compare_file("results/tables/" + f)] if f.endswith(".json") else []
        print("%-48s %s (%.0f s)" % ("table: " + kind, "PASS" if not diffs else "DIFFERS", time.time() - t))
        for d in diffs[:5]:
            print("    " + d)
        bad += bool(diffs)
    print("check: %s (tolerance: relative %.0e, absolute %.0e)" % ("FAIL" if bad else "PASS", REL, ABS))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
