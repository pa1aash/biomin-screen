#!/usr/bin/env python3
"""Print the headline quantities of the paper, each read from the file that carries it.

    python scripts/numbers.py            print the table
    python scripts/numbers.py --json     also write results/numbers.json

The list is data/headline_numbers.yaml: for each quantity, the file it is read from, the key path (or a regular
expression for a text file), the format and the unit. Quantities that bound each other (a low and a high end) are
printed on one line as an interval. Run `make tables` first: most quantities come from the generated tables in
results/tables/. The paper prints each value with the format given here, so the two can be compared digit by digit.
"""
import json
import math
import re
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from biomin_screen import archive  # noqa: E402
SPEC = ROOT / "data" / "headline_numbers.yaml"


def lookup(doc, key):
    for part in key.split("/"):
        doc = doc[part] if isinstance(doc, dict) else doc[int(part)]
    return doc


def section_text(text, heading):
    out, level = [], None
    for line in text.splitlines():
        m = re.match(r"^(#+)\s+(.*?)\s*$", line)
        if level is None:
            if m and m.group(2) == heading:
                level = len(m.group(1))
            continue
        if m and len(m.group(1)) <= level:
            break
        out.append(line)
    return "\n".join(out)


def scalar(s):
    s = s.strip()
    if re.fullmatch(r"-?[0-9][0-9 ]*(\.[0-9]+)?([eE][-+]?[0-9]+)?", s):
        s = s.replace(" ", "")
        return int(s) if re.fullmatch(r"-?[0-9]+", s) else float(s)
    return s


def read(spec, cache):
    path = ROOT / spec["source"]
    if path not in cache:
        text = path.read_text(encoding="utf-8")
        cache[path] = json.loads(text) if path.suffix == ".json" else yaml.safe_load(text) if path.suffix in (".yaml", ".yml") else text
    doc = cache[path]
    if spec.get("key"):
        doc = lookup(doc, spec["key"])
    if spec.get("pattern"):
        if spec.get("section"):
            doc = section_text(doc, spec["section"])
        found = [scalar(m.group(1)) for m in re.finditer(spec["pattern"], doc, re.M)]
        red = spec.get("reduce", "first")
        doc = len(found) if red == "count" else found[0] if red == "first" else (max(found) if red == "max" else min(found))
    return doc


def show(value, fmt):
    if fmt == "power":
        a, b = re.fullmatch(r"\s*([0-9]+)\s*\*\*\s*([0-9]+)\s*", str(value)).groups()
        return "%s^%s" % (a, b)
    if fmt == "text" or fmt.startswith("date:"):
        if fmt.startswith("date:"):
            import datetime
            return datetime.date.fromisoformat(str(value)).strftime(fmt[5:])
        return str(value)
    if fmt.startswith("sci:"):
        digits = int(fmt[4:])
        if value == 0:
            return ("{:.%df}" % digits).format(0.0)
        exp = int(math.floor(math.log10(abs(value))))
        mant = value / 10 ** exp
        if round(abs(mant), digits) >= 10:
            mant, exp = mant / 10, exp + 1
        return "{:.{d}f}e{e:+d}".format(mant, d=digits, e=exp)
    return ("{:%s}" % fmt).format(value)


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    archive.unpack(ROOT)
    spec = yaml.safe_load(SPEC.read_text(encoding="utf-8"))["numbers"]
    cache, rows, done = {}, [], {}
    for e in spec:
        try:
            value = read(e, cache)
            text = show(value, e.get("format", "g"))
        except (OSError, KeyError, IndexError, ValueError) as exc:
            raise SystemExit("%s: cannot read %s (%s). Run `make tables` first." % (e["id"], e["source"], exc))
        done[e["id"]] = {"value": value, "text": text, "unit": e.get("unit", "")}
        rows.append(e)
    printed = set()
    width = max(len(e["id"]) for e in rows)
    for e in rows:
        i = e["id"]
        if i in printed:
            continue
        stem = re.sub(r"_(low|lo|high|hi)$", "", i)
        mate = next((o["id"] for o in rows if o["id"] != i and re.sub(r"_(low|lo|high|hi)$", "", o["id"]) == stem
                     and re.search(r"_(low|lo|high|hi)$", i) and re.search(r"_(low|lo|high|hi)$", o["id"])), None)
        if mate and mate not in printed and re.search(r"_(low|lo)$", i):
            a, b = done[i], done[mate]
            print("%-*s  %s to %s %s" % (width, stem, a["text"], b["text"], a["unit"]))
            printed |= {i, mate}
        elif mate and mate not in printed:
            continue
        else:
            d = done[i]
            print("%-*s  %s %s" % (width, i, d["text"], d["unit"]))
            printed.add(i)
    if "--json" in argv:
        out = ROOT / "results" / "numbers.json"
        out.write_text(json.dumps(done, indent=1, sort_keys=True) + "\n", encoding="utf-8")
        print("wrote %s" % out.relative_to(ROOT))
    return 0


if __name__ == "__main__":
    sys.exit(main())
