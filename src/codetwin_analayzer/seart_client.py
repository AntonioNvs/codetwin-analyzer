import requests

from typing import List

class SEARTAPIError(Exception):
    """Exceção customizada para erros na API do SEART GHS."""
    pass

class SEARTClient:
    def __init__(self):
        """
        Inicializa o cliente da API SEART GitHub Search (GHS).
        """
        self.base_url = "https://seart-ghs.si.usi.ch/api"
        self.session = requests.Session()

        self.session.headers.update({
            "Accept": "application/json",
        })

    def search_repositories(self, language: str, min_stars: int = 0, max_results: int = 100) -> List[str]:
        """
        Chama o endpoint de busca do SEART GHS filtrando por linguagem e quantidade mínima de estrelas.
        Retorna uma lista de 'full_name' (owner/repo) limitada a 'max_results'.
        """
        endpoint = f"{self.base_url}/v1/search/repositories"

        params = {
            "language": language,
            "starsMin": min_stars,
            "size": max_results
        }

        response = self.session.get(endpoint, params=params)

        if response.status_code != 200:
            raise SEARTAPIError(
                f"Erro ao buscar repositórios no SEART (Status {response.status_code}): {response.text}"
            )

        data = response.json()

        if isinstance(data, dict):
            items = data.get("items", data.get("content", []))
        else:
            items = data

        full_names = []

        for repo in items:
            full_name = repo.get("name")

            if full_name:
                full_names.append(full_name)

            if len(full_names) >= max_results:
                break

        return full_names

