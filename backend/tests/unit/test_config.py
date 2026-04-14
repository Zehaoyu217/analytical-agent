from app.config import get_config


def test_config_loads_defaults() -> None:
    config = get_config()
    assert config.environment == "test"
    assert config.host == "127.0.0.1"
    assert config.port == 8000


def test_config_sandbox_defaults() -> None:
    config = get_config()
    assert config.sandbox_timeout_seconds == 30
    assert config.sandbox_max_memory_mb == 2048


def test_config_model_default() -> None:
    config = get_config()
    assert config.default_model == "qwen3.5:9b"
