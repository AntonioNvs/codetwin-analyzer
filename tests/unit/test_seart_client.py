import pytest

from typing import Optional
from unittest.mock import MagicMock
from codetwin_analyzer.seart_client import SEARTClient, SEARTAPIError

pytestmark = pytest.mark.unit


def _make_mock_response(status_code: int, json_data: Optional[dict] = None, text: str = "") -> MagicMock:
    """Helper: cria um MagicMock simulando uma requests.Response."""
    mock_resp = MagicMock()
    mock_resp.status_code = status_code
    mock_resp.text = text
    if json_data is not None:
        mock_resp.json.return_value = json_data
    else:
        mock_resp.json.side_effect = ValueError("No JSON")
    return mock_resp


class TestSEARTClient:
    """Testes unitários para a classe SEARTClient."""

    def test_search_repositories_basic(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """search_repositories retorna lista de full_names corretamente."""
        json_data = {
            "items": [
                {"name": "owner1/repo1"},
                {"name": "owner2/repo2"},
            ]
        }
        mock_get = MagicMock(return_value=_make_mock_response(200, json_data))
        monkeypatch.setattr("requests.Session.get", mock_get)

        client = SEARTClient()
        result = client.search_repositories(language="Python")

        assert result == ["owner1/repo1", "owner2/repo2"]

    def test_search_repositories_with_filters(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """search_repositories envia os query params corretos para a API."""
        json_data = {"items": [{"name": "owner/repo"}]}
        mock_get = MagicMock(return_value=_make_mock_response(200, json_data))
        monkeypatch.setattr("requests.Session.get", mock_get)

        client = SEARTClient()
        client.search_repositories(
            language="Java",
            min_stars=50,
            max_results=10,
            created_after="2020-01-01",
            created_before="2023-12-31",
            min_size_kb=100,
            max_size_kb=5000,
            license_filter="MIT",
        )

        _, kwargs = mock_get.call_args
        params = kwargs.get("params", {})

        assert params["language"] == "Java"
        assert params["starsMin"] == 50
        assert params["size"] == 10
        assert params["createdMin"] == "2020-01-01"
        assert params["createdMax"] == "2023-12-31"
        assert params["sizeMin"] == 100
        assert params["sizeMax"] == 5000
        assert params["license"] == "MIT"

    def test_search_repositories_empty(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Quando a API não retorna repositórios, o resultado deve ser lista vazia."""
        json_data = {"items": []}
        mock_get = MagicMock(return_value=_make_mock_response(200, json_data))
        monkeypatch.setattr("requests.Session.get", mock_get)

        client = SEARTClient()
        result = client.search_repositories(language="Go")

        assert result == []

    def test_search_retry_on_500(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Erro 500 deve gerar 3 tentativas antes de levantar SEARTAPIError."""
        mock_resp_500 = _make_mock_response(500, text="Internal Server Error")
        mock_get = MagicMock(return_value=mock_resp_500)
        monkeypatch.setattr("requests.Session.get", mock_get)
        monkeypatch.setattr("time.sleep", lambda _: None)

        client = SEARTClient()
        with pytest.raises(SEARTAPIError) as exc_info:
            client.search_repositories(language="Python")

        assert mock_get.call_count == 3
        assert "3" in str(exc_info.value)

    def test_get_repository_details(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Repositórios com campo 'content' também são parseados corretamente."""
        json_data = {
            "content": [
                {"name": "owner3/repo3"},
                {"name": "owner4/repo4"},
            ]
        }
        mock_get = MagicMock(return_value=_make_mock_response(200, json_data))
        monkeypatch.setattr("requests.Session.get", mock_get)

        client = SEARTClient()
        result = client.search_repositories(language="JavaScript")

        assert "owner3/repo3" in result
        assert "owner4/repo4" in result

    def test_rate_limit_retry(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Erro 429 (4xx) levanta SEARTAPIError imediatamente, sem retry."""
        mock_resp_429 = _make_mock_response(429, text="Too Many Requests")
        mock_get = MagicMock(return_value=mock_resp_429)
        monkeypatch.setattr("requests.Session.get", mock_get)

        client = SEARTClient()
        with pytest.raises(SEARTAPIError) as exc_info:
            client.search_repositories(language="Python")

        assert mock_get.call_count == 1
        assert "429" in str(exc_info.value)
