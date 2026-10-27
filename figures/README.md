# Figures

The seven data figures of the paper, built from the stored outputs under `results/` and `data/`.

    python -m biomin_screen.figures.cli            # build all seven into figures/ (PDF, PNG and a numeric sidecar)
    python -m biomin_screen.figures.cli --only retrodiction     # one figure, by name or by id (fig4)
    python -m biomin_screen.figures.cli --check    # rebuild into a scratch directory and compare with the shipped sidecars
    biomin-screen figures [--check]                # the same

Building needs no network, no Blender and no git. Build one figure at a time on a small machine (`--only`).

| Figure id (paper source numbering) | File | Input files |
|---|---|---|
| fig4 | `retrodiction` | `data/retrodiction/results/results.json` |
| fig7 | `carbonate_dissolution` | `results/screen/table_r2/summary.json`, `data/params.yaml` |
| fig10 | `formation_benchmark` | `results/pourbaix/benchmark/formation_benchmark_table.csv`, `.../formation_benchmark_table.json` |
| fig11 | `al_window` | `results/pourbaix/ladder/passivation_window_v3.csv`, `results/pourbaix/benchmark/al_window.json` |
| fig14 | `precision_map` | `results/screen/precision_ph/precision_map.json` |
| fig15 | `regime_map` | `results/pourbaix/ladder/ladder.csv`, `results/tables/regime_table.csv`, `results/screen/k2_grid_ph/summary.json`, `results/screen/k2_perph_decade/perph.csv`, `results/screen/k2_acid_decade/summary.json`, `results/screen/k2_alkaline_decade/summary.json`, `configs/thresholds.yaml` |
| fig17 | `k2_vs_k1` | `results/screen/k2_perph_decade/perph.csv`, `results/screen/k2_grid_ph/summary.json`, `results/screen/k2_acid_decade/summary.json`, `results/screen/k2_alkaline_decade/summary.json`, `results/pourbaix/ladder/ladder.csv`, `configs/thresholds.yaml` |

Each name gives `figures/<name>.pdf`, `figures/<name>.png` (600 dpi) and `figures/<name>.json`. The templates are
`figures/src/figN.py`; each defines `FIGURE` (name, description, size, input files, schema) and `build(data, root, aux)`.

## Rules the figures follow

No legends, no text inside the axes except tick labels, panel letters outside the axes. The checker
(`biomin_screen.figures.checker`) enforces this on the drawn figure and on the written PDF (every text span must lie in
a tick label, axis title, colour-bar label or panel letter), together with the RSC size, font-size and line-width limits.

## Font

The figure font is the first installed face of Helvetica, Liberation Sans, DejaVu Sans (`figures/style/rsc_spec.yaml`,
`applied.font_family`). DejaVu Sans ships with matplotlib, so a font is always found. Arial is not required. The build
prints the face it used. The face changes glyph shapes and label widths, not the plotted numbers.

## Check

PDF and PNG bytes differ across platforms and fonts, so `--check` compares the sidecar `figures/<name>.json` of a fresh
build with the shipped one. A sidecar holds, per axes, the scales, limits, tick positions and labels and the data
coordinates of every drawn artist, rounded to 6 significant digits; numbers agree when they differ by at most a relative
1e-6 (plus an absolute 1e-12 for values that are zero up to noise). The PDF and PNG are for viewing.
