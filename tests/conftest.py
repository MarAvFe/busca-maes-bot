"""Pytest configuration and shared fixtures."""

import pytest

from buscamaes.sources.rnp import reset_rnp_client


@pytest.fixture(autouse=True)
def _reset_rnp_client():
    """Reset RNP client singleton before each test for isolation."""
    reset_rnp_client()
    yield
    reset_rnp_client()
