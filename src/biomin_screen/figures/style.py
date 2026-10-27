"""Load the generated RSC style and the palette; expose column widths and colours."""
from functools import lru_cache
from pathlib import Path

import yaml

from biomin_screen.figures import paths

CM_PER_IN = 2.54


def _root():
    from biomin_screen import _util
    return _util.repo_root()


@lru_cache(maxsize=4)
def _spec(style_dir):
    return yaml.safe_load((Path(style_dir) / "rsc_spec.yaml").read_text())


@lru_cache(maxsize=4)
def _palette(style_dir):
    return yaml.safe_load((Path(style_dir) / "palette.yaml").read_text())


def spec(root=None):
    return _spec(str(paths(root or _root())["style"]))


def palette(root=None):
    return _palette(str(paths(root or _root())["style"]))


def applied(root=None):
    return spec(root)["applied"]


class FontError(Exception):
    pass


def font_chain(root=None):
    """The figure font and its fallbacks, in order (applied.font_family)."""
    fam = applied(root)["font_family"]
    return [fam["value"]] + list(fam.get("fallbacks", []))


def _find(name):
    """Path of an installed font of family `name`, or None (no silent default font)."""
    from matplotlib import font_manager
    try:
        return font_manager.findfont(name, fallback_to_default=False)
    except ValueError:
        return None


def font(root=None):
    """The first installed font of the chain: {family, file, rank}.

    rank 0 is the preferred face of the chain. Raises FontError when no face of the chain is
    installed, rather than letting matplotlib fall back to its default.
    """
    chain = font_chain(root)
    for rank, name in enumerate(chain):
        path = _find(name)
        if path:
            return {"family": name, "file": path, "rank": rank}
    raise FontError("none of the figure fonts is installed: %s" % ", ".join(chain))


def use(root=None):
    """Select the Agg backend, apply rsc.mplstyle and pin the font.

    The style lists the whole chain; the font actually used is then set alone, so matplotlib can
    neither pick a different face of the list nor fall back silently.
    """
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    plt.rcdefaults()
    plt.style.use(str(paths(root or _root())["style"] / "rsc.mplstyle"))
    plt.rcParams["font.sans-serif"] = [font(root)["family"]]
    return plt


def width_in(kind, root=None):
    """Column width in inches: kind is 'single' or 'double'."""
    return float(applied(root)["width_%s_in" % kind]["value"])


def max_height_in(root=None):
    return float(applied(root)["max_height_in"]["value"])


def figsize(kind, height_cm, root=None):
    h = height_cm / CM_PER_IN
    if h > max_height_in(root):
        raise ValueError("height %.1f cm exceeds the RSC maximum" % height_cm)
    return (width_in(kind, root), h)


def min_font_pt(root=None):
    return float(applied(root)["font_size"]["value"])


def min_line_pt(root=None):
    return float(applied(root)["line_width_min"]["value"])


def categorical(name, root=None):
    """Okabe-Ito colour by name (hex)."""
    return palette(root)["categorical"]["okabe_ito"][name]["hex"]


def cycle(root=None):
    pal = palette(root)
    return [pal["categorical"]["okabe_ito"][n]["hex"] for n in pal["categorical"]["cycle"]]
