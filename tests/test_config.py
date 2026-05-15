import pytest
from reviewer.config import _env_bool, Config


@pytest.fixture
def base_env(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "fake-anthropic-key")
    monkeypatch.setenv("VCS_PROVIDER", "github")
    monkeypatch.setenv("GITHUB_TOKEN", "fake-token")
    monkeypatch.setenv("GITHUB_REPOSITORY", "owner/repo")
    monkeypatch.setenv("GITHUB_EVENT_PATH", "/tmp/event.json")
    monkeypatch.delenv("AI_FETCH_CHANGED_FULL", raising=False)
    monkeypatch.delenv("AI_FETCH_RELATED_FILES", raising=False)
    monkeypatch.delenv("AI_FETCH_RELATED_DEPTH", raising=False)
    monkeypatch.delenv("GITLAB_CI", raising=False)
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)


def test_env_bool_truthy_values(monkeypatch):
    for value in ("true", "TRUE", "True", "1", "yes", "YES"):
        monkeypatch.setenv("FLAG", value)
        assert _env_bool("FLAG") is True


def test_env_bool_falsy_values(monkeypatch):
    for value in ("false", "0", "no", "", "anything-else", "off"):
        monkeypatch.setenv("FLAG", value)
        assert _env_bool("FLAG") is False


def test_env_bool_unset(monkeypatch):
    monkeypatch.delenv("FLAG", raising=False)
    assert _env_bool("FLAG") is False


def test_fetch_defaults_off(base_env):
    config = Config()
    assert config.fetch_changed_full is False
    assert config.fetch_related_files is False
    assert config.fetch_related_depth == 1


def test_fetch_changed_full_enabled(base_env, monkeypatch):
    monkeypatch.setenv("AI_FETCH_CHANGED_FULL", "true")
    config = Config()
    assert config.fetch_changed_full is True


def test_fetch_related_files_enabled(base_env, monkeypatch):
    monkeypatch.setenv("AI_FETCH_RELATED_FILES", "1")
    config = Config()
    assert config.fetch_related_files is True


def test_fetch_related_depth_explicit(base_env, monkeypatch):
    monkeypatch.setenv("AI_FETCH_RELATED_DEPTH", "3")
    config = Config()
    assert config.fetch_related_depth == 3


def test_fetch_related_depth_zero_is_allowed(base_env, monkeypatch):
    monkeypatch.setenv("AI_FETCH_RELATED_DEPTH", "0")
    config = Config()
    assert config.fetch_related_depth == 0


def test_fetch_related_depth_invalid_string_fails(base_env, monkeypatch):
    monkeypatch.setenv("AI_FETCH_RELATED_DEPTH", "banana")
    with pytest.raises(SystemExit):
        Config()


def test_fetch_related_depth_negative_fails(base_env, monkeypatch):
    monkeypatch.setenv("AI_FETCH_RELATED_DEPTH", "-1")
    with pytest.raises(SystemExit):
        Config()
