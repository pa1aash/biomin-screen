"""Physics core of the screen.

Pure, vectorised functions in SI units. Every function validates its inputs against
the physical domain of the quantity it computes and raises ValueError outside it.

Modules
    constants        physical constants, taken from sympy's unit system (not typed)
    wetting          shape factor f(theta); Young's relation under the specified convention;
                     the rejected forms (comparison only)
    nucleation       classical nucleation theory barriers and critical radius
    supersaturation  saturation ratio (bulk and with Ca2+ enrichment) and driving force
    adhesion         Dupre work of adhesion in water
    sequestration    Ca2+ transfer free energy, enrichment and its saturation bound
    template         the barrier on the template through its two channels
    conformality     spreading coefficient, coalescence and closure thickness
    stability        Pourbaix and Li-open grand potentials
    film             electronic thickness bounds of an insulating film
"""
from biomin_screen.physics.constants import AVOGADRO, BOLTZMANN, GAS_CONSTANT
from biomin_screen.physics.nucleation import (
    barrier_in_kT,
    critical_radius,
    heterogeneous_barrier,
    homogeneous_barrier,
    homogeneous_barrier_from_saturation,
)
from biomin_screen.physics.supersaturation import driving_force_molar, driving_force_per_formula_unit
from biomin_screen.physics.wetting import shape_factor, shape_factor_from_cos

__all__ = [
    "AVOGADRO", "BOLTZMANN", "GAS_CONSTANT",
    "barrier_in_kT", "critical_radius", "heterogeneous_barrier", "homogeneous_barrier",
    "homogeneous_barrier_from_saturation",
    "driving_force_molar", "driving_force_per_formula_unit",
    "shape_factor", "shape_factor_from_cos",
]
