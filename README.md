# biomin-screen

An open thermodynamic screening framework for mineral coatings made from biopolymer-templated carbonate and
phosphate phases, the minerals of the nacre and bone lineages. It tests a candidate phase at the two stages where it
would have to exist on an aluminium current collector in a fluorine-free lithium-ion cathode: dissolution in the
alkaline aqueous slurry of electrode processing, and oxidation at the potential of the cell. Inputs are sourced
thermochemistry with uncertainty; outputs are an exclusion map, break-even ratios, a required-precision map and the
input value at which each verdict flips. The framework is biomimetic in its framing: the candidates are the mineral
phases that organisms form under biopolymer control, evaluated as coating materials. This repository re-derives the
numbers, tables and data figures of the accompanying paper from the sourced parameter file and cached inputs.

## Quick start

    git clone https://github.com/pa1aash/biomin-screen && cd biomin-screen
    make env       # once: Python 3.12 virtual environment from requirements.txt (needs network)
    make test      # test suite
    make check     # regenerate the stored outputs in work/ and compare them with the shipped ones
    make numbers   # the headline quantities of the paper, with intervals
    make tables    # rebuild results/tables/
    make figures   # rebuild the data figures in figures/
    make all       # test, check, tables, figures, numbers
    make help      # every target

Reproduction needs no network, GPU, API key or retraining after `make env`. The Makefile runs the source in `src/`,
never an installed copy. The Dockerfile is provided untested; use the pinned requirements for the supported route. To screen your own phase see `examples/add_a_candidate.md` and run
`python examples/run_example.py`.

| Target | Reads | Time (laptop, one core) |
|---|---|---|
| `make env` | `requirements.txt` | under a minute with a warm package cache, a few minutes without; once |
| `make test` | `tests/`, stored outputs | about 2 minutes (1096 pass; 112 are skipped, each with a stated reason) |
| `make check` | `configs/`, `data/`, cached thermodynamic data | about 6 minutes |
| `make numbers` | `data/headline_numbers.yaml`, `results/tables/` | a second |
| `make tables` | stored outputs in `results/` | seconds |
| `make figures` | stored outputs, `data/retrodiction/` | under 10 seconds |
| `make screen` | the omitted per-cell documents, every regenerated stage and the two long production runs, compared with the shipped summaries | about 20 minutes, peak 1.9 GB; needs 8 GB of memory |
| `make screen-quick` | per-cell documents and the production runs at 8192 samples per state, no sensitivity analysis | about 2 minutes; written to `work/quick/` |

`make check` compares every number of each regenerated file with the shipped file. The tolerance is a relative 1e-9
(absolute 1e-12); timestamps, run times and provenance blocks are not compared. Figures are compared through their data
sidecars (`figures/*.json`, same tolerance), not through image bytes, which depend on the installed font.

## Directory map

    src/biomin_screen/   physics/ (relations per formula unit), screen/ (stage logic, Monte Carlo, sensitivity,
                         precision map, break-even), pourbaix/ (oxidation-onset ladder, windows, cached-data readers),
                         literature/ (parameter table and evidence table), tables/, figures/, retro/ (retrodiction)
    data/                params.yaml (sourced parameters with grades), evidence_table.csv (one row per value, DOI and
                         locator), thresholds, symbols, retrodiction cases, headline_numbers.yaml
    configs/             screen configuration, gap tables, thresholds, symbol bindings, results schema
    results/pourbaix/    cached Materials Project and NIST data, ladder, benchmark, windows, carbonate-control runs
    results/screen/      K2 grids, phosphate films, per-pH doses, break-even ratios, carbonate chain, precision map
    results/tables/      the paper's regime, break-even and input tables (CSV and JSON)
    figures/             the seven data figures (PDF, PNG and a data sidecar each), figures/README.md
    examples/            add_a_candidate.md and a runnable example phase
    scripts/             numbers.py, check.py, screen.py

## Contents

Included: the screening code, the parameter file and evidence table with grades, the configurations, the cached
Materials Project data (CC BY 4.0, attributed; no key needed), the stored outputs the tables read, the scripts for every
data table and data figure of the paper, a test suite, a pinned environment and an untested Dockerfile.

Not included: the manuscript, the rendered hero figure and schematic art, structure-generation material, and the
per-cell Pourbaix documents (18 slurry documents and the c5 inputs snapshot; `make screen` rebuilds them) and the
raw outputs of the sensitivity sweeps behind the required-precision map, which `make check` reads and does not regenerate.

Files over 100 KB under `results/` are stored gzip-compressed (`name.json.gz`, 97 files). Every command that reads
them unpacks the missing plain copies first (`python -m biomin_screen.archive unpack`); `results/ARCHIVE.sha256` lists
the sha256 of each unpacked file and `python -m biomin_screen.archive verify` compares them. Unpacking about 113 MB
of plain JSON needs that much free disk.

## Software versions

Python 3.12.13; numpy 2.5.4, scipy 1.18.1, pymatgen 2026.9.24, matplotlib 3.11.2, PyYAML 6.0.3, sympy 1.14.0,
pytest 9.1.1. Every pin is in `requirements.txt`. Materials Project database version 2026.04.13.

## Licences

Code: MIT (`LICENSE`). Data and results of this repository: CC BY 4.0 (`LICENSE-DATA`). Third-party data keep their own
licences and attribution: see `THIRD_PARTY.md`, which gives the Materials Project attribution.

## How to cite

Use `CITATION.cff` (GitHub shows a "Cite this repository" button) or the Zenodo record of the release.

## Scope

The repository re-derives the paper's results from sourced data. It does not test any coating experimentally. A phase
that passes the dissolution test meets a necessary condition only; the oxidation test can exclude a phase but cannot
admit one. No performance claim follows from any verdict.

Regeneration is numerical, not bitwise. `make check` was verified on macOS arm64 only. It reproduces the regenerated stages to the stated tolerance on the
platform that produced the shipped files (macOS, arm64, the pinned versions); another platform can differ in the last
digits. The production runs (`make screen`) are Monte Carlo runs with fixed seeds; they reproduce the shipped
summaries only where the sampling order is identical (it was, on the platform above), and `make screen-quick` uses a much smaller sample, skips the sensitivity analysis and is not
expected to equal them. On the platform of the shipped files `make screen` reproduced both production runs to the stated
tolerance. A regenerated per-cell document is equivalent to the omitted one, not byte-identical.
