""""""
import pytest

pytestmark = pytest.mark.skip(reason='needs the retrieval package and the thread stage of the literature tooling, which are not shipped')


def test_unknown_thread():
    raise AssertionError("not run")


def test_paths_are_thread_scoped():
    raise AssertionError("not run")


def test_search_logs_query():
    raise AssertionError("not run")


def test_search_unknown_route():
    raise AssertionError("not run")


def test_fulltext_paywalled_is_logged():
    raise AssertionError("not run")


def test_fulltext_falls_back_to_archived_copy():
    raise AssertionError("not run")


def test_fulltext_europepmc_xml():
    raise AssertionError("not run")


def test_abstract_cached_locally_and_logged():
    raise AssertionError("not run")


def test_abstract_missing_logged():
    raise AssertionError("not run")


def test_pdf_page_markers():
    raise AssertionError("not run")


def test_jats_table_cells():
    raise AssertionError("not run")


def test_inverted_index():
    raise AssertionError("not run")


def test_merge_run_writes_outputs():
    raise AssertionError("not run")


def test_merge_refuses_invalid_rows():
    raise AssertionError("not run")
