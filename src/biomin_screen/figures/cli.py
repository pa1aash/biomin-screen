"""Command line of the figure builder.

    python -m biomin_screen.figures.cli [--only NAME ...] [--no-png]
    python -m biomin_screen.figures.cli --check [--only NAME ...]
    python -m biomin_screen.figures.cli --list
    biomin-screen figures ...                  (the same)

Builds the data figures from the stored outputs under results/ and data/ into figures/ as
PDF and PNG, with a numeric sidecar figures/<name>.json. `--check` rebuilds into a scratch
directory and compares the sidecars with the shipped ones (relative tolerance 1e-6). A
figure is named by its name (retrodiction) or its id (fig4). Needs no network, no Blender and no git.
"""
import argparse
import sys

from biomin_screen import _util
from biomin_screen.figures import build


def main(argv=None):
    ap = argparse.ArgumentParser(prog="biomin-screen figures", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--check", action="store_true",
                    help="rebuild into a scratch directory and compare the numeric sidecars with the shipped ones")
    ap.add_argument("--only", nargs="+", metavar="NAME", help="build only these figures (name or id)")
    ap.add_argument("--no-png", action="store_true", help="write the PDF and the sidecar only")
    ap.add_argument("--list", action="store_true", help="list the figures and their input files")
    ap.add_argument("--root", help="repository root (default: found from the working directory)")
    args = ap.parse_args(argv)
    root = _util.repo_root(args.root) if args.root else _util.repo_root()
    try:
        if args.list:
            for mod in build.select(root):
                f = mod.FIGURE
                print("%-6s %-22s %s" % (f["id"], f["name"], ", ".join([f["input"]] + sorted(f.get("aux", {}).values()))))
            return 0
        if args.check:
            problems = build.check(root, only=args.only)
            for p in problems:
                print("differs: " + p)
            print("figures: %s" % ("FAIL" if problems else "PASS"))
            return 1 if problems else 0
        _records, failures = build.run(root, only=args.only, png=not args.no_png)
    except build.FigureError as exc:
        print("figures: %s" % exc)
        return 1
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
