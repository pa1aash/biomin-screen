# Carbonate-control stability inputs

Written by `python -m biomin_screen.pourbaix.c5 --config results/pourbaix/config/c5.yaml` from the parameter snapshot
`results/pourbaix/inputs/params_8bc15c8.json`. These documents are the thermodynamic proxies the carbonate chain reads:
Pourbaix diagrams of the slurry regime and Li-referenced windows of the cell regime. They are proxies; no rates.

| File | Content |
|---|---|
| `slurry/aCa<a>_CT<c>_Al<al>.json` | one per (a_Ca, C_T, total Al): the Pourbaix diagram as the competing-phase and Al-phase baseline at fixed C(IV). Water lines are under `extensions.pourbaix`. |
| `slurry_summary.json` | per design point: decomposition energies against the DFT tolerance, the Al baseline per total Al, the proxy control |
| `slurry_c5_inputs.json` | the baseline: tolerance, the calcite offset stated (Ksp bias -2.48 and edge shift, so the proxy is context), competing phases, Al phases, carbon-redox sensitivity |
| `../omega_control.json` | the falsifiability fixture for the Omega test (one dissolving, one supersaturated case) |
| `cell/<sink>.json` | one per specified sink and the solvated sink, as `run_cell` writes them (`oxidation` is the lowest over the schemes); the governing route is in `cell_scheme_table.json` |
| `cell_summary.json` | the cell-regime window under each scheme; the per-class verdicts in `cell_scheme_table.json` govern |
| `cell_scheme_table.json` | every scheme in one table: the experimental route governing, janaf and mp as comparators with their benchmark errors (+0.382, -0.233 V per electron), the corrected values and the margin of the governing route |

`../final/` holds the final runs of the same documents.
