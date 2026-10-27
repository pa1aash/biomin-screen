#!/usr/bin/env python3
"""Run the dissolution test (K2) of examples/example_phase.yaml on a small grid of states.

    python examples/run_example.py

For each state it prints the saturation ratio Omega = IAP / K_sp at the median K_sp and at the K_sp that is exceeded
with probability 1 - p_cred, and whether the phase passes (Omega >= 1 at the latter). A phase passes the dissolution
test only where every state of the grid passes; the pass is a necessary condition, not a sufficient one.
"""
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from biomin_screen.literature import params as P  # noqa: E402
from biomin_screen.physics import supersaturation as S  # noqa: E402


def main():
    spec = yaml.safe_load((Path(__file__).parent / "example_phase.yaml").read_text(encoding="utf-8"))
    phase, states, p_cred = spec["phase"], spec["states"], spec["p_cred"]
    table = P.load_params(ROOT / "data" / "params.yaml", ROOT)
    prior = P.prior(phase["keys"]["ksp"], table)
    nu = phase["stoichiometry"]
    log_ksp_median = float(prior.ppf(0.5))
    log_ksp_worst = float(prior.ppf(p_cred))       # largest K_sp of the credible band: the phase dissolves most
    print("%s, log10 K_sp: median %.2f, worst case at p=%.2f %.2f" % (phase["name"], log_ksp_median, p_cred, log_ksp_worst))
    passing = 0
    total = 0
    for a_ca in states["a_ca"]:
        for a_po4 in states["a_po4"]:
            omega = [S.saturation_ratio_mineral(a_ca, a_po4, 1.0, nu["nu_ca"], nu["nu_x"], nu["nu_y"], states["a_w"],
                                                nu["n_hyd"], 10.0 ** k) for k in (log_ksp_median, log_ksp_worst)]
            ok = omega[1] >= 1.0
            passing += ok
            total += 1
            print("a_Ca %.0e  a_PO4 %.0e  Omega(median) %10.3g  Omega(worst) %10.3g  %s"
                  % (a_ca, a_po4, omega[0], omega[1], "pass" if ok else "does not pass"))
    print("%d of %d states pass; the phase passes the dissolution test only if all do." % (passing, total))
    for key in ("v_m",):
        if phase["keys"].get(key) not in table.entries:
            print("no sourced %s: the nucleation and thin-film tests would read undetermined" % key)


if __name__ == "__main__":
    main()
