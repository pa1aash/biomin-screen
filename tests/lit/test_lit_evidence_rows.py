"""Row ids and thread codes of the evidence table; the merge rules of thread outputs are skipped."""
import pytest

from lit_helpers import good_row
from biomin_screen.literature import evidence as E


def test_threads_f_to_j_validate():
    for t in ("T-F", "T-G", "T-H", "T-I", "T-J"):
        rid = t.replace("-", "") + "-001"
        assert E.validate_row(good_row(row_id=rid, thread=t)) == []
    assert E.validate_row(good_row(row_id="TU-001", thread="T-U"))


def test_threads_k_to_m_validate():
    for t in ("T-K", "T-L", "T-M"):
        rid = t.replace("-", "") + "-001"
        assert E.validate_row(good_row(row_id=rid, thread=t)) == []
    assert E.validate_row(good_row(row_id="TK-001", thread="T-L"))


def test_threads_n_to_q_validate():
    for t in ("T-N", "T-O", "T-P", "T-Q"):
        rid = t.replace("-", "") + "-001"
        assert E.validate_row(good_row(row_id=rid, thread=t)) == []
    assert E.validate_row(good_row(row_id="TU-001", thread="T-U"))


@pytest.mark.skip(reason="merging thread outputs belongs to the merge tooling and the run record it writes, which are not shipped")
def test_merge_key_ignores_range_and_unit():
    raise AssertionError("not run")


@pytest.mark.skip(reason="merging thread outputs belongs to the merge tooling and the run record it writes, which are not shipped")
def test_merge_key_keeps_distinct_values_and_symbols():
    raise AssertionError("not run")


@pytest.mark.skip(reason="merging thread outputs belongs to the merge tooling and the run record it writes, which are not shipped")
def test_merge_skips_unstarted_threads_and_writes_the_run_record():
    raise AssertionError("not run")


@pytest.mark.skip(reason="merging thread outputs belongs to the merge tooling and the run record it writes, which are not shipped")
def test_merge_key_uses_the_range_of_range_only_rows():
    raise AssertionError("not run")
