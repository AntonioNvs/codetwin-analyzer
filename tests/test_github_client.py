import io
import os
import zipfile
import pytest

from unittest.mock import MagicMock
from codetwin_analyzer.github_client import GitHubClient, GitHubAPIError


class TestGitHubClient:
    """Testes unitários para a classe GitHubClient."""

    def test_init_with_token(self) -> None:
        """Verifica que o header Authorization é configurado corretamente."""
        client = GitHubClient(token="test-token-123")
        assert client.session.headers.get("Authorization") == "Bearer test-token-123"

    def test_init_without_token_uses_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Verifica que o token é lido de GITHUB_TOKEN quando não passado."""
        monkeypatch.setenv("GITHUB_TOKEN", "env-token-abc")
        client = GitHubClient()
        assert client.token == "env-token-abc"
        assert client.session.headers.get("Authorization") == "Bearer env-token-abc"

    def test_get_success(self, mock_github_session: MagicMock) -> None:
        """_get retorna JSON corretamente em resposta 200."""
        mock_github_session.return_value.status_code = 200
        mock_github_session.return_value.json.return_value = {"key": "value"}

        client = GitHubClient(token="token")
        result = client._get("/repos/owner/repo")

        assert result == {"key": "value"}

    def test_get_http_error(self, mock_github_session: MagicMock) -> None:
        """_get levanta GitHubAPIError quando o status_code não é 200."""
        mock_github_session.return_value.status_code = 404
        mock_github_session.return_value.text = "Not Found"

        client = GitHubClient(token="token")

        with pytest.raises(GitHubAPIError) as exc_info:
            client._get("/repos/owner/inexistente")

        assert "404" in str(exc_info.value)

    def test_get_default_branch(self, mock_github_session: MagicMock) -> None:
        """get_default_branch retorna o valor de 'default_branch' da API."""
        mock_github_session.return_value.status_code = 200
        mock_github_session.return_value.json.return_value = {
            "default_branch": "main",
            "name": "repo",
        }

        client = GitHubClient(token="token")
        branch = client.get_default_branch("owner", "repo")

        assert branch == "main"

    def test_get_repo_metadata_returns_expected_keys(self, mock_github_session: MagicMock) -> None:
        """get_repo_metadata retorna dict com todas as chaves esperadas."""
        mock_github_session.return_value.status_code = 200
        mock_github_session.return_value.json.return_value = {
            "stargazers_count": 42,
            "forks_count": 10,
            "language": "Python",
            "created_at": "2020-01-01T00:00:00Z",
            "updated_at": "2021-06-15T12:00:00Z",
            "size": 1024,
            "open_issues_count": 5,
            "license": {"name": "MIT License"},
        }

        client = GitHubClient(token="token")
        metadata = client.get_repo_metadata("owner", "repo")

        expected_keys = {
            "stars", "forks", "language", "created_at",
            "updated_at", "size", "open_issues", "license",
        }
        assert set(metadata.keys()) == expected_keys
        assert metadata["stars"] == 42
        assert metadata["forks"] == 10
        assert metadata["language"] == "Python"
        assert metadata["license"] == "MIT License"

    def test_download_repository(self, tmp_path: pytest.TempPathFactory, mock_github_session: MagicMock) -> None:
        """download_repository faz GET com stream e extrai o ZIP no destino."""
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w") as zf:
            zf.writestr("owner-repo-abc123/README.md", "# Test Repo")
        zip_bytes = zip_buffer.getvalue()

        mock_branch_response = MagicMock()
        mock_branch_response.status_code = 200
        mock_branch_response.json.return_value = {"default_branch": "main"}
        mock_branch_response.links = {}

        mock_zip_response = MagicMock()
        mock_zip_response.status_code = 200
        mock_zip_response.iter_content.return_value = [zip_bytes]

        mock_github_session.side_effect = [mock_branch_response, mock_zip_response]

        destination = str(tmp_path / "extracted")
        os.makedirs(destination, exist_ok=True)

        client = GitHubClient(token="token")
        client.download_repository("owner", "repo", destination)

        extracted_files = list(tmp_path.rglob("*.md"))
        assert len(extracted_files) == 1
        assert extracted_files[0].read_text() == "# Test Repo"
