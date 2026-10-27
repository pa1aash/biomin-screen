"""Registry of the specified functions and its equivalence check (skipped: the tooling is not shipped)."""
import pytest

pytestmark = pytest.mark.skip(reason='checks the function registry and the contract equivalence tooling, which are not shipped')


def test_implementation_matches_contract_expression():
    raise AssertionError("not run")


def test_every_contract_function_is_implemented():
    raise AssertionError("not run")


def test_template_barrier_matches_contract_composite():
    raise AssertionError("not run")


def test_constant_relations_hold():
    raise AssertionError("not run")


def test_recorded_check_is_a_pass_for_the_implemented_version():
    raise AssertionError("not run")


def test_checker_accepts_the_specified_young_relation():
    raise AssertionError("not run")


def test_checker_rejects_a_sign_slipped_young_relation():
    raise AssertionError("not run")


def test_checker_rejects_a_wrong_argument_set():
    raise AssertionError("not run")


def test_conditioning_allowance_never_excuses_a_less_accurate_implementation():
    raise AssertionError("not run")
