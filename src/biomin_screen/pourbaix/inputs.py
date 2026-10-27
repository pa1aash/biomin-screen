"""Fixed literature inputs of the carbonate runs: a verbatim subset of data/params.yaml and of the
evidence rows it cites, at a pinned parameter set.

The runs read the pinned parameters from a shipped snapshot, results/pourbaix/inputs/params_<sha7>.json.
The snapshot holds each entry exactly as the parameter file wrote it (no value is retyped), the blob id
and the sha256 of the source bytes. It is read as shipped; nothing here rebuilds it.
"""
import json

from biomin_screen.pourbaix.paths import POURBAIX_RESULTS

INPUTS_DIR = POURBAIX_RESULTS / "inputs"


class SnapshotError(RuntimeError):
    pass


def snapshot_path(params_sha):
    return INPUTS_DIR / ("params_%s.json" % params_sha[:7])


def load_snapshot(params_sha):
    """The shipped snapshot for params_sha."""
    path = snapshot_path(params_sha)
    if not path.is_file():
        raise SnapshotError("no snapshot %s" % path)
    snap = json.loads(path.read_text(encoding="utf-8"))
    if snap["params_sha"] != params_sha:
        raise SnapshotError("snapshot %s is for %s, not %s" % (path, snap["params_sha"], params_sha))
    return snap


class Params:
    """Read access to a snapshot: entries by key and evidence rows by row id."""

    def __init__(self, snap):
        self.snap = snap
        self.sha = snap["params_sha"]

    def entry(self, key):
        try:
            return self.snap["entries"][key]
        except KeyError as exc:
            raise SnapshotError("key %s is not in the snapshot" % key) from exc

    def value(self, key):
        return self.entry(key)["value"]

    def unit(self, key):
        return self.entry(key)["unit"]

    def range(self, key):
        return self.entry(key)["range"]

    def row(self, row_id):
        try:
            return self.snap["rows"][row_id]
        except KeyError as exc:
            raise SnapshotError("row %s is not in the snapshot" % row_id) from exc

    def cite(self, key):
        """Short citation of a key: its status and source rows."""
        e = self.entry(key)
        return {"key": key, "status": e["status"], "sources": list(e.get("sources") or []),
                "params_sha": self.sha}
