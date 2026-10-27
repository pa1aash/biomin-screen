"""Reference audit of a manuscript bibliography (skipped: the manuscript and its bibliography are not shipped)."""
import pytest

pytestmark = pytest.mark.skip(reason='audits the manuscript bibliography, which is not shipped')


def test_rows_per_key_support_and_problems():
    raise AssertionError("not run")


def test_unknown_rows_and_wrong_doi_are_refused():
    raise AssertionError("not run")


def test_resolution_falls_back_to_datacite_and_reads_update_notices():
    raise AssertionError("not run")


def test_committed_audit_covers_every_bib_key():
    raise AssertionError("not run")
