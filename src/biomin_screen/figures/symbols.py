"""Axis titles from the symbol register (data/symbols.yaml).

The register gives each symbol id its LaTeX form and SI unit; the titles set it as mathtext in
the figure font. Quantities the screen reports in units of k_B T, and axes that need a unit
other than SI (degrees, V on a named scale), are composed here from register ids only.
"""
from functools import lru_cache
from pathlib import Path

import yaml

REGISTER = "data/symbols.yaml"

# Units written the way the register writes them -> axis-title form. A unit not listed here is
# printed as the register gives it.
_UNIT_TEXT = {"1": None, "rad": "rad", "V": "V", "J m^-2": r"J m$^{-2}$", "J mol^-1": r"J mol$^{-1}$"}


@lru_cache(maxsize=4)
def _symbols(path):
    return {s["id"]: s for s in yaml.safe_load(Path(path).read_text())["symbols"]}


def symbols(root):
    """data/symbols.yaml as {id: entry}."""
    return _symbols(str(Path(root) / REGISTER))


def entry(sym_id, root):
    table = symbols(root)
    if sym_id not in table:
        raise KeyError("symbol %r not in %s" % (sym_id, REGISTER))
    return table[sym_id]


def symbol(sym_id, root):
    """The register's LaTeX form as mathtext."""
    return "$%s$" % entry(sym_id, root)["latex"]


def unit_text(sym_id, root):
    u = entry(sym_id, root)["unit"]
    return _UNIT_TEXT.get(u, u)


def axis_title(sym_id, root, unit=None):
    """'symbol (unit)'; unit overrides the register's SI unit (for example '°' for an angle)."""
    u = unit if unit is not None else unit_text(sym_id, root)
    return symbol(sym_id, root) if not u else "%s (%s)" % (symbol(sym_id, root), u)
