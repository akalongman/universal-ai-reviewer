import json
import pytest
from unittest.mock import MagicMock, patch


def _build_github_provider(repo_mock):
    from reviewer.vcs_providers import GitHubProvider

    event_payload = {"pull_request": {"number": 42}}
    tmp_file = "/tmp/_test_github_event.json"
    with open(tmp_file, "w") as fh:
        json.dump(event_payload, fh)

    with patch("reviewer.vcs_providers.GitHubProvider.__init__", lambda self, *_args, **_kwargs: None):
        provider = GitHubProvider.__new__(GitHubProvider)
        provider.repo = repo_mock
        provider.pr = MagicMock(head=MagicMock(sha="head-sha-abc"))
        provider.head_sha = "head-sha-abc"
        provider.pr_number = 42
        provider.issue = MagicMock()
        return provider


def test_github_get_file_content_exists():
    from reviewer.vcs_providers import GitHubProvider

    content_file = MagicMock(decoded_content=b"console.log('hi');")
    content_file.__class__ = MagicMock
    repo = MagicMock()
    repo.get_contents.return_value = content_file

    provider = _build_github_provider(repo)
    result = provider.get_file_content("src/handler.js", "head-sha-abc")

    assert result == "console.log('hi');"
    repo.get_contents.assert_called_once_with("src/handler.js", ref="head-sha-abc")


def test_github_get_file_content_404_returns_none():
    from github import UnknownObjectException
    repo = MagicMock()
    repo.get_contents.side_effect = UnknownObjectException(404, {"message": "Not Found"}, {})

    provider = _build_github_provider(repo)
    assert provider.get_file_content("src/missing.js", "head-sha-abc") is None


def test_github_get_file_content_other_error_propagates():
    repo = MagicMock()
    repo.get_contents.side_effect = RuntimeError("rate limit")

    provider = _build_github_provider(repo)
    with pytest.raises(RuntimeError):
        provider.get_file_content("src/handler.js", "head-sha-abc")


def test_github_get_file_content_directory_returns_none():
    repo = MagicMock()
    repo.get_contents.return_value = [MagicMock(), MagicMock()]

    provider = _build_github_provider(repo)
    assert provider.get_file_content("src/", "head-sha-abc") is None


def _build_gitlab_provider(project_mock):
    from reviewer.vcs_providers import GitLabProvider
    provider = GitLabProvider.__new__(GitLabProvider)
    provider.project = project_mock
    provider.mr = MagicMock(sha="head-sha-xyz")
    provider.head_sha = "head-sha-xyz"
    provider.gl = MagicMock()
    return provider


def test_gitlab_get_file_content_exists():
    file_obj = MagicMock()
    file_obj.decode.return_value = b"<?php echo 'hi'; ?>"
    project = MagicMock()
    project.files.get.return_value = file_obj

    provider = _build_gitlab_provider(project)
    result = provider.get_file_content("src/Service.php", "head-sha-xyz")

    assert result == "<?php echo 'hi'; ?>"
    project.files.get.assert_called_once_with(file_path="src/Service.php", ref="head-sha-xyz")


def test_gitlab_get_file_content_404_returns_none():
    from gitlab.exceptions import GitlabGetError
    err = GitlabGetError("not found")
    err.response_code = 404
    project = MagicMock()
    project.files.get.side_effect = err

    provider = _build_gitlab_provider(project)
    assert provider.get_file_content("src/missing.php", "head-sha-xyz") is None


def test_gitlab_get_file_content_other_error_propagates():
    from gitlab.exceptions import GitlabGetError
    err = GitlabGetError("server error")
    err.response_code = 500
    project = MagicMock()
    project.files.get.side_effect = err

    provider = _build_gitlab_provider(project)
    with pytest.raises(GitlabGetError):
        provider.get_file_content("src/Service.php", "head-sha-xyz")
