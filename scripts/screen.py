#!/usr/bin/env python3
"""Regenerate the large screening outputs that are not shipped, and the long production runs.

    python scripts/screen.py            per-cell documents into results/, then every stage into work/ and compared
                                        with the shipped outputs (about 20 minutes, peak 1.9 GB)
    python scripts/screen.py --quick    the per-cell documents, then the two production runs with a smaller sample,
                                        written to work/quick/ (about 2 minutes)

Both modes first rebuild the per-cell Pourbaix documents (results/pourbaix/final/slurry/ and the c5 inputs snapshot) that
the public tree leaves out; they are written into results/ (the c5 and final run directories are rewritten with equivalent documents;
`git checkout results` restores the shipped ones). The full mode then runs `scripts/check.py --full`: all
regenerated stages and the two carbonate-chain production runs go to work/ and are compared with the shipped summaries.
The shipped summaries are never overwritten (a production run refuses to overwrite its output). The quick mode draws 8192
samples per state (2^13, against 2^20 in the production runs) and skips the Sobol and Shapley sensitivity analyses (they
account for nearly all of the 9 minutes of the ignorance-prior run), so its probabilities carry visibly larger Monte Carlo
error, its output has no sensitivity section, and it is NOT expected to equal the shipped summaries. The machine needs
8 GB of memory; both modes use a single core.
"""
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))
import check  # noqa: E402
from biomin_screen import archive  # noqa: E402

QUICK_DRAWS = ["--decision-draws", "8192", "--draws", "8192", "--no-sensitivity"]


def run(label, args, cwd, env, extra=()):
    t = time.time()
    p = subprocess.run([sys.executable, "-m"] + args + list(extra), cwd=cwd, env=env, capture_output=True, text=True)
    print("%-48s %s (%.0f s)" % (label, "ok" if p.returncode == 0 else "FAIL", time.time() - t))
    if p.returncode:
        print("    " + "\n    ".join((p.stderr or p.stdout).strip().splitlines()[-3:]))
    return p.returncode


def main(argv):
    quick = "--quick" in argv
    archive.unpack(ROOT)
    env = dict(os.environ, PYTHONPATH=str(ROOT / "src"), BIOMIN_SCREEN_ROOT=str(ROOT), PYTHONHASHSEED="0",
               OMP_NUM_THREADS="1", OPENBLAS_NUM_THREADS="1")
    bad = 0
    bad += bool(run("per-cell slurry and cell documents", ["biomin_screen.pourbaix.carbonate_run", "--config",
                                                          "results/pourbaix/config/final.yaml"], ROOT, env))
    bad += bool(run("c5 inputs snapshot", ["biomin_screen.pourbaix.c5", "--config", "results/pourbaix/config/c5.yaml"], ROOT, env))
    if not quick:
        return check.main(["--full"]) or (1 if bad else 0)
    work = ROOT / "work" / "quick"
    check.WORK = work
    check.prepare(True)
    env.update(PYTHONPATH=str(work / "src"), BIOMIN_SCREEN_ROOT=str(work))
    for label, args, _files in check.LONG_STAGES:
        extra = check.EXTRA_ARGS.get(args[1], []) + QUICK_DRAWS
        bad += bool(run(label, args, work, env, extra))
    print("screen (quick): %s; output in work/quick/" % ("FAIL" if bad else "done"))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
