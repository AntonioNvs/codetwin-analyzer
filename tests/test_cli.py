import logging
import pytest

from io import StringIO
from unittest.mock import MagicMock, patch, call
from codetwin_analyzer.cli import CodeTwinCLI
from codetwin_analyzer.parser import CloneFragment, ClonePair
from codetwin_analyzer.metrics import CloneMetrics


def _make_metrics(total: int = 3, t1: int = 2, t2: int = 1) -> CloneMetrics:
    """Helper: cria um CloneMetrics com valores controlados."""
    return CloneMetrics(
        total_clones=total,
        type1_count=t1,
        type2_count=t2,
        total_files_affected=2,
        total_lines_duplicated=30,
    )


def _make_pairs() -> list[ClonePair]:
    """Helper: retorna uma lista mínima de ClonePairs pré-classificados."""
    frag_a = CloneFragment("a.py", 1, 5, 100, "def foo(): pass")
    frag_b = CloneFragment("b.py", 1, 5, 100, "def foo(): pass")
    return [ClonePair(fragment_a=frag_a, fragment_b=frag_b, shared_tokens=100, type="Tipo 1")]


class TestCLI:
    """Testes de integração para a classe CodeTwinCLI."""

    def test_analyze_with_mock(self, tmp_path: pytest.TempPathFactory, capsys: pytest.CaptureFixture) -> None:
        """analyze exibe o sumário correto quando o pipeline é mockado com sucesso."""
        pairs = _make_pairs()
        metrics = _make_metrics()

        with patch("codetwin_analyzer.cli.GitHubClient") as mock_gh_cls, \
             patch("codetwin_analyzer.cli.CPDRunner") as mock_cpd_cls, \
             patch("codetwin_analyzer.cli.parse_cpd_xml", return_value=[pairs[0].fragment_a, pairs[0].fragment_b]), \
             patch("codetwin_analyzer.cli.group_into_pairs", return_value=pairs), \
             patch("codetwin_analyzer.cli.compute_clone_counts", return_value=metrics), \
             patch("codetwin_analyzer.cli.most_cloned_files", return_value=[("a.py", 2)]), \
             patch("codetwin_analyzer.cli.temp_dir"):

            mock_gh_cls.return_value.download_repository = MagicMock()
            mock_cpd_cls.return_value.run_with_auto_detect = MagicMock()

            cli = CodeTwinCLI()
            cli.analyze(repo_url="https://github.com/owner/repo")

        captured = capsys.readouterr()
        assert "SUMÁRIO" in captured.out
        assert "3" in captured.out  # total_clones
        assert "2" in captured.out  # type1_count

    def test_analyze_invalid_url(self, capsys: pytest.CaptureFixture) -> None:
        """analyze com URL inválida exibe mensagem de erro e chama sys.exit(1)."""
        cli = CodeTwinCLI()

        with pytest.raises(SystemExit) as exc_info:
            cli.analyze(repo_url="nao-e-uma-url-valida")

        assert exc_info.value.code == 1

    def test_search_prints_results(self, capsys: pytest.CaptureFixture) -> None:
        """search exibe a lista de repositórios encontrados pelo SEARTClient."""
        repos = ["owner1/repo1", "owner2/repo2", "owner3/repo3"]

        with patch("codetwin_analyzer.cli.SEARTClient") as mock_seart_cls:
            mock_seart_cls.return_value.search_repositories.return_value = repos

            cli = CodeTwinCLI()
            cli.search(language="Python", max_results=3)

        captured = capsys.readouterr()
        assert "owner1/repo1" in captured.out
        assert "owner2/repo2" in captured.out
        assert "owner3/repo3" in captured.out

    def test_metrics_command(self, capsys: pytest.CaptureFixture) -> None:
        """metrics exibe o painel com contagens e densidade quando o pipeline é mockado."""
        pairs = _make_pairs()
        metrics = _make_metrics()

        with patch("codetwin_analyzer.cli.GitHubClient") as mock_gh_cls, \
             patch("codetwin_analyzer.cli.CPDRunner") as mock_cpd_cls, \
             patch("codetwin_analyzer.cli.parse_cpd_xml", return_value=[pairs[0].fragment_a]), \
             patch("codetwin_analyzer.cli.group_into_pairs", return_value=pairs), \
             patch("codetwin_analyzer.cli.compute_clone_counts", return_value=metrics), \
             patch("codetwin_analyzer.cli.most_cloned_files", return_value=[("a.py", 2)]), \
             patch("codetwin_analyzer.cli.clone_density", return_value=0.05), \
             patch("codetwin_analyzer.cli.temp_dir"):

            mock_gh_cls.return_value.download_repository = MagicMock()
            mock_cpd_cls.return_value.detect_language.return_value = "python"
            mock_cpd_cls.return_value.run_cpd = MagicMock()

            cli = CodeTwinCLI()
            cli.metrics(repo_url="https://github.com/owner/repo")

        captured = capsys.readouterr()
        assert "PAINEL" in captured.out or "LIMPO" in captured.out

    def test_verbose_flag(self, caplog: pytest.LogCaptureFixture) -> None:
        """Instanciar CLI com verbose=True faz o logger aceitar mensagens DEBUG."""
        with caplog.at_level(logging.DEBUG, logger="codetwin_analyzer"):
            cli = CodeTwinCLI(verbose=True)

        # O logger deve estar configurado em nível DEBUG
        import logging as _logging
        codetwin_logger = _logging.getLogger("codetwin_analyzer")
        assert codetwin_logger.level == _logging.DEBUG
