from app.core.config import Settings


def test_legacy_environment_names_and_full_completion_url_are_supported():
    config = Settings(
        API_Key="example-secret",
        URL="https://provider.example/v1/chat/completions",
        MODEL_ID="provider-model",
        DEMO_MODE=False,
    )

    assert config.api_key == "example-secret"
    assert config.normalized_base_url == "https://provider.example/v1"
    assert config.ai_configured


def test_remote_http_api_url_is_not_used_for_credentialed_requests():
    config = Settings(
        API_KEY="example-secret",
        BASE_URL="http://provider.example/v1",
        MODEL_ID="provider-model",
        DEMO_MODE=False,
    )

    assert config.normalized_base_url is None
    assert not config.ai_configured
