"""Run configurations for the Pourbaix and window code.

Every physical input in a run configuration is a mapping with a `source`:

- `data/params.yaml`: the value is read from the parameter file under `key`. A missing file or key
  is an error, never a silent default.
- `mock`: a placeholder for pipeline checks. Allowed only when the caller passes
  allow_mock=True (the `--mock` flag); the configuration must then also say `mock: true`.
- `choice`: a method choice made and justified in the configuration (no number involved).

The pH axis of a slurry-regime run needs an explicit grid `pH: {min, max}` in the run configuration,
whose bounds are `data/params.yaml` (with its key) or `mock` (the grid then also says `mock: true`).

Numerical settings (grid sizes, tolerances) live under `numerics` and carry no source.
"""
import hashlib
import json
from pathlib import Path

import yaml

from biomin_screen.pourbaix.paths import PARAMS_FILE, REPO

SOURCES = {"data/params.yaml", "mock", "choice"}


class MockRefused(RuntimeError):
    """A mock value was found while mock values are not allowed."""


class ConfigError(ValueError):
    pass


def canonical_hash(obj):
    """sha256 of the canonical JSON (sorted keys, no whitespace), the results schema's config_hash rule."""
    text = json.dumps(obj, sort_keys=True, separators=(",", ":"))
    return "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()


def file_hash(path):
    return "sha256:" + hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _is_input(node):
    return isinstance(node, dict) and "source" in node


def _walk(node, path=()):
    if _is_input(node):
        yield path, node
        return
    if isinstance(node, dict):
        for k, v in node.items():
            yield from _walk(v, path + (k,))
    elif isinstance(node, list):
        for i, v in enumerate(node):
            yield from _walk(v, path + (str(i),))


def _lit_value(node, lit_params):
    if lit_params is None:
        raise ConfigError("data/params.yaml is not available; value %s cannot be resolved" % node.get("key"))
    cur = lit_params
    for part in str(node["key"]).split("."):
        if not isinstance(cur, dict) or part not in cur:
            raise ConfigError("data/params.yaml has no key %s" % node["key"])
        cur = cur[part]
    return cur["value"] if isinstance(cur, dict) and "value" in cur else cur


def _set(tree, path, value):
    cur = tree
    for k in path[:-1]:
        cur = cur[int(k)] if isinstance(cur, list) else cur[k]
    last = path[-1]
    if isinstance(cur, list):
        cur[int(last)] = value
    else:
        cur[last] = value


def _check_ph_axis(raw):
    """The slurry-regime pH axis must be an explicit run-config grid."""
    ph = raw.get("regimes", {}).get("R-slurry", {}).get("pH")
    if not isinstance(ph, dict) or not all(_is_input(ph.get(b)) for b in ("min", "max")):
        raise ConfigError("the slurry regime needs an explicit pH grid in the run configuration: "
                          "pH: {min: {...}, max: {...}} with sourced bounds")
    srcs = {ph[b]["source"] for b in ("min", "max")}
    if not srcs <= {"mock", "data/params.yaml"}:
        raise ConfigError("pH grid bounds must be sourced from data/params.yaml or mock, not %s"
                          % sorted(srcs))
    for b in ("min", "max"):
        if ph[b]["source"] == "data/params.yaml" and not ph[b].get("key"):
            raise ConfigError("pH.%s: a data/params.yaml bound must cite its key" % b)
    if "mock" in srcs and ph.get("mock") is not True:
        raise ConfigError("a mock pH grid must be marked mock: true")


def load(path, allow_mock=False, params_path=PARAMS_FILE):
    """Load and resolve a run configuration.

    Returns (resolved, meta). `resolved` has every input node replaced by its value; `meta`
    holds the raw configuration, its hashes and the source of every input.
    """
    path = Path(path)
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict) or "regimes" not in raw:
        raise ConfigError("%s: not a run configuration" % path)
    is_mock = bool(raw.get("mock"))
    if is_mock and not allow_mock:
        raise MockRefused("%s is a mock configuration (mock: true); pass --mock to run it" % path)

    _check_ph_axis(raw)

    lit_params = None
    if Path(params_path).is_file():
        lit_params = yaml.safe_load(Path(params_path).read_text(encoding="utf-8"))

    resolved = json.loads(json.dumps(raw))
    sources = []
    for p, node in _walk(raw):
        src = node["source"]
        if src not in SOURCES:
            raise ConfigError("%s: unknown source %r" % ("/".join(p), src))
        if src == "mock":
            if not allow_mock:
                raise MockRefused("%s is a mock value; pass --mock to use it" % "/".join(p))
            if not is_mock:
                raise MockRefused("%s is a mock value in a configuration without mock: true"
                                  % "/".join(p))
            value = node["value"]
        elif src == "data/params.yaml":
            value = _lit_value(node, lit_params)
        else:
            value = node["value"]
        if "unit" in node:
            # keep the unit (and basis) next to the value so the consumer can check it
            value = {"value": value, "unit": node["unit"],
                     **({"basis": node["basis"]} if "basis" in node else {})}
        _set(resolved, p, value)
        sources.append({"input": "/".join(p), "source": src, "value": value,
                        **({"key": node.get("key")} if src == "data/params.yaml" else {}),
                        **({"note": node["note"]} if "note" in node else {})})

    meta = {"path": path.resolve().relative_to(REPO).as_posix() if path.resolve().is_relative_to(REPO)
            else str(path), "file_hash": file_hash(path), "config_hash": canonical_hash(raw),
            "mock": is_mock, "sources": sources}
    return resolved, meta
