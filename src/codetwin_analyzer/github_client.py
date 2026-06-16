import os
import zipfile
import tempfile
import requests

from pathlib import Path
from typing import Dict, Any, Optional, List


class GitHubAPIError(Exception):
    """Exceção customizada para erros na API do GitHub."""
    pass


class GitHubClient:
    def __init__(self, token: Optional[str] = None):
        """
        Inicializa o clienta da API do GitHub.
        Se o token não for passado, tenta ler da variável de ambiente GITHUB_TOKEN.
        """
        self.token = token or os.environ.get("GITHUB_TOKEN")
        self.base_url = "https://api.github.com"

        self.session = requests.Session()
        self.session.headers.update({
            "Accept": "application/vnd.github.v3+json",
        })

        if self.token:
            self.session.headers.update({
                "Authorization": f"Bearer {self.token}"
            })

    def _get(self, url: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Faz uma requisição GET. Se a URL for um caminho relativo (ex: /repos/...),
        concatena com a base_url. Levanta GitHubAPIError se o status não for 200.
        """
        if url.startswith("/"):
            url = f"{self.base_url}{url}"

        response = self.session.get(url, params=params)

        if response.status_code != 200:
            raise GitHubAPIError(
                f"Erro na API do GitHub (Status {response.status_code}) ao acessar {url}: {response.text}"
            )

        return response.json()

    def get_default_branch(self, owner: str, repo: str) -> str:
        """
        Obtém a branch padrão (default_branch) de um repositório.
        """
        endpoint = f"/repos/{owner}/{repo}"
        data = self._get(endpoint)
        return data.get("default_branch", "main")

    def get_repo_metadata(self, owner: str, repo: str) -> Dict[str, Any]:
        """
        Obtém metadados específicos de um repositório.
        """
        endpoint = f"/repos/{owner}/{repo}"
        data = self._get(endpoint)

        repo_license = data.get("license")
        license_name = repo_license.get("name") if repo_license else None

        return {
            "stars": data.get("stargazers_count", 0),
            "forks": data.get("forks_count", 0),
            "language": data.get("language"),
            "created_at": data.get("created_at"),
            "updated_at": data.get("updated_at"),
            "size": data.get("size", 0),
            "open_issues": data.get("open_issues_count", 0),
            "license": license_name,
        }

    def download_repository(self, owner: str, repo: str, destination: str, branch: Optional[str] = None) -> None:
        """
        Baixa o código fonte do repositório em formato ZIP uitilizando stream
        para economizar memória e extrai no destino especificado.
        """
        if not branch:
            branch = self.get_default_branch(owner, repo)

        endpoint = f"{self.base_url}/repos/{owner}/{repo}/zipball/{branch}"

        response = self.session.get(endpoint, stream=True)
        if response.status_code != 200:
            raise GitHubAPIError(
                f"Erro ao baixar o repositório {owner}/{repo} (Status {response.status_code}): {response.text}"
            )

        with tempfile.NamedTemporaryFile(delete=False, suffix=".zip") as tmp_file:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    tmp_file.write(chunk)
            tmp_path = tmp_file.name

        try:
            with zipfile.ZipFile(tmp_path, "r") as zip_ref:
                zip_ref.extractall(destination)
        finally:
            Path(tmp_path).unlink(missing_ok=True)

    def get_branches(self, owner: str, repo: str) -> List[str]:
        """
        Retorna uma lista com os nomes de todas as branches do repositório.
        """
        endpoint = f"/repos/{owner}/{repo}/branches"
        branches_data = self._get(endpoint)

        return [branch["name"] for branch in branches_data]

    def get_commits(
        self,
        owner: str,
        repo: str,
        since: Optional[str] = None,
        until: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Obtém a lista de commits de um repositório, lidando com a paginação da API.
        Retorna uma lista padronizada com sha, data, mensagem e autor.
        """
        url = f"{self.base_url}/repos/{owner}/{repo}/commits"
        params = {"per_page": 100}

        if since:
            params["since"] = since
        if until:
            params["until"] = until

        parsed_commits = []

        while url:
            response = self.session.get(url, params=params)

            if response.status_code != 200:
                raise GitHubAPIError(
                    f"Erro ao buscar commits (Status {response.status_code}): {response.text}"
                )

            data = response.json()

            for item in data:
                commit_info = item.get("commit", {})
                author_info = commit_info.get("author", {})

                parsed_commits.append({
                    "sha": item.get("sha"),
                    "date": author_info.get("date"),
                    "message": commit_info.get("message"),
                    "author": author_info.get("name"),
                })

            params = None
            url = response.links.get("next", {}).get("url")

        return parsed_commits
