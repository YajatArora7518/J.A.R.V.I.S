"""Unit tests never recover a mocked HTTP failure by opening the user's browser."""
from unittest.mock import patch
import pytest


@pytest.fixture(autouse=True)
def isolate_browser_search():
    with patch('actions.browser_search.search_in_browser', return_value=[]):
        yield
