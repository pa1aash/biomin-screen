"""Checks on the shipped evidence table: it validates and every row has a DOI and a locator."""
from pathlib import Path

import pytest

from biomin_screen.literature import evidence as E

REPO = Path(__file__).resolve().parents[2]
TABLE = REPO / "data" / "evidence_table.csv"


@pytest.mark.skipif(not TABLE.exists(), reason="no evidence table yet")
def test_evidence_table_validates():
    assert E.validate_file(TABLE) == []


@pytest.mark.skipif(not TABLE.exists(), reason="no evidence table yet")
def test_every_row_has_doi_and_locator():
    _, rows = E.read_csv(TABLE)
    assert rows and all(r["doi"].strip() and r["locator"].strip() for r in rows)


@pytest.mark.skip(reason="scans the research corpus (lit/) against forbidden-claim patterns of a scope file that is not shipped")
def test_corpus_files_free_of_scope_patterns():
    raise AssertionError("not run")
