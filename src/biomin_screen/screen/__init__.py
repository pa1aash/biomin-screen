"""Parameter screen: priors -> Monte Carlo -> Sobol -> per-link thresholds.

Production priors come from data/params.yaml; thresholds are fixed from physics in
data/thresholds.md before any production screen runs, so nothing here sets a threshold or a prior.

Modules
    priors      prior-file loader; refuses mock files unless explicitly allowed
    links       per-link physical models evaluated on sampled inputs
    propagate   Monte Carlo propagation of priors through a link model
    sobol       Sobol first- and total-order indices with bootstrap confidence intervals
    thresholds  parser and equality check of the thresholds block (data/thresholds.md, configs/thresholds.yaml)
    summary     results summary conforming to configs/results_schema.json
"""
