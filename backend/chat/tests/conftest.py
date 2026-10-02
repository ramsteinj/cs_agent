from unittest import mock

import pytest


@pytest.fixture(autouse=True)
def _no_real_claude_calls():
    """Fail loudly if a test would reach the real Anthropic API.

    Tests that exercise llm.py patch anthropic.Anthropic themselves (inner patch wins).
    """
    with mock.patch(
        "chat.llm.anthropic.Anthropic",
        side_effect=AssertionError("real Anthropic API call in tests"),
    ):
        yield
