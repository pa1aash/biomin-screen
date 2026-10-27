import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SRC = str(REPO / "src")
if SRC not in sys.path:
    sys.path.insert(0, SRC)


from biomin_screen import archive  # noqa: E402

archive.unpack(REPO)
