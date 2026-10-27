"""Figure system: RSC style, palette, panel letters, the figure checker and the builder.

Layout of the repository it works on:
  figures/style/   rsc_spec.yaml, rsc.mplstyle (generated), palette.yaml
  figures/src/     figN.py templates, schemas/*.json
  figures/         the built figures: <name>.pdf, <name>.png and the numeric sidecar <name>.json
"""
from pathlib import Path


def paths(root):
    root = Path(root)
    fig = root / "figures"
    return {
        "root": root,
        "style": fig / "style",
        "src": fig / "src",
        "schemas": fig / "src" / "schemas",
        "out": fig,
    }
