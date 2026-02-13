import os
import tempfile
import shutil
import pathlib
import pytest


@pytest.fixture
def tmp_dir():
    """Provide a temporary directory that is cleaned up after the test."""
    d = tempfile.mkdtemp(prefix="protea_test_")
    yield pathlib.Path(d)
    shutil.rmtree(d, ignore_errors=True)


@pytest.fixture
def project_root():
    """Return the project root path."""
    return pathlib.Path(__file__).resolve().parent.parent
