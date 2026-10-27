# Third-party data

Every external dataset the repository reads, with its source, licence and identifier. The code is MIT
(`LICENSE`); the repository's own data and results are CC BY 4.0 (`LICENSE-DATA`). The datasets below keep
their own licences and attribution; they are not relicensed here.

| Dataset | Files | Source | Licence | Identifier |
|---|---|---|---|---|
| Materials Project, thermodynamic entries (database version 2026.04.13, `GGA_GGA+U`) | `results/pourbaix/cache/mp_entries_*.json` (shipped as `.json.gz`) | https://materialsproject.org, retrieved through the `mp-api` client | CC BY 4.0 (https://creativecommons.org/licenses/by/4.0/); every cached entry carries the tag `BY-C` and the loader admits only that tag | A. Jain et al., APL Materials 1, 011002 (2013), doi:10.1063/1.4812323 |
| Materials Project contributed data: Aqueous Ion Reference Data (MPContribs project `ion_ref_data`) | `results/pourbaix/cache/mp_ion_reference_data.json` (shipped as `.json.gz`) | https://materialsproject.org, MPContribs | CC BY 4.0, data owned by its contributors | K. A. Persson et al., Phys. Rev. B 85, 235438 (2012), doi:10.1103/PhysRevB.85.235438 |
| NIST-JANAF Thermochemical Tables | `results/pourbaix/cache/janaf_*.json` and the `janaf_*.json` files beside the ladder and benchmark outputs | https://janaf.nist.gov (NIST Standard Reference Database 13) | NIST Standard Reference Data; see the terms at https://www.nist.gov/open/license | M. W. Chase, NIST-JANAF Thermochemical Tables, J. Phys. Chem. Ref. Data Monograph 9 (1998), doi:10.18434/T42S31 |
| NBS tables of chemical thermodynamic properties (pages used, as OCR text) | `results/pourbaix/cache/nbs1982_ocr.json` | https://srd.nist.gov/JPCRD/jpcrdS2Vol11.pdf | NIST Standard Reference Data | D. D. Wagman et al., J. Phys. Chem. Ref. Data 11, Suppl. 2 (1982), erratum doi:10.1063/1.555845 |
| Literature values of the parameter table | `data/evidence_table.csv` (one row per value, with DOI and locator), `data/params.yaml` | the papers named by the DOI of each row | the values are facts quoted with their source; the papers keep their own copyright | one DOI per row |
| Retrodiction cases | `data/retrodiction/cases.yaml` | the papers named by the DOI of each case | as above | one DOI per case |

## Materials Project attribution

The Materials Project data used here are from database version 2026.04.13 and are used under the Creative
Commons Attribution 4.0 International licence. Cite A. Jain, S. P. Ong, G. Hautier, W. Chen, W. D. Richards,
S. Dacek, S. Cholia, D. Gunter, D. Skinner, G. Ceder and K. A. Persson, "Commentary: The Materials Project: A
materials genome approach to accelerating materials innovation", APL Materials 1, 011002 (2013),
https://doi.org/10.1063/1.4812323.

Changes made to the data: the MP2020 compatibility corrections and the aqueous-compatibility adjustments were
applied when the entries were retrieved; the Pourbaix entries were rebuilt offline from the cached solid entries
and the ion reference data, following Persson et al. (2012); amorphous calcium carbonate is represented as the
calcite entry plus a sourced free-energy offset; for the lithium-referenced window an all-experimental route
replaces the computed energies where experimental data exist. Entries derived from GNoME, which are licensed
CC BY-NC 4.0, are excluded. Use of these data does not imply endorsement by the Materials Project or by its
contributors. Details are in `results/pourbaix/cache/NOTICE.md`.
