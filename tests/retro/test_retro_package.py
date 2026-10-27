"""Submission package validator (skipped: the package and its metadata are not shipped)."""
import pytest

pytestmark = pytest.mark.skip(reason='validates the preprint submission package, which is not shipped')


def test_orcid_checksum():
    raise AssertionError("not run")


def test_committed_package_passes_with_placeholders_listed():
    raise AssertionError("not run")


def test_release_mode_fails_on_placeholders():
    raise AssertionError("not run")


def test_copied_package_passes():
    raise AssertionError("not run")


def test_email_address_rejected():
    raise AssertionError("not run")


def test_bad_orcid_rejected():
    raise AssertionError("not run")


def test_author_order_must_match_register():
    raise AssertionError("not run")


def test_single_corresponding_author():
    raise AssertionError("not run")


def test_credit_roles_checked_against_taxonomy():
    raise AssertionError("not run")


def test_sourced_item_needs_recheck_mark_and_known_id():
    raise AssertionError("not run")


def test_cited_id_must_appear_in_recheck_list():
    raise AssertionError("not run")


def test_checklist_items_need_source_and_mark():
    raise AssertionError("not run")


def test_result_numbers_rejected():
    raise AssertionError("not run")


def test_non_result_digits_allowed():
    raise AssertionError("not run")


def test_scope_language_rejected():
    raise AssertionError("not run")


def test_missing_file_reported():
    raise AssertionError("not run")


def test_package_check_command():
    raise AssertionError("not run")
