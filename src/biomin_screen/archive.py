"""Large result documents are shipped gzip-compressed and unpacked on first use.

A file `results/.../name.json.gz` stands for `results/.../name.json`. `results/ARCHIVE.sha256` lists the sha256
of every unpacked file; `unpack` writes the files that are missing and `verify` compares the unpacked files with
that list. An unpacked file that already exists is never overwritten, so a regenerated output is kept.

    python -m biomin_screen.archive unpack|verify|pack
"""
import gzip
import hashlib
import sys
from pathlib import Path

from biomin_screen import _util

LISTING = "results/ARCHIVE.sha256"
MIN_BYTES = 100 * 1024


def _sha(data):
    return hashlib.sha256(data).hexdigest()


def listing(root):
    p = Path(root) / LISTING
    out = {}
    if p.is_file():
        for line in p.read_text(encoding="utf-8").splitlines():
            if line.strip():
                digest, name = line.split(None, 1)
                out[name.strip()] = digest
    return out


def unpack(root=None):
    """Write every archived file that is not on disk; returns the relative paths written."""
    root = Path(root) if root else _util.repo_root()
    written = []
    for gz in sorted((root / "results").rglob("*.json.gz")):
        target = gz.with_suffix("")
        if not target.exists():
            target.write_bytes(gzip.decompress(gz.read_bytes()))
            written.append(str(target.relative_to(root)))
    return written


def verify(root=None):
    """Problems found when the files are compared with the listing (an archived file that is not unpacked is read from
    its .gz); empty when all agree."""
    root = Path(root) if root else _util.repo_root()
    bad = []
    for name, digest in listing(root).items():
        p = root / name
        gz = p.with_name(p.name + ".gz")
        if p.is_file():
            data = p.read_bytes()
        elif gz.is_file():
            data = gzip.decompress(gz.read_bytes())
        else:
            bad.append("missing " + name)
            continue
        if _sha(data) != digest:
            bad.append("differs " + name)
    return bad


def pack(root=None):
    """Compress every plain JSON result over MIN_BYTES to name.json.gz (mtime 0, so the bytes are reproducible),
    remove the plain file from the shipped set and rewrite the listing. The plain files stay on disk."""
    root = Path(root) if root else _util.repo_root()
    entries = dict(listing(root))
    for p in sorted((root / "results").rglob("*.json")):
        if p.stat().st_size > MIN_BYTES and "dryrun" not in p.parts:  # dryrun/ holds test products
            data = p.read_bytes()
            p.with_name(p.name + ".gz").write_bytes(gzip.compress(data, 9, mtime=0))
            entries[str(p.relative_to(root))] = _sha(data)
    (root / LISTING).write_text("".join("%s  %s\n" % (d, n) for n, d in sorted(entries.items())), encoding="utf-8")
    return sorted(entries)


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    cmd = argv[0] if argv else "unpack"
    if cmd == "unpack":
        w = unpack()
        print("unpacked %d files" % len(w))
        return 0
    if cmd == "verify":
        bad = verify()
        for b in bad:
            print(b)
        print("archive: %s" % ("FAIL" if bad else "PASS"))
        return 1 if bad else 0
    if cmd == "pack":
        print("packed %d files" % len(pack()))
        return 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main())
