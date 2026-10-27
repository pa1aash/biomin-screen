"""Supplements of the parameter table (README section 8): labels, filled gaps and the one edited key."""
import re
from pathlib import Path

import pytest
import yaml

from biomin_screen.literature import params as P

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def table():
    return yaml.safe_load((ROOT / P.PARAMS).read_text(encoding="utf-8"))


def test_added_keys_carry_a_supplement_label(table):
    added = {k: e["added_in"] for k, e in table["params"].items() if "added_in" in e}
    assert added and all(re.fullmatch(r"supplement-[1-9][0-9]*", v) for v in added.values()), added


def test_filled_gaps_are_gaps(table):
    for k, e in table["params"].items():
        if "fills" in e:
            gap = table["params"][e["fills"]]
            assert gap["status"] == "gap" and gap["prior"] == {"family": "none"}, k
            assert e["status"] != "gap" and e.get("added_in"), k


def test_n_req_is_the_poisson_rule():
    e = P.load_params(ROOT / P.PARAMS, ROOT).entries["n_req"]
    assert e["derived"]["expr"] == "log(1 / (1 - p_cred)) / A_patch"
    assert e["derived"]["inputs"] == {"p_cred": "p_cred", "A_patch": "patch_area"}


@pytest.mark.skip(reason="compares the table with its first release, which is read from the version history that the shipped repository does not carry")
def test_every_key_of_the_first_release_is_unchanged_except_the_one_edit():
    raise AssertionError("not run")


@pytest.mark.skip(reason="compares the table with its first release, which is read from the version history that the shipped repository does not carry")
def test_no_key_is_removed():
    raise AssertionError("not run")


@pytest.mark.skip(reason="compares the table with its first release, which is read from the version history that the shipped repository does not carry")
def test_aliases_of_the_first_release_are_unchanged_except_the_edited_key():
    raise AssertionError("not run")


@pytest.mark.skip(reason="compares the table with its first release, which is read from the version history that the shipped repository does not carry")
def test_correlation_groups_of_the_first_release_keep_their_members_and_kind():
    raise AssertionError("not run")
