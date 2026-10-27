"""Provenance and guards of the production runs (fixed inputs).

Every production document records, besides the shared fields of biomin_screen.screen.run: the code version (git_sha), the sha256 of the
thresholds block, the sha256 of symbol_bindings.yaml (the file and its header hash), the gap tables' sha256 and the sha256 of the
K1 ladder (ladder.csv). The ladder hash is checked against the fixed value before any output: a different ladder stops the run.
"""
import hashlib
from pathlib import Path

from biomin_screen.screen import thresholds as thr

LADDER = Path("results") / "pourbaix" / "ladder" / "ladder.csv"
LADDER_SHA256 = "d7bdd907ab83e2153407cceda93f125289086402527066e3b2780b4a4c338526"   # sha256 of results/pourbaix/ladder/ladder.csv
BINDINGS = Path("configs") / "symbol_bindings.yaml"
GAP_TABLES = (Path("configs") / "gap_resolution.yaml", Path("configs") / "gap_resolution_ph.yaml")
THRESHOLDS_BLOCK_VERSION = 11
HEADER_PREFIX = "# sha256 of this file with this line removed: "


class Fixed(RuntimeError):
    """A fixed input differs from its specified value: the run stops."""


def sha256_file(path):
    """Plain hex sha256 of the raw bytes of a file."""
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def tagged(hexdigest):
    """The 'sha256:<hex>' form of the results schema."""
    return "sha256:" + hexdigest


def bindings_header_hash(path):
    """(recorded hash, recomputed hash) of symbol_bindings.yaml: the sha256 of the file with the hash line removed."""
    lines = Path(path).read_text(encoding="utf-8").splitlines(keepends=True)
    idx = [i for i, ln in enumerate(lines) if ln.startswith(HEADER_PREFIX)]
    if len(idx) != 1:
        raise Fixed("%s must hold exactly one header hash line" % path)
    body = "".join(lines[:idx[0]] + lines[idx[0] + 1:])
    return lines[idx[0]][len(HEADER_PREFIX):].strip(), hashlib.sha256(body.encode("utf-8")).hexdigest()


def check_fixed(root):
    """Raise Fixed unless the ladder hash and the bindings header hash are as specified."""
    root = Path(root)
    got = sha256_file(root / LADDER)
    if got != LADDER_SHA256:
        raise Fixed("ladder.csv sha256 %s differs from the fixed %s" % (got, LADDER_SHA256))
    rec, calc = bindings_header_hash(root / BINDINGS)
    if rec != calc:
        raise Fixed("symbol_bindings.yaml header hash %s does not match its body %s" % (rec, calc))
    return True


def extra(root):
    """The provenance fields of the fixed inputs (all optional in the results schema)."""
    root = Path(root)
    th = root / thr.COPY
    block = thr.split_copy(th.read_text(encoding="utf-8"))[1] if th.exists() else None
    rec, calc = bindings_header_hash(root / BINDINGS) if (root / BINDINGS).exists() else (None, None)
    return {
        "thresholds_block_version": THRESHOLDS_BLOCK_VERSION if block else None,
        "thresholds_block_sha256": tagged(hashlib.sha256(block.encode("utf-8")).hexdigest()) if block else None,
        "symbol_bindings_file": BINDINGS.as_posix() if (root / BINDINGS).exists() else None,
        "symbol_bindings_hash": tagged(sha256_file(root / BINDINGS)) if (root / BINDINGS).exists() else None,
        "symbol_bindings_header_hash": tagged(calc) if calc else None,
        "gap_table_hashes": {p.as_posix(): tagged(sha256_file(root / p)) for p in GAP_TABLES if (root / p).exists()} or None,
        "ladder_file": LADDER.as_posix() if (root / LADDER).exists() else None,
        "ladder_hash": tagged(sha256_file(root / LADDER)) if (root / LADDER).exists() else None,
    }
