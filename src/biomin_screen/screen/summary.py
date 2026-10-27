"""Results summary of a screen run, conforming to configs/results_schema.json."""
import hashlib
import json
import time
from pathlib import Path

from biomin_screen import __version__

SCHEMA_PATH = Path(__file__).resolve().parents[3] / "configs" / "results_schema.json"


def config_hash(config):
    """sha256 of the canonical JSON of a run configuration (sorted keys, compact)."""
    blob = json.dumps(config, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "sha256:" + hashlib.sha256(blob).hexdigest()


def git_state(root):
    """(code version, dirty flag): the package version, and False (the shipped code is not a working copy)."""
    return __version__, False


def provenance(root, config, prior_set, contract_sha=None):
    sha, dirty = git_state(root)
    prior_path = Path(prior_set.path)
    try:
        rel = prior_path.resolve().relative_to(Path(root).resolve()).as_posix()
    except ValueError:
        rel = prior_path.as_posix()
    return {"git_sha": sha, "git_dirty": dirty, "config_hash": config_hash(config),
            "prior_file": rel, "prior_file_hash": prior_set.sha256, "contract_sha": contract_sha}


SCHEMA_VERSION = "5"


def build(regimes, prov, mock, stability=None, required_precision=None, claims=None, study=None, extensions=None,
          stage_rows=None):
    """Assemble a results document (schema v5); regimes, stability, claims or stage_rows must be given."""
    doc = {"schema_version": SCHEMA_VERSION, "mock": bool(mock),
           "generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "provenance": prov}
    if regimes is not None:
        doc["regimes"] = regimes
    if stability is not None:
        doc["stability"] = stability
    if required_precision is not None:
        doc["required_precision"] = required_precision
    if claims is not None:
        doc["claims"] = claims
    if study is not None:
        doc["study"] = study
    if stage_rows is not None:
        doc["stage_rows"] = stage_rows
    if extensions:
        doc["extensions"] = extensions
    return doc


def load_schema(path=SCHEMA_PATH):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def validate(summary, schema=None):
    """Raise jsonschema.ValidationError unless summary conforms to the results schema."""
    import jsonschema
    jsonschema.validate(summary, schema or load_schema())


def write(summary, path):
    validate(summary)
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path
