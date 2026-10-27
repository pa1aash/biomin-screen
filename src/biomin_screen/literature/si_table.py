"""DOIs cited by the parameter table, generated from data/params.yaml and data/evidence_table.csv.

    python -m biomin_screen.literature.si_table [--out DIR] [--check]

Writes, under data/si_table/ (default):

    params_table_dois.csv  the DOIs of every source row of the parameter table, one per row under a `doi` header,
                           in the order of the keys of data/params.yaml

--check regenerates in memory and fails if the written file differs.
"""
import argparse
import sys
from pathlib import Path

from biomin_screen import _util
from biomin_screen.literature import evidence as E
from biomin_screen.literature import params as P

OUT = Path("data") / "si_table"
FILES = ("params_table_dois.csv",)


def dois_of(e, rows):
    out = []
    srcs = list(e.get("sources") or [])
    if e["prior"]["family"] == "categorical":
        for o in e["prior"]["options"]:
            srcs += [s for s in o.get("sources") or [] if s not in srcs]
    for s in srcs:
        d = rows[s]["doi"].lower()
        if d not in out:
            out.append(d)
    return out


def generate(root):
    root = Path(root)
    p = P.load_params(root / P.PARAMS, root)
    params = p.entries
    _, rows = E.read_csv(root / P.TABLE)
    rows = {r["row_id"]: r for r in rows}
    dois = []
    for e in params.values():
        dois += [d for d in dois_of(e, rows) if d not in dois]
    return {"params_table_dois.csv": "doi\n" + "\n".join(dois) + "\n"}


def main(argv=None):
    ap = argparse.ArgumentParser(prog="python -m biomin_screen.literature.si_table")
    ap.add_argument("--out")
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args(argv)
    root = _util.repo_root()
    out = Path(a.out) if a.out else root / OUT
    files = generate(root)
    if a.check:
        stale = [n for n, t in files.items() if not (out / n).exists() or (out / n).read_text(encoding="utf-8") != t]
        print("si_table: %s" % ("up to date" if not stale else "stale: %s" % ", ".join(stale)))
        return 1 if stale else 0
    out.mkdir(parents=True, exist_ok=True)
    for n, t in files.items():
        (out / n).write_text(t, encoding="utf-8")
    print("wrote %s (%d DOIs)" % (", ".join(str(out / n) for n in files),
                                  len(files["params_table_dois.csv"].split()) - 1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
