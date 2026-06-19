import pytest

from pathlib import Path
from unittest.mock import MagicMock, patch
from codetwin_analyzer.cpd_runner import CPDRunner, CPDExecutionError

pytestmark = pytest.mark.unit


class TestCPDRunner:
    """Testes unitários para a classe CPDRunner."""

    def test_run_cpd_success(self, tmp_path: Path) -> None:
        """run_cpd não levanta exceção quando subprocess retorna exit code 0."""
        output_file = tmp_path / "output.xml"

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stderr = ""

        with patch("subprocess.run", return_value=mock_result):
            runner = CPDRunner(pmd_path="/fake/pmd")
            runner.run_cpd(source_dir=tmp_path, output_file=output_file)

    def test_run_cpd_failure_raises_error(self, tmp_path: Path) -> None:
        """run_cpd levanta CPDExecutionError quando subprocess retorna exit code != 0 e != 4."""
        output_file = tmp_path / "output.xml"

        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stderr = "Something went wrong"

        with patch("subprocess.run", return_value=mock_result):
            runner = CPDRunner(pmd_path="/fake/pmd")
            with pytest.raises(CPDExecutionError) as exc_info:
                runner.run_cpd(source_dir=tmp_path, output_file=output_file)

        assert "1" in str(exc_info.value)

    def test_detect_language_python(self, tmp_path: Path) -> None:
        """detect_language retorna 'python' quando o diretório contém majoritariamente .py."""
        (tmp_path / "main.py").write_text("print('hello')")
        (tmp_path / "utils.py").write_text("def foo(): pass")
        (tmp_path / "notes.txt").write_text("some notes")

        runner = CPDRunner(pmd_path="/fake/pmd")
        assert runner.detect_language(tmp_path) == "python"

    def test_detect_language_mixed(self, tmp_path: Path) -> None:
        """detect_language retorna 'java' quando a maioria dos arquivos é .java."""
        for i in range(3):
            (tmp_path / f"Class{i}.java").write_text("public class Foo {}")
        (tmp_path / "script.py").write_text("pass")

        runner = CPDRunner(pmd_path="/fake/pmd")
        assert runner.detect_language(tmp_path) == "java"

    def test_pmd_not_installed(self) -> None:
        """Quando 'pmd' não está no PATH e nenhum caminho é fornecido, levanta FileNotFoundError."""
        with patch("shutil.which", return_value=None):
            with pytest.raises(FileNotFoundError) as exc_info:
                CPDRunner()

        assert "pmd" in str(exc_info.value).lower()

    def test_run_with_auto_detect_chains_correctly(self, tmp_path: Path) -> None:
        """run_with_auto_detect detecta a linguagem e repassa para run_cpd corretamente."""
        (tmp_path / "app.py").write_text("x = 1")
        output_file = tmp_path / "result.xml"

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stderr = ""

        with patch("subprocess.run", return_value=mock_result) as mock_run:
            runner = CPDRunner(pmd_path="/fake/pmd")
            runner.run_with_auto_detect(source_dir=tmp_path, output_file=output_file)

        call_args = mock_run.call_args[0][0]
        assert "--language" in call_args
        lang_idx = call_args.index("--language")
        assert call_args[lang_idx + 1] == "python"

    def test_detect_language_java(self, tmp_path: Path) -> None:
        """detect_language retorna 'java' quando arquivos .java predominam."""
        (tmp_path / "App.java").write_text("class App {}")
        
        runner = CPDRunner(pmd_path="/fake/pmd")
        assert runner.detect_language(tmp_path) == "java"

    def test_detect_language_javascript(self, tmp_path: Path) -> None:
        """detect_language retorna 'javascript' quando arquivos .js predominam."""
        (tmp_path / "script.js").write_text("console.log('test');")
        
        runner = CPDRunner(pmd_path="/fake/pmd")
        assert runner.detect_language(tmp_path) == "javascript"

    def test_detect_language_cpp(self, tmp_path: Path) -> None:
        """detect_language retorna 'cpp' quando arquivos .cpp ou .c++ predominam."""
        (tmp_path / "main.cpp").write_text("int main() {}")
        (tmp_path / "utils.c++").write_text("void utils() {}")
        
        runner = CPDRunner(pmd_path="/fake/pmd")
        assert runner.detect_language(tmp_path) == "cpp"

    def test_detect_language_go(self, tmp_path: Path) -> None:
        """detect_language retorna 'go' quando arquivos .go predominam."""
        (tmp_path / "main.go").write_text("package main")
        
        runner = CPDRunner(pmd_path="/fake/pmd")
        assert runner.detect_language(tmp_path) == "go"

    def test_detect_language_unknown(self, tmp_path: Path) -> None:
        """run_with_auto_detect levanta ValueError quando não detecta linguagem."""
        (tmp_path / "unknown.xyz").write_text("data")
        
        runner = CPDRunner(pmd_path="/fake/pmd")
        assert runner.detect_language(tmp_path) is None

        with pytest.raises(ValueError) as exc_info:
            runner.run_with_auto_detect(tmp_path, tmp_path / "out.xml")
            
        assert "Não foi possível detectar" in str(exc_info.value)
