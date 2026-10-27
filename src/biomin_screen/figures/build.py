"""Discover figure templates, read and validate their inputs, render, check and write outputs.

A template is figures/src/figN.py defining:
  FIGURE  dict with id (the file stem), name (the output file stem), description (what the figure
          shows, in a sentence, since the figure holds no legend or labels), width ('single' |
          'double'), height_cm, schema (repository-relative path of the JSON Schema the main input
          must satisfy), input (repository-relative path of the main input file), and optionally
          aux: {name: repository-relative path} for further inputs (the parameter rows behind a
          design axis, for example);
  build(data, root, aux) -> matplotlib Figure.

Inputs are the stored outputs under results/ and data/ and are read from there: .json, .yaml and
.csv files (a CSV is read as {"columns": [...], "rows": [{column: text}, ...]}; lines starting with
'#' are comments). Nothing is fetched.

After saving, the PDF itself is checked: every text span in it must lie inside the box of a
tick label, an axis title, a colour-bar label or a panel letter (checker.check_pdf_text).
Each figure also writes figures/<name>.json, the numeric sidecar (biomin_screen.figures.sidecar).
"""
import csv
import gc
import importlib.util
import io
import json
import logging
import re
import tempfile
import time
from pathlib import Path

import yaml

from biomin_screen.figures import checker, paths, schema, sidecar, style

_FIG_RE = re.compile(r"^fig(\d+)\.py$")
_REQUIRED = ("id", "name", "description", "width", "height_cm", "schema", "input")


class FigureError(Exception):
    pass


def discover(root):
    src = paths(root)["src"]
    found = []
    for p in src.iterdir() if src.is_dir() else []:
        m = _FIG_RE.match(p.name)
        if m:
            found.append((int(m.group(1)), p))
    return [p for _, p in sorted(found)]


def load_template(path):
    spec = importlib.util.spec_from_file_location("biomin_figure_" + path.stem, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    fig = getattr(mod, "FIGURE", None)
    if not isinstance(fig, dict) or not callable(getattr(mod, "build", None)):
        raise FigureError("%s: needs FIGURE and build(data, root, aux)" % path.name)
    missing = [k for k in _REQUIRED if k not in fig]
    if missing:
        raise FigureError("%s: FIGURE lacks %s" % (path.name, ", ".join(missing)))
    if fig["id"] != path.stem:
        raise FigureError("%s: FIGURE id %r does not match the file name" % (path.name, fig["id"]))
    if fig["width"] not in ("single", "double"):
        raise FigureError("%s: width must be single or double" % path.name)
    return mod


def parse_csv(text):
    """{"columns": [...], "rows": [{column: text}, ...]} of a CSV output file.

    Lines starting with '#' are comments (the benchmark file opens with one). Every cell stays
    a string; a template converts the columns it plots and refuses what it cannot read.
    """
    lines = [ln for ln in text.splitlines() if not ln.startswith("#")]
    reader = csv.DictReader(io.StringIO("\n".join(lines)))
    return {"columns": list(reader.fieldnames), "rows": [dict(r) for r in reader]}


def read(path):
    """The parsed content of an input file: JSON, YAML or CSV by extension."""
    path = Path(path)
    if not path.exists():
        raise FigureError("input %s is missing" % path)
    text = path.read_text(encoding="utf-8")
    if path.suffix == ".csv":
        return parse_csv(text)
    if path.suffix == ".json":
        return json.loads(text)
    if path.suffix in (".yaml", ".yml"):
        return yaml.safe_load(text)
    raise FigureError("%s: cannot read a %s input" % (path, path.suffix))


def load_input(root, mod):
    """The main input of a template, checked against its schema."""
    fig = mod.FIGURE
    data = read(Path(root) / fig["input"])
    sch, cite = schema.resolve(fig["schema"], root)
    errs = schema.validate(data, sch)
    if errs:
        raise FigureError("%s: input does not match %s:\n  %s" % (fig["id"], cite, "\n  ".join(errs[:20])))
    return data


def load_aux(root, mod):
    """{name: data} for FIGURE["aux"]."""
    return {name: read(Path(root) / ref) for name, ref in mod.FIGURE.get("aux", {}).items()}


def make_figure(root, mod, data, aux=None):
    plt = style.use(root)
    fig = mod.build(data, root, aux or {})
    return plt, fig


def render(root, mod, data, out_dir, aux=None, png=True):
    """Draw, check and write one figure: <name>.pdf, <name>.png (when png) and <name>.json.

    Returns {"id", "name", "files": [written paths]}.
    """
    root = Path(root)
    fid, name = mod.FIGURE["id"], mod.FIGURE["name"]
    plt, fig = make_figure(root, mod, data, aux)
    try:
        expected = style.figsize(mod.FIGURE["width"], mod.FIGURE["height_cm"], root)
        got = tuple(fig.get_size_inches())
        if any(abs(a - b) > 1e-3 for a, b in zip(expected, got)):
            raise FigureError("%s: size %s differs from FIGURE width/height_cm %s" % (fid, got, expected))
        problems = checker.check_rsc(fig, root)
        if problems:
            raise checker.FigureCheckError(["%s: %s" % (fid, x) for x in problems])
        out_dir = Path(out_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        pdf = out_dir / (name + ".pdf")
        side = out_dir / (name + ".json")
        boxes = checker.allowed_text_boxes(fig)
        fig.savefig(pdf, format="pdf", metadata={"Creator": None, "Producer": None, "CreationDate": None})
        problems = checker.check_pdf_text(pdf, boxes)
        if problems:
            raise checker.FigureCheckError(["%s: %s" % (fid, x) for x in problems])
        written = [pdf]
        if png:
            dpi = int(style.applied(root)["raster_dpi"]["value"])
            f = out_dir / (name + ".png")
            fig.savefig(f, format="png", dpi=dpi, metadata={"Software": None})
            written.append(f)
        inputs = [mod.FIGURE["input"]] + [v for _k, v in sorted(mod.FIGURE.get("aux", {}).items())]
        doc = sidecar.series(fig, {"id": fid, "name": name, "inputs": inputs})
        side.write_text(sidecar.dumps(doc), encoding="utf-8")
        written.append(side)
    finally:
        plt.close(fig)
        gc.collect()
    return {"id": fid, "name": name, "files": written}


def select(root, only=None):
    """The template modules to build; `only` holds figure ids (fig4) or names (retrodiction)."""
    mods = [load_template(p) for p in discover(root)]
    if not only:
        return mods
    wanted = set(only)
    known = {m.FIGURE["id"] for m in mods} | {m.FIGURE["name"] for m in mods}
    unknown = sorted(wanted - known)
    if unknown:
        raise FigureError("no such figure: %s (known: %s)" % (", ".join(unknown), ", ".join(sorted(known))))
    return [m for m in mods if m.FIGURE["id"] in wanted or m.FIGURE["name"] in wanted]


def run(root, only=None, out_dir=None, png=True, log=print):
    """Build the figures (or those in `only`) into out_dir (default figures/). Returns (records, failures)."""
    root = Path(root)
    out_dir = Path(out_dir) if out_dir else paths(root)["out"]
    records, failures = [], []
    logging.getLogger("fontTools").setLevel(logging.ERROR)  # system fonts with malformed tables warn on every embed
    log("font: %s" % style.font(root)["family"])
    for mod in select(root, only):
        fid = mod.FIGURE["id"]
        t0 = time.time()
        try:
            data = load_input(root, mod)
            rec = render(root, mod, data, out_dir, aux=load_aux(root, mod), png=png)
            records.append(rec)
            log("%s: ok %.1f s -> %s" % (fid, time.time() - t0, ", ".join(p.name for p in rec["files"])))
        except checker.FigureCheckError as exc:
            failures.extend(exc.problems)
            log("%s: checker FAIL\n  %s" % (fid, "\n  ".join(exc.problems)))
        except FigureError as exc:
            failures.append(str(exc))
            log("%s: FAIL %s" % (fid, exc))
        gc.collect()
    return records, failures


def check(root, only=None, log=print):
    """Rebuild each figure into a scratch directory and compare its sidecar with the shipped one.

    The comparison is numeric (biomin_screen.figures.sidecar: 6 significant digits, relative
    tolerance 1e-6); PDF and PNG bytes are not compared, since they differ across platforms and
    fonts. Returns a list of problems (empty when every figure agrees).
    """
    root = Path(root)
    problems = []
    with tempfile.TemporaryDirectory(prefix="biomin_figures_") as tmp:
        records, failures = run(root, only=only, out_dir=tmp, png=False, log=log)
        problems += failures
        shipped_dir = paths(root)["out"]
        for rec in records:
            name = rec["name"]
            fresh = json.loads((Path(tmp) / (name + ".json")).read_text())
            shipped = shipped_dir / (name + ".json")
            if not shipped.exists():
                problems.append("%s: no shipped sidecar %s" % (name, shipped.relative_to(root)))
                continue
            for ext in (".pdf", ".png"):
                if not (shipped_dir / (name + ext)).exists():
                    problems.append("%s: no shipped %s" % (name, name + ext))
            diffs = sidecar.differences(json.loads(shipped.read_text()), fresh)
            for d in diffs[:10]:
                problems.append("%s: %s" % (name, d))
            if len(diffs) > 10:
                problems.append("%s: ... and %d more differences" % (name, len(diffs) - 10))
            log("%s: %s" % (name, "differs" if diffs else "matches the shipped sidecar"))
    return problems
