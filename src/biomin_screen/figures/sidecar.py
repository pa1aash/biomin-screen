"""The numeric sidecar of a figure: the plotted series as rounded numbers, for the check.

PDF and PNG bytes depend on the platform and the font, so `figures --check` compares these
sidecars instead. A sidecar lists, per axes, the scales and limits, the tick positions and
labels, and every drawn artist with its data coordinates: lines, rectangles and other patches,
point and segment collections, images. All numbers are rounded to 6 significant digits and
compared with a relative tolerance of RTOL (plus ATOL for values that are zero up to noise).
Nothing in it depends on the font or the renderer.
"""
import json
import math

import numpy as np

SIG = 6
RTOL = 1e-6
ATOL = 1e-12


def _num(x):
    x = float(x)
    if math.isnan(x):
        return "nan"
    if math.isinf(x):
        return "inf" if x > 0 else "-inf"
    return float("%.*g" % (SIG, x))


def _arr(a):
    return [_num(v) for v in np.ravel(np.asarray(a, dtype=float))]


def _hex(c):
    from matplotlib.colors import to_hex
    try:
        return to_hex(c, keep_alpha=True)
    except ValueError:
        return str(c)


def _style(artist):
    ls = artist.get_linestyle()
    return str(ls if isinstance(ls, str) else tuple(ls))


def _line(ln):
    return {"kind": "line", "x": _arr(ln.get_xdata(orig=False)), "y": _arr(ln.get_ydata(orig=False)),
            "color": _hex(ln.get_color()), "linestyle": _style(ln), "marker": str(ln.get_marker())}


def _patch(p):
    from matplotlib.patches import Rectangle
    if isinstance(p, Rectangle):
        geom = [p.get_x(), p.get_y(), p.get_width(), p.get_height()]
        kind = "rect"
    else:
        geom = p.get_path().vertices
        kind = type(p).__name__
    return {"kind": kind, "geom": _arr(geom), "face": _hex(p.get_facecolor()), "hatch": str(p.get_hatch())}


def _collection(c):
    out = {"kind": type(c).__name__}
    if hasattr(c, "get_segments"):
        out["segments"] = [_arr(s) for s in c.get_segments()]
    else:
        out["offsets"] = _arr(c.get_offsets())
    return out


def _axes(ax):
    from matplotlib.collections import Collection
    from matplotlib.image import AxesImage
    from matplotlib.lines import Line2D
    from matplotlib.patches import Patch
    from matplotlib.spines import Spine
    out = {"xscale": ax.get_xscale(), "yscale": ax.get_yscale(),
           "xlim": _arr(ax.get_xlim()), "ylim": _arr(ax.get_ylim()),
           "xticks": _arr(ax.get_xticks()), "yticks": _arr(ax.get_yticks()),
           "xticklabels": [t.get_text() for t in ax.get_xticklabels()],
           "yticklabels": [t.get_text() for t in ax.get_yticklabels()],
           "xlabel": ax.get_xlabel(), "ylabel": ax.get_ylabel(), "panel": ax.get_title(loc="left")}
    items = []
    for ch in ax.get_children():
        if isinstance(ch, Line2D):
            items.append(_line(ch))
        elif isinstance(ch, Patch) and ch is not ax.patch and not isinstance(ch, Spine):
            items.append(_patch(ch))
        elif isinstance(ch, Collection):
            items.append(_collection(ch))
        elif isinstance(ch, AxesImage):
            items.append({"kind": "image", "data": _arr(ch.get_array())})
    out["artists"] = items
    return out


def series(fig, meta):
    """The sidecar document of a drawn figure; `meta` (id, name, inputs) is stored as given."""
    fig.canvas.draw()  # tick labels exist only after a draw
    return dict(meta, axes=[_axes(ax) for ax in fig.axes])


def dumps(doc):
    """One axes per block, one artist per line, so that a changed series shows as a small diff."""
    head = {k: v for k, v in doc.items() if k != "axes"}
    lines = ["{"]
    for k, v in head.items():
        lines.append(" %s: %s," % (json.dumps(k), json.dumps(v)))
    lines.append(' "axes": [')
    blocks = []
    for ax in doc["axes"]:
        rest = {k: v for k, v in ax.items() if k != "artists"}
        art = ",\n".join("   " + json.dumps(a) for a in ax["artists"])
        blocks.append('  {"frame": %s, "artists": [\n%s\n  ]}' % (json.dumps(rest), art))
    lines.append(",\n".join(blocks))
    lines.append(" ]")
    lines.append("}")
    return "\n".join(lines) + "\n"


def differences(a, b, rtol=RTOL, atol=ATOL, where="$"):
    """[message] for every place where two sidecar documents differ beyond the tolerance."""
    if isinstance(a, dict) and isinstance(b, dict):
        out = []
        for k in sorted(set(a) | set(b)):
            if k not in a or k not in b:
                out.append("%s.%s: present in one only" % (where, k))
            else:
                out += differences(a[k], b[k], rtol, atol, "%s.%s" % (where, k))
        return out
    if isinstance(a, list) and isinstance(b, list):
        if len(a) != len(b):
            return ["%s: length %d vs %d" % (where, len(a), len(b))]
        out = []
        for i, (x, y) in enumerate(zip(a, b)):
            out += differences(x, y, rtol, atol, "%s[%d]" % (where, i))
        return out
    if isinstance(a, (int, float)) and isinstance(b, (int, float)) and not isinstance(a, bool) and not isinstance(b, bool):
        if abs(a - b) <= rtol * max(abs(a), abs(b)) + atol:
            return []
        return ["%s: %r vs %r" % (where, a, b)]
    return [] if a == b else ["%s: %r vs %r" % (where, a, b)]
