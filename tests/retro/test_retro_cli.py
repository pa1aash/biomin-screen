"""The retro check command (skipped: the command line is not shipped)."""
import pytest

pytestmark = pytest.mark.skip(reason='the retro command line is not part of the shipped package')


def test_retro_check_command_passes_on_committed_files():
    raise AssertionError("not run")
