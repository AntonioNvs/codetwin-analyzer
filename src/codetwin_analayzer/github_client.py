import os
import requests

from typing import Dict, Any, Optional

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