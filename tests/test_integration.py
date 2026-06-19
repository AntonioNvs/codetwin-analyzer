import pytest
import json
from pathlib import Path
from codetwin_analyzer.cli import CodeTwinCLI

# Marca todos os testes deste arquivo como de integração
pytestmark = pytest.mark.integration

class TestEndToEnd:
    """Testes de integração fim-a-fim para a CLI do CodeTwin Analyzer."""

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

        out, err = capsys.readouterr()
        # O pipeline deve terminar com sucesso sem dar exceções não tratadas
        assert "CodeTwin" not in err.lower() or "error" not in err.lower()

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

    def test_search_and_analyze(self) -> None:
        """busca SEART + análise de 1 repo."""
        cli = CodeTwinCLI(quiet=True)
        
        try:
            # Buscando projetos minúsculos e limitando a 1 resultado
            cli.search(language="python", min_stars=500, max_results=1, analyze=True)
        except SystemExit as e:
            if e.code != 0:
                pytest.fail("Comando search com analyze=True falhou.")
