"""Evidence-table schema and validator (data/params_README.md describes how the rows are used).

validate_rows() returns a list of "row_id: problem" strings; an empty list means the table is valid.
"""
import csv
import io
import re
from pathlib import Path

from biomin_screen import identifiers as R

COLUMNS = ["row_id", "thread", "doi", "locator", "quantity", "symbol", "value", "unit",
           "range_or_uncertainty", "conditions", "method", "grade", "extraction_route", "retrieved_at",
           "contrary", "retro_candidate", "notes"]
THREADS = ("T-A", "T-B", "T-C", "T-D", "T-E", "T-F", "T-G", "T-H", "T-I", "T-J", "T-K",
           "T-L", "T-M", "T-N", "T-O", "T-P", "T-Q", "T-R", "T-S", "T-T")
GRADES = ("A", "B", "C", "D")
ROUTES = ("full text", "SI", "abstract")
METHODS = ("experiment", "computation", "compilation")
QUALITATIVE = "qualitative"

_ROW_ID = re.compile(r"^T[A-T]-\d{3}$")
_DOI = re.compile(r"^10\.\d{4,9}/\S+$")
_SLUG = re.compile(r"^[a-z][a-z0-9_]*$")
_NUM = r"[-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?"
_VALUE = re.compile(r"^(?:<=|>=|<|>|≤|≥)?\s*%s$" % _NUM)
_RANGE = re.compile(r"^(?:±\s*%s%%?|\+%s\s*/\s*-%s|%s\s*\.\.\s*%s)$" % ((_NUM,) * 5))
_LOCATOR = re.compile(r"(\bp\.|\bpp\.|\bpage\b|\btable\b|\bfig|\beq|\bsection\b|\bsec\.|\bscheme\b|\babstract\b|\bSI\b|\bS\d)",
                      re.I)
_WHEN = re.compile(r"^\d{4}-\d{2}-\d{2}(?:T\d{2}:\d{2}(?::\d{2})?Z)?$")
_QUOTE = re.compile(r"[\"“]([^\"”]*)[\"”]")

_ureg = None


def ureg():
    global _ureg
    if _ureg is None:
        import pint

        _ureg = pint.UnitRegistry()
    return _ureg


def unit_ok(unit):
    if not unit or not unit.strip():
        return False
    if unit in ("1", "dimensionless"):
        return True
    try:
        ureg().parse_units(unit)
        return True
    except Exception:
        try:
            q = ureg().parse_expression(unit)
            return hasattr(q, "units") and float(getattr(q, "magnitude", 1)) == 1.0
        except Exception:
            return False


def number_range(text):
    """'lo..hi' -> (lo, hi) or None."""
    m = re.match(r"^\s*(%s)\s*\.\.\s*(%s)\s*$" % (_NUM, _NUM), text or "")
    return (float(m.group(1)), float(m.group(2))) if m else None


def read_csv(path):
    with open(path, newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        header = reader.fieldnames or []
        return header, list(reader)


def write_csv(path, rows):
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=COLUMNS, lineterminator="\n", quoting=csv.QUOTE_MINIMAL)
    w.writeheader()
    for r in rows:
        w.writerow({k: r.get(k, "") for k in COLUMNS})
    Path(path).write_text(buf.getvalue(), encoding="utf-8")


def validate_row(r):
    rid = r.get("row_id") or "?"
    errs = []

    def bad(msg):
        errs.append("%s: %s" % (rid, msg))

    if not _ROW_ID.match(rid):
        bad("row_id must look like TA-001")
    if r.get("thread") not in THREADS:
        bad("thread %r not in %s" % (r.get("thread"), THREADS))
    elif _ROW_ID.match(rid) and rid[:2] != r["thread"].replace("-", ""):
        bad("row_id prefix does not match thread")
    doi = (r.get("doi") or "").strip()
    if not _DOI.match(doi) or R.normalize_doi(doi) != doi.lower():
        bad("DOI syntax: %r" % doi)
    loc = (r.get("locator") or "").strip()
    if not loc:
        bad("locator missing")
    elif not _LOCATOR.search(loc):
        bad("locator %r names no page, table, figure, equation, section, SI item or abstract" % loc)
    if not _SLUG.match(r.get("quantity") or ""):
        bad("quantity must be a lower-case slug")
    unit = (r.get("unit") or "").strip()
    value = (r.get("value") or "").strip()
    rng = (r.get("range_or_uncertainty") or "").strip()
    if unit == QUALITATIVE:
        if not value:
            bad("qualitative row needs a value (the observed outcome)")
    else:
        if not unit_ok(unit):
            bad("unit does not parse: %r" % unit)
        if value and not _VALUE.match(value):
            bad("value is not numeric: %r" % value)
        if rng and not _RANGE.match(rng):
            bad("range_or_uncertainty not one of ±x, ±x%%, +a/-b, lo..hi: %r" % rng)
        if not value and not number_range(rng):
            bad("quantity row needs a numeric value or a lo..hi range")
    if not (r.get("conditions") or "").strip():
        bad("conditions missing (write n.s. for each unstated item)")
    method = (r.get("method") or "").strip()
    if not method.split(":")[0].strip() in METHODS:
        bad("method must start with experiment, computation or compilation: %r" % method)
    grade = r.get("grade")
    if grade not in GRADES:
        bad("grade %r not in A-D" % grade)
    route = r.get("extraction_route")
    if route not in ROUTES:
        bad("extraction_route %r not in %s" % (route, ROUTES))
    if route == "abstract" and grade in ("A", "B", "C"):
        bad("abstract-only rows are capped at grade D")
    if method.startswith("compilation") and grade in ("A", "B"):
        bad("a compilation (secondary citation) is graded C at best")
    if not _WHEN.match(r.get("retrieved_at") or ""):
        bad("retrieved_at must be an ISO date or UTC timestamp")
    if r.get("contrary") not in ("y", "n"):
        bad("contrary must be y or n")
    retro = (r.get("retro_candidate") or "").strip()
    if not (retro == "n" or re.match(r"^y:\s*\S", retro)):
        bad("retro_candidate must be n or 'y: <observed outcome>'")
    for field in ("notes", "conditions", "method", "value"):
        for q in _QUOTE.findall(r.get(field) or ""):
            if len(q.split()) >= 15:
                bad("quote in %s has %d words (limit 14)" % (field, len(q.split())))
    return errs


def validate_rows(rows, header=None):
    errs = []
    if header is not None and list(header) != COLUMNS:
        errs.append("header: expected %s, got %s" % (",".join(COLUMNS), ",".join(header)))
    seen = set()
    for r in rows:
        rid = r.get("row_id")
        if rid in seen:
            errs.append("%s: duplicate row_id" % rid)
        seen.add(rid)
        errs.extend(validate_row(r))
    return errs


def validate_file(path):
    header, rows = read_csv(path)
    return validate_rows(rows, header)
