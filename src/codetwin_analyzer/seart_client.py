import time
import requests

from typing import List, Optional


class SEARTAPIError(Exception):
    """Exceção customizada para erros na API do SEART GHS."""
    pass


class SEARTClient:
    def __init__(self):
        """Inicializa o cliente da API SEART GitHub Search (GHS)."""
        self.base_url = "https://seart-ghs.si.usi.ch/api"
        self.session = requests.Session()

        self.session.headers.update({
            "Accept": "application/json",
        })

    def search_repositories(
        self,
        language: str,
        min_stars: int = 0,
        max_results: int = 100,
        created_after: Optional[str] = None,
        created_before: Optional[str] = None,
        min_size_kb: Optional[int] = None,
        max_size_kb: Optional[int] = None,
        license_filter: Optional[str] = None
    ) -> List[str]:
        """Busca repositórios no SEART GHS com múltiplos filtros e mecanismo de retry (backoff).

        Args:
            language (str): A linguagem de programação para filtro principal.
            min_stars (int, optional): Número mínimo de estrelas do repositório. Default é 0.
            max_results (int, optional): Número máximo de resultados retornados. Default é 100.
            created_after (str, optional): Filtra repositórios criados após esta data (ISO 8601).
            created_before (str, optional): Filtra repositórios criados antes desta data (ISO 8601).
            min_size_kb (int, optional): Tamanho mínimo do repositório em KB.
            max_size_kb (int, optional): Tamanho máximo do repositório em KB.
            license_filter (str, optional): Filtra repositórios pela licença.

        Returns:
            List[str]: Lista contendo o nome completo (owner/repo) dos repositórios encontrados.

        Raises:
            SEARTAPIError: Caso ocorra um erro na requisição à API (status 400 ou 500) após as tentativas.
        """
        endpoint = f"{self.base_url}/v1/search/repositories"

        params = {
            "language": language,
            "starsMin": min_stars,
            "size": max_results
        }

        if created_after:
            params["createdMin"] = created_after
        if created_before:
            params["createdMax"] = created_before
        if min_size_kb:
            params["sizeMin"] = min_size_kb
        if max_size_kb:
            params["sizeMax"] = max_size_kb
        if license_filter:
            params["license"] = license_filter

        max_retries = 3

        for attempt in range(max_retries):
            try:
                response = self.session.get(endpoint, params=params, timeout=30)

                if response.status_code == 200:
                    break

                elif 400 <= response.status_code < 500:
                    raise SEARTAPIError(
                        f"Erro de requisição ({response.status_code}): Seus parâmetros podem estar incorretos. "
                        f"Detalhes: {response.text}"
                    )

                elif 500 <= response.status_code < 600:
                    error_msg = f"Erro no servidor SEART (Status {response.status_code})."

            except requests.exceptions.RequestException as e:
                error_msg = f"Falha de conexão ao SEART: {str(e)}"

            if attempt < max_retries - 1:
                sleep_time = 2 ** attempt
                print(
                    f"{error_msg} Tentando novamente em {sleep_time} segundos... "
                    f"(Tentativa {attempt + 1}/{max_retries})"
                )
                time.sleep(sleep_time)
            else:
                raise SEARTAPIError(
                    f"Falha ao buscar repositórios após {max_retries} tentativas. Último erro: {error_msg}")

        try:
            data = response.json()
        except ValueError:
            raise SEARTAPIError(
                f"A API retornou uma resposta não-JSON (Status {response.status_code}): {response.text}")

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
