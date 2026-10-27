# Add a candidate phase and run the screen

The screen turns sourced thermochemistry into a verdict per stage for any mineral phase. A phase needs four things.

## 1. A sourced value, with its uncertainty

Every number the screen uses is a row of `data/evidence_table.csv`: the quantity, the value, its range, the conditions,
the DOI and the locator in the paper, and an evidence grade (A to D). Add one row per value. For the dissolution test a
phase needs a solubility product per formula unit. For the oxidation test it needs the formation thermochemistry of the
phase and of its oxidation products. For the nucleation and thin-film tests it also needs a molar volume and interfacial
energies; where these are missing the tests read *undetermined*, and an undetermined test never passes.

## 2. A key in the parameter file

`data/params.yaml` is generated from the evidence table and the key specification `data/params_spec.yaml` by the rule in
`data/params_README.md`. Add the key to the specification (symbol, unit, the rows it draws on, the prior family the rule
selects) and regenerate and validate:

    python -m biomin_screen.literature.build_params
    python -m pytest tests/lit -q

The grade of the sources limits the prior built from them (a grade-D source gives a wide prior).

## 3. An entry in the candidate list

Add the phase to `minerals:` in `configs/screen.yaml`, with its formula unit, stoichiometry and parameter keys.
`examples/example_phase.yaml` shows the block. Its oxidation reactions go into the onset ladder
(`src/biomin_screen/pourbaix/oxidation_ladder.py`), which reads formation energies from the cached Materials Project
data in `results/pourbaix/cache/`.

## 4. Run the screen

Try the dissolution test on a small grid first; it runs in a second and needs only the phase file:

    python examples/run_example.py

Then rerun the stages that read the candidate list, and the tables built from them:

    python -m biomin_screen.pourbaix.oxidation_ladder run
    python -m biomin_screen.pourbaix.ladder run
    python -m biomin_screen.screen k2-grid --out results/screen/<run>_ph/summary.json
    biomin-screen tables regime

A new verdict applies to the stated framing, crystalline or amorphous, and to the inputs as sourced. A pass of the
dissolution test is a necessary condition for a coating, never a sufficient one. The oxidation test can exclude a phase
but cannot admit one, because a pass would need a lower bound that rests on transfer free energies that are unmeasured.
