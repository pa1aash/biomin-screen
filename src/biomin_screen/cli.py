"""`biomin-screen`: the command line of the screening framework.

    biomin-screen tables regime|breakeven|inputs [--check]
    biomin-screen screen ...        the screen runs (see `biomin-screen screen --help`)
    biomin-screen ladder ...        the oxidation-onset ladder and the aluminium passivation window
    biomin-screen figures [--check]
"""
import argparse
import sys

from biomin_screen import _util


def _tables(args):
    from biomin_screen.tables import breakeven_table, input_tables, regime_table
    mod = {"regime": regime_table, "breakeven": breakeven_table, "inputs": input_tables}[args.which]
    root = _util.repo_root()
    if args.check:
        stale = mod.check(root)
        for p in stale:
            print("differs: %s" % p)
        print("tables %s: %s" % (args.which, "FAIL" if stale else "PASS"))
        return 1 if stale else 0
    for p in mod.write(root):
        print("wrote " + str(p.relative_to(root)))
    return 0


def main(argv=None):
    from biomin_screen import archive
    archive.unpack(_util.repo_root())
    argv = list(sys.argv[1:] if argv is None else argv)
    ap = argparse.ArgumentParser(prog="biomin-screen", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    t = sub.add_parser("tables", help="regenerate or check a table of the paper")
    t.add_argument("which", choices=("regime", "breakeven", "inputs"))
    t.add_argument("--check", action="store_true", help="compare with the shipped table instead of writing")
    t.set_defaults(fn=_tables)
    for name in ("screen", "ladder", "figures"):
        sub.add_parser(name, add_help=False)
    if argv and argv[0] in ("screen", "ladder", "figures"):
        return _dispatch(argv[0], argv[1:])
    args = ap.parse_args(argv)
    return args.fn(args)


def _dispatch(name, rest):
    if name == "screen":
        from biomin_screen.screen.__main__ import main as run
    elif name == "ladder":
        from biomin_screen.pourbaix.ladder import main as run
    else:
        from biomin_screen.figures.cli import main as run
    return run(rest) or 0


if __name__ == "__main__":
    sys.exit(main())
