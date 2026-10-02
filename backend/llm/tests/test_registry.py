import pytest

import llm


def test_three_providers_with_labels():
    assert [(p.name, p.label) for p in llm.PROVIDERS.values()] == [
        ("anthropic", "Claude"),
        ("openai", "ChatGPT"),
        ("gemini", "Gemini"),
    ]
    assert llm.DEFAULT_PROVIDER == "anthropic"


def test_claude_defaults_to_opus_5_5():
    claude = llm.get_provider("anthropic")

    assert claude.default_model == "claude-opus-5-5"
    assert "claude-sonnet-5-5" in claude.recommended_models


def test_unknown_provider():
    with pytest.raises(ValueError):
        llm.get_provider("mistral")


@pytest.mark.parametrize(
    ("provider", "key", "masked"),
    [
        ("anthropic", "sk-ant-api03-secretWXYZ", "sk-ant-...WXYZ"),
        ("openai", "sk-proj-secretWXYZ", "sk-...WXYZ"),
        ("gemini", "AIzaSySecretWXYZ", "AIza...WXYZ"),
        ("gemini", "unexpected-formatWXYZ", "...WXYZ"),
    ],
)
def test_mask_key_shows_only_fixed_prefix_and_last4(provider, key, masked):
    assert llm.get_provider(provider).mask_key(key) == masked
