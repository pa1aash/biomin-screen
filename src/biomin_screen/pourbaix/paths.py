"""Repository paths used by the Pourbaix and window code."""
from pathlib import Path

from biomin_screen._util import repo_root

REPO = repo_root(Path(__file__))
POURBAIX_RESULTS = REPO / "results" / "pourbaix"
CACHE_DIR = POURBAIX_RESULTS / "cache"
CONFIG_DIR = POURBAIX_RESULTS / "config"
PARAMS_FILE = REPO / "data" / "params.yaml"


def rel(path):
    """Repository-relative POSIX path of `path`."""
    return Path(path).resolve().relative_to(REPO).as_posix()
