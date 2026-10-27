"""Run provenance and checks against the results schema.

The `provenance` block follows the results schema (configs/results_schema.json, $defs/provenance) field
by field. The schema's `prior_file` is the run configuration here, since the Pourbaix runs have no prior
file. `provenance_pourbaix` carries what the schema block has no room for: the cache hash, the Materials
Project database version and the library versions. The code version is `biomin_screen.__version__`.
"""
import datetime as dt
import hashlib
import json
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

import biomin_screen
from biomin_screen.pourbaix import cache
from biomin_screen.pourbaix.paths import REPO

SCHEMA_PATH = "configs/results_schema.json"
LIBS = ["pymatgen", "mp-api", "emmet-core", "numpy", "scipy", "rdkit", "ase", "pyyaml"]


def utc_now():
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def code_version():
    return biomin_screen.__version__


def lib_versions():
    out = {}
    for n in LIBS:
        try:
            out[n] = version(n)
        except PackageNotFoundError:
            out[n] = None
    return out


def block(config_meta):
    """(schema-conformant provenance, extra Pourbaix provenance)."""
    m = cache.manifest()
    w4 = {"git_sha": code_version(), "git_dirty": False, "config_hash": config_meta["config_hash"],
          "prior_file": config_meta["path"], "prior_file_hash": config_meta["file_hash"],
          "contract_sha": None}
    extra = {"cache_dir": cache.CACHE_DIR.relative_to(REPO).as_posix(),
             "cache_hash": cache.cache_hash(), "mp_database_version": m["mp_database_version"],
             "mp_thermo_types": m["thermo_types"], "library_versions": lib_versions(),
             "schema": {"path": SCHEMA_PATH}}
    return w4, extra


def validate_against(schema_path, instance, subschema=None):
    """Validate `instance` against the schema file `schema_path` (relative to the repository)."""
    import jsonschema

    schema = json.loads((REPO / schema_path).read_text(encoding="utf-8"))
    if subschema:
        schema = {**schema["$defs"][subschema], "$defs": schema.get("$defs", {})}
    v = jsonschema.Draft202012Validator(schema)
    errs = sorted(v.iter_errors(instance), key=lambda e: list(e.absolute_path))
    return {"checked": True, "schema": schema_path, "subschema": subschema,
            "valid": not errs,
            "errors": [{"path": "/".join(str(p) for p in e.absolute_path) or "(root)",
                        "message": e.message[:300]} for e in errs]}


def sha256_file(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()
