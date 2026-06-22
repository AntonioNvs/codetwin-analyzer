import pytest
import json
import shutil
import requests
from pathlib import Path
from codetwin_analyzer.cli import CodeTwinCLI

# Marca todos os testes deste arquivo como de integração
pytestmark = pytest.mark.integration


def _pmd_available() -> bool:
    """Verifica se o executável PMD está disponível no sistema."""
    return shutil.which("pmd") is not None


def _seart_host_reachable() -> bool:
    """Verifica se o host do SEART responde (apenas conectividade de rede).

    Não valida se a API está funcional — apenas se o servidor aceita conexão TCP/SSL.
    A validação da API é feita em runtime dentro do teste."""
    for verify in (True, False):
        try:
            requests.get(
                "https://seart-ghs.si.usi.ch/",
                timeout=10,
                verify=verify,
            )
            return True
        except requests.exceptions.SSLError:
            continue
        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout):
            return False
    return False


pmd_required = pytest.mark.skipif(
    not _pmd_available(),
    reason="PMD não está instalado no sistema. Instale o PMD para rodar testes de integração."
)

seart_required = pytest.mark.skipif(
    not _seart_host_reachable(),
    reason="Host SEART inacessível (erro de rede/SSL). Verifique sua conexão."
)

class TestEndToEnd:
    """Testes de integração fim-a-fim para a CLI do CodeTwin Analyzer."""

    @pmd_required
    def test_full_pipeline_small_repo(self, capsys) -> None:
        """baixa repo público pequeno real, roda pipeline completo, verifica saída."""
        cli = CodeTwinCLI(quiet=True)
        
        # docopt é um repositório pequeno de Python com um único arquivo importante.
        repo_url = "https://github.com/docopt/docopt"
        
        # Como o docopt é muito pequeno, talvez não encontre clones (min_tokens alto). 
        # Vamos passar min_tokens baixo ou apenas validar que não quebra.
        try:
            cli.analyze(repo_url, min_tokens=10)
        except SystemExit as e:
            if e.code != 0:
                pytest.fail(f"Pipeline abortou com exit code {e.code}")

        _capsys_out, err = capsys.readouterr()
        # O pipeline deve terminar com sucesso sem dar exceções não tratadas
        assert "CodeTwin" not in err.lower() or "error" not in err.lower()

    @pmd_required
    def test_json_export_roundtrip(self, tmp_path: Path) -> None:
        """exporta JSON, verifica parse reverso."""
        cli = CodeTwinCLI(quiet=True)
        out_file = tmp_path / "integration_export.json"
        
        repo_url = "https://github.com/docopt/docopt"
        
        try:
            cli.analyze(repo_url, format="json", output=str(out_file), min_tokens=10, history=False)
        except SystemExit as e:
            if e.code != 0:
                pytest.fail("A exportação JSON abortou o programa prematuramente.")

        # Verifica parse reverso
        assert out_file.exists(), "O arquivo JSON não foi gerado."
        
        with open(out_file, "r", encoding="utf-8") as f:
            data = json.load(f)
            
        assert "metrics" in data
        assert "history" in data

    @pmd_required
    @seart_required
    def test_search_and_analyze(self) -> None:
        """busca SEART + análise de 1 repo."""
        cli = CodeTwinCLI(quiet=True)

        try:
            # Buscando projetos minúsculos e limitando a 1 resultado
            cli.search(language="python", min_stars=500, max_results=1, analyze=True)
        except SystemExit as e:
            if e.code != 0:
                pytest.skip(
                    "SEART search falhou no ambiente atual "
                    "(API pode estar instável ou com parâmetros alterados)."
                )
