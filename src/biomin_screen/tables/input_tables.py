"""The input tables, generated from the parameter file, the onset ladder and the benchmark.

`biomin-screen tables inputs` reads the files named in INPUTS and writes, in results/tables:
  input_tables.csv   the sourced inputs of the dissolution test (parameters), the governing reaction of each ladder
                     entry on the experimental route with its upper bound and margin and the database comparator with
                     its measured error (benchmark), every oxidation reaction of the ladder (reactions), the database
                     benchmark per phase (dft) and the conversion steps (conversion), as rows of plain text;
  input_tables.json  the numbers of the tables under their names, with the sha256 of each input, and the speciation
                     fractions of carbonate and phosphate, computed here from the specified acid constants at the
                     specified slurry pH values.
Nothing in a table is typed: every number is read from an input file, and every source is cited by its DOI.
`--check` regenerates in memory and compares byte for byte.
"""
import csv
import hashlib
import io
import json
import re
from pathlib import Path

import yaml

from biomin_screen.literature import evidence as E
from biomin_screen.literature import params as P
from biomin_screen.literature import si_table
from biomin_screen.tables import paths
from biomin_screen.tables.regime_table import Num, plain_of
from biomin_screen.screen import k2_carbonate

INPUTS = {
    "params": "data/params.yaml",
    "labels": "data/si_table/labels.yaml",
    "ladder": "results/pourbaix/ladder/ladder.csv",
    "benchmark": "results/pourbaix/benchmark/formation_benchmark_table.csv",
    "screen": "configs/screen.yaml",
}
OUT_CSV, OUT_JSON = "input_tables.csv", "input_tables.json"


class InputTableError(Exception):
    pass


# ---------------------------------------------------------------- the sourced inputs of the dissolution test

# (table key, parameter key, name stem); the groups are printed in this order
PARAM_GROUPS = (
    ("solubility products, log10 K_sp per formula unit", (
        ("log_ksp_calcite", "log10_ksp_calcite", "KspCalcite"),
        ("log_ksp_aragonite", "log10_ksp_aragonite_25c_i0", "KspAragonite"),
        ("log_ksp_acc", "log10_ksp_acc", "KspAcc"),
        ("log_ksp_hap", "log10_ksp_hap", "KspHap"),
        ("log_ksp_acp", "log10_ksp_acp", "KspAcp"),
        ("log_ksp_btcp", "log10_ksp_btcp", "KspBtcp"),
        ("log_ksp_atcp", "log10_ksp_atcp", "KspAtcp"),
        ("log_ksp_ocp", "log10_ksp_ocp", "KspOcp"),
        ("log_ksp_ocp_ca4h", "log10_ksp_ocp_ca4h_basis", "KspOcpCah"),
        ("log_ksp_brushite", "log10_ksp_brushite", "KspBrushite"),
        ("log_ksp_li3po4", "log10_ksp_li3po4", "KspLiPhos"),
    )),
    ("acid constants (dissociation, pK)", (
        ("pk1_carbonic", "pk1_carbonic", "PkCarbonicA"),
        ("pk2_carbonic", "pk2_carbonic", "PkCarbonicB"),
        ("pka1_phosphoric", "pka1_h3po4", "PkPhosA"),
        ("pka2_phosphoric", "pka2_h3po4", "PkPhosB"),
        ("pka3_phosphoric", "pka3_h3po4", "PkPhosC"),
        ("pkw", "pkw", "PkWater"),
    )),
)
# Rows of the carbonate framings of K2 (row parameter key -> framing): each must read the K_sp key that the
# dissolution test binds in screen.yaml.
K2_FRAMING_OF = {"log10_ksp_calcite": "calcite", "log10_ksp_aragonite_25c_i0": "aragonite", "log10_ksp_acc": "ACC"}
PRIOR_WORD = {"fixed": "fixed", "uniform": "uniform", "normal": "normal", "loguniform": "log-uniform"}


def check_k2_keys(screen_cfg):
    """Every carbonate row of the parameter table reads the K_sp key that K2 binds; the K2 framings all have a row."""
    bound = k2_carbonate.ksp_keys(screen_cfg)
    rows = {f: k for k, f in K2_FRAMING_OF.items()}
    if set(bound) != set(rows):
        raise InputTableError("K2 framings %s, carbonate rows of the parameter table %s" % (sorted(bound), sorted(rows)))
    table_keys = {pkey for _t, members in PARAM_GROUPS for _j, pkey, _s in members}
    bad = ["%s: the parameter table reads %s, K2 reads %s" % (f, rows[f], bound[f]) for f in sorted(bound)
           if rows[f] != bound[f] or rows[f] not in table_keys]
    if bad:
        raise InputTableError("; ".join(bad))


def param_rows(docs):
    params, rows, labels = docs["params"], docs["evidence"], docs["labels"]
    check_k2_keys(docs["screen"])
    out = []
    for title, members in PARAM_GROUPS:
        group = []
        for jkey, pkey, stem in members:
            if pkey not in params:
                raise InputTableError("data/params.yaml has no key %s" % pkey)
            e = params[pkey]
            fam = e["prior"]["family"]
            if fam not in PRIOR_WORD:
                raise InputTableError("%s: prior family %s has no table word" % (pkey, fam))
            val = Num("NumPar%sVal" % stem, "params/%s/value" % jkey, float(e["value"]), ".2f")
            if fam == "fixed":
                rng = ["fixed"]
            else:
                rng = [Num("NumPar%sLo" % stem, "params/%s/min" % jkey, float(e["range"]["min"]), ".2f"), " to ",
                       Num("NumPar%sHi" % stem, "params/%s/max" % jkey, float(e["range"]["max"]), ".2f")]
            dois = si_table.dois_of(e, rows)
            cite = ", ".join(dois) if dois else "--"
            # a labelled alternative (`of:`) prints the label of the quantity it stands for
            label = _plain(labels[e.get("of") or pkey]["label"])
            group.append(([label], [val], rng, [PRIOR_WORD[fam]], [e.get("best_grade") or "--"], [cite]))
        out.append((title, group))
    return out


# ---------------------------------------------------------------- the benchmark and reaction tables: the onset ladder

PHASE_NAME = {
    "brushite": "brushite",
    "ACP": "ACP (beta-TCP reference)",
    "HAp": "HAp",
    "OCP": "OCP",
    "b-TCP": "beta-TCP",
    "a-TCP": "alpha-TCP",
    "Li3PO4": "Li3PO4",
    "Ca2P2O7": "Ca2P2O7",
    "Ca(PO3)2 / Ca-polyphosphate glass": "Ca(PO3)2",
    "AlPO4": "AlPO4",
    "Al(PO3)3": "Al(PO3)3",
    "Al-polyphosphate (R1 gel)": "Al-polyphosphate gel",
    "(LiPO3)n Hydro-Quebec film": "(LiPO3)n (baseline)",
    "baked aluminophosphate (Tsinghua)": "baked aluminophosphate (baseline)",
    "CaSiO3": "CaSiO3 (comparator)",
    "Ca2SiO4": "Ca2SiO4 (comparator)",
    "Li2SiO3": "Li2SiO3 (comparator)",
    "CaCO3": "calcium carbonate (control)",
}
GLASS_PHASES = ("Ca(PO3)2 / Ca-polyphosphate glass", "(LiPO3)n Hydro-Quebec film")
OXIDATION_STAGES = ("slurry", "cell", "comparator", "control")
MAIN_STAGES = ("slurry", "cell", "control")       # the benchmark table leaves the silicate comparators to the reaction table
_ERR = re.compile(r"\|error\| ([0-9.]+) (<=|>) ([0-9.]+) kJ/mol per atom")
_EQ = re.compile(r"(?:^|; )([^;]*->[^;]*)$")
_FORMULA = re.compile(r"^[A-Z(][A-Za-z0-9()]*$")
_COEF = re.compile(r"^[0-9]+(\.[0-9]+)?$")


def _stem(phase, framing, rid=""):
    """A letters-only name stem for one ladder row."""
    words = {"brushite": "Brushite", "ACP": "Acp", "HAp": "Hap", "OCP": "Ocp", "b-TCP": "Btcp", "a-TCP": "Atcp",
             "Li3PO4": "LiOrtho", "Ca2P2O7": "CaPyro", "Ca(PO3)2 / Ca-polyphosphate glass": "CaMeta", "AlPO4": "AlOrtho",
             "Al(PO3)3": "AlMeta", "Al-polyphosphate (R1 gel)": "AlGel", "(LiPO3)n Hydro-Quebec film": "LiMeta",
             "baked aluminophosphate (Tsinghua)": "Baked", "CaSiO3": "CaSilMeta", "Ca2SiO4": "CaSilOrtho",
             "Li2SiO3": "LiSil", "CaCO3": "Carbonate"}
    if phase not in words:
        raise InputTableError("ladder phase %r has no name stem" % phase)
    tail = "".join({"r": "R", "s": "S", "1": "One", "2": "Two", "3": "Three", "4": "Four"}[c] for c in rid) if rid else ""
    return words[phase] + ("Am" if framing == "amorphous" else "") + tail


def framing_word(phase, framing):
    if framing == "amorphous":
        return "glass" if phase in GLASS_PHASES else "amorphous"
    return "crystal" if phase in GLASS_PHASES else "crystalline"


def equation_text(notes):
    """The reaction of a ladder row (the last `;` segment of its notes that holds an arrow), labels in brackets dropped."""
    m = _EQ.search(notes.strip())
    if not m:
        return None
    eq = re.sub(r"\s*\[[^\]]*\]", "", m.group(1)).strip()
    for tok in eq.split():
        if not (tok in ("+", "->") or _FORMULA.match(tok) or _COEF.match(tok)):
            raise InputTableError("reaction %r has a token that is not a formula: %s" % (eq, tok))
    return eq


def benchmark_words(status):
    """The database comparator of a ladder row: its per-atom error against the specified band, or why there is none."""
    m = _ERR.search(status)
    if m:
        return float(m.group(1)), float(m.group(3)), ("benchmarked" if m.group(2) == "<=" else "outside the band")
    m = re.search(r"dft-unbenchmarked \(([^)]*)\)", status)
    if m:
        reason = {"no tabulated value": "no tabulated value",
                  "the tabulated phase is a glass, MP a crystal": "the tabulated phase is a glass",
                  "DfG only: the 0 K energy has no like-for-like DfH": "no tabulated enthalpy"}.get(m.group(1))
        if reason is None:
            raise InputTableError("unbenchmarked reason not covered: %s" % m.group(1))
        return None, None, "unbenchmarked: " + reason
    raise InputTableError("benchmark status not covered: %s" % status)


def _num(x):
    try:
        return float(x)
    except ValueError:
        return None


def ladder_groups(docs, stages):
    """(phase, framing, stage, governing row, its reaction rows) per ladder entry with oxidation reactions, in file order."""
    rows = [r for r in docs["ladder"] if r["stage"] in stages and r["reaction_id"] not in ("-",)]
    out, seen = [], []
    for r in rows:
        k = (r["phase"], r["framing"], r["stage"])
        if k not in seen:
            seen.append(k)
    for k in seen:
        sel = [r for r in rows if (r["phase"], r["framing"], r["stage"]) == k]
        agg = [r for r in sel if r["reaction_id"] == "ALL"]
        reactions = [r for r in sel if r["reaction_id"] != "ALL"]
        if not reactions:
            continue
        if agg:
            a = agg[0]
            gov = [r for r in reactions if r["E_ub_V"] == a["E_ub_V"] and r["margin_V"] == a["margin_V"] and a["E_ub_V"]]
            gov = gov[0] if gov and a["budget_status"] == "complete" else None
        else:
            gov = reactions[0] if len(reactions) == 1 and reactions[0]["budget_status"] == "complete" else None
        out.append((k, gov, reactions))
    return out


def _onset_parts(r, key, stem):
    e, m = _num(r["E_ub_V"]), _num(r["margin_V"])
    eub = [Num("NumBen%sEub" % stem, "ladder/%s/e_ub" % key, e, ".2f", "V")] if e is not None else ["--"]
    mar = [Num("NumBen%sMargin" % stem, "ladder/%s/margin" % key, m, ".3f", "V")] if m is not None else ["--"]
    return eub, mar


def _undetermined_reason(r):
    s = r["budget_status"]
    if s.startswith("symbolic: expt route undetermined: "):
        return "undetermined: no tabulated data for " + ", ".join(_plain(x) for x in s.split(": ")[-1].split(","))
    if s == "incomplete":
        return "undetermined: incomplete uncertainty budget"
    raise InputTableError("budget status not covered: %s" % s)


def benchmark_rows(docs):
    out = []
    for (phase, framing, stage), gov, reactions in ladder_groups(docs, MAIN_STAGES):
        stem = _stem(phase, framing)
        key = "main/" + stem
        err, band, word = benchmark_words(reactions[0]["benchmark_status"])
        errp = [Num("NumBen%sErr" % stem, "ladder/%s/dft_error" % key, err, ".1f")] if err is not None else []
        comp = (errp + [" (" + word + ")"]) if errp else [word]
        if gov is None:
            out.append(([PHASE_NAME[phase]], [framing_word(phase, framing)], [_undetermined_reason(reactions[0])], ["--"], ["--"], comp))
            continue
        eub, mar = _onset_parts(gov, key, stem)
        out.append(([PHASE_NAME[phase]], [framing_word(phase, framing)], [equation_text(gov["notes"])], eub, mar, comp))
    return out


def reaction_rows(docs):
    out = []
    for (phase, framing, stage), _gov, reactions in ladder_groups(docs, OXIDATION_STAGES):
        for r in reactions:
            stem = _stem(phase, framing, r["reaction_id"])
            key = "si/" + stem
            eq = equation_text(r["notes"])
            if eq is None:
                raise InputTableError("ladder row %s %s %s has no reaction in its notes" % (phase, framing, r["reaction_id"]))
            eub, mar = _onset_parts(r, key, stem)
            status = {"complete": "complete"}.get(r["budget_status"]) or _undetermined_reason(r)
            out.append(([PHASE_NAME[phase]], [framing_word(phase, framing)], [eq], eub, mar, [status]))
    return out


# ---------------------------------------------------------------- SI: the database benchmark and the conversion steps

def dft_rows(docs):
    out = []
    for r in docs["benchmark"]:
        stem = re.sub(r"[^A-Za-z]", "", r["phase"].replace("2", "Two").replace("3", "Three").replace("4", "Four")
                      .replace("5", "Five").replace("6", "Six").replace("7", "Seven").replace("8", "Eight"))
        key = "dft/" + stem
        name = _plain(r["phase"]).replace("b-TCP", "beta-TCP").replace("a-TCP", "alpha-TCP")
        cells = [[name], [r["formula"]]]
        for col, name, fmt in (("expt_dfH_kJ", "Dfh", ".1f"), ("dft_minus_dfH_kJ", "Diff", ".1f"),
                               ("dft_minus_dfH_kJ_per_atom", "DiffAtom", ".1f")):
            v = _num(r[col]) if r[col] else None
            cells.append([Num("NumDft%s%s" % (stem, name), "%s/%s" % (key, col), v, fmt)] if v is not None else ["--"])
        disp = r["display"]
        word = ("benchmarked" if disp.startswith("dft-benchmarked") else "outside the band" if disp.startswith("dft-benchmark-failed")
                else "unbenchmarked" if disp.startswith("dft-unbenchmarked") else None)
        if word is None:
            raise InputTableError("benchmark display not covered: %s" % disp)
        cells.append([word])
        out.append(cells)
    return out


_AW = re.compile(r"a_w\*=([0-9.e+-]+) \(range ([0-9.e+-]+) to ([0-9.e+-]+)\)")


def _sci_fmt(v):
    return ".3g" if 0.01 <= abs(v) < 1000 else "sci:2"


def conversion_rows(docs):
    out = []
    reasons = {"no coacervate binodal or activity data": "no binodal or activity data of the coacervate",
               "Al(PO3)3 has no tabulated thermochemistry": "no tabulated thermochemistry of Al(PO3)3",
               "Ksp of the Al polyphosphate is a gap": "no solubility product of the aluminium polyphosphate",
               "not a dehydration threshold": "not a dehydration threshold"}
    for k, r in enumerate(r for r in docs["ladder"] if r["stage"] == "conversion"):
        stem = "Conv" + "ABCDEFGHIJ"[k]
        m = _AW.search(r["notes"])
        if m:
            vals = [float(x) for x in m.groups()]
            nums = [Num("NumConv%s%s" % (stem[4:], n), "conversion/%s/%s" % (stem, n.lower()), v, _sci_fmt(v))
                    for n, v in zip(("Aw", "AwLo", "AwHi"), vals)]
            aw = [nums[0], " (", nums[1], " to ", nums[2], ")"]
            reading = "threshold only; kinetically gated"
        else:
            aw = ["--"]
            found = [v for t, v in reasons.items() if t in r["notes"]]
            if len(found) != 1:
                raise InputTableError("conversion row %r: undetermined reason not covered" % r["phase"])
            reading = "undetermined: " + found[0]
        out.append(([_plain(_step_label(r["phase"]))], [_plain(r["reaction_id"])], aw, [reading]))
    return out


def _step_label(s):
    """A conversion-step label without the internal route ids (R1 to R3) and with the baseline named by its film."""
    s = re.sub(r"\s*\(R[0-9](?:, R[0-9])*\)|\bR[0-9]\s+", "", s)
    s = s.replace("Hydro-Quebec film", "(LiPO3)n film")
    return s[:1].upper() + s[1:] if s[:1].islower() else s


def _plain(s):
    """A label or reaction as plain text, whitespace normalised."""
    return " ".join(s.split())


# ---------------------------------------------------------------- the speciation fractions of carbonate and phosphate

def speciation(docs):
    """Fraction of carbonate as CO3^2- and of phosphate as PO4^3- (per cent), from the specified acid constants at
    infinite dilution, at the lowest and the central pH of the specified slurry range."""
    p = docs["params"]
    k1, k2 = float(p["pk1_carbonic"]["value"]), float(p["pk2_carbonic"]["value"])
    a1, a2, a3 = (float(p[k]["value"]) for k in ("pka1_h3po4", "pka2_h3po4", "pka3_h3po4"))
    ph = p["ph_slurry"]
    lo, mid = float(ph["range"]["min"]), float(ph["value"])

    def co3(x):
        return 100.0 / (1 + 10 ** (k2 - x) + 10 ** (k1 + k2 - 2 * x))

    def po4(x):
        return 100.0 / (1 + 10 ** (a3 - x) + 10 ** (a2 + a3 - 2 * x) + 10 ** (a1 + a2 + a3 - 3 * x))

    return [Num("NumSpecPhLow", "speciation/ph_low", lo, ".0f"), Num("NumSpecPhMid", "speciation/ph_mid", mid, ".0f"),
            Num("NumSpecCarbonateLow", "speciation/co3_pct_low", co3(lo), ".0f", "%"),
            Num("NumSpecPhosphateLow", "speciation/po4_pct_low", po4(lo), ".2f", "%"),
            Num("NumSpecPhosphateMid", "speciation/po4_pct_mid", po4(mid), ".0f", "%")]


# ---------------------------------------------------------------- reading, rendering, writing

def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read_inputs(root):
    root = Path(root)
    for k, rel in INPUTS.items():
        if not (root / rel).is_file():
            raise InputTableError("missing input %s" % rel)
    p = P.load_params(root / P.PARAMS, root)
    _, ev = E.read_csv(root / P.TABLE)
    with (root / INPUTS["ladder"]).open(encoding="utf-8") as fh:
        ladder = list(csv.DictReader(fh))
    with (root / INPUTS["benchmark"]).open(encoding="utf-8") as fh:
        bench = list(csv.DictReader(l for l in fh if not l.startswith("#")))
    docs = {"params": p.entries, "evidence": {r["row_id"]: r for r in ev}, "ladder": ladder, "benchmark": bench,
            "labels": yaml.safe_load((root / INPUTS["labels"]).read_text(encoding="utf-8")),
            "screen": yaml.safe_load((root / INPUTS["screen"]).read_text(encoding="utf-8"))}
    return docs, {k: sha256(root / rel) for k, rel in INPUTS.items()}


def render_csv(docs, built):
    """Every table as rows of plain text: table, group, then the cells of the row."""
    out = io.StringIO()
    w = csv.writer(out, lineterminator="\n")
    w.writerow(["table", "group", "cells"])
    for title, rows in built["params"]:
        for r in rows:
            w.writerow(["parameters", plain_of(title) if isinstance(title, list) else title] + [plain_of(c) for c in r])
    for k in ("benchmark", "reactions", "dft", "conversion"):
        for r in built[k]:
            w.writerow([k, ""] + [plain_of(c) for c in r])
    w.writerow(["speciation", "", plain_of(built["speciation"])])
    return out.getvalue()


def build_all(docs):
    return {"params": param_rows(docs), "benchmark": benchmark_rows(docs), "reactions": reaction_rows(docs),
            "dft": dft_rows(docs), "conversion": conversion_rows(docs), "speciation": speciation(docs)}


def collect(built):
    found = {}

    def take(parts):
        for n in parts:
            if isinstance(n, Num):
                if n.name in found and (found[n.name].key, found[n.name].value) != (n.key, n.value):
                    raise InputTableError("number %s has two meanings" % n.name)
                found[n.name] = n

    for _t, rows in built["params"]:
        for r in rows:
            for c in r:
                take(c)
    for k in ("benchmark", "reactions", "dft", "conversion"):
        for r in built[k]:
            for c in r:
                take(c)
    take(built["speciation"])
    return found


def render_json(shas, nums):
    tree = {}
    for n in nums.values():
        node = tree
        parts = n.key.split("/")
        for p in parts[:-1]:
            node = node.setdefault(p, {})
        node[parts[-1]] = n.value
    out = {"schema": 1, "generator": "biomin-screen tables inputs",
           "inputs": {INPUTS[k]: shas[k] for k in INPUTS}, "numbers": tree}
    return json.dumps(out, indent=1, sort_keys=True) + "\n"


def generate(root):
    """The outputs as {path: text}, without writing anything."""
    docs, shas = read_inputs(root)
    built = build_all(docs)
    nums = collect(built)
    gen = paths.generated(root)
    return {(gen / OUT_CSV): render_csv(docs, built), (gen / OUT_JSON): render_json(shas, nums)}


def write(root):
    out = generate(root)
    for p, text in out.items():
        Path(p).write_text(text, encoding="utf-8", newline="\n")
    return sorted(out)


def check(root):
    """Paths whose committed text differs from a fresh generation (empty means byte-identical)."""
    return [p for p, text in generate(root).items()
            if not Path(p).is_file() or Path(p).read_bytes() != text.encode("utf-8")]
