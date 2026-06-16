import pytest

from pathlib import Path
from codetwin_analyzer.parser import CloneFragment, ClonePair
from codetwin_analyzer.metrics import (
    CloneMetrics,
    compute_clone_counts,
    most_cloned_files,
    most_cloned_functions,
    clone_density,
)


def _make_pair(
    tmp_path: Path,
    code_a: str,
    code_b: str,
    filename_a: str = "file_a.py",
    filename_b: str = "file_b.py",
    begin: int = 1,
) -> ClonePair:
    """Helper: escreve dois arquivos em tmp_path e monta um ClonePair apontando para eles."""
    path_a = tmp_path / filename_a
    path_b = tmp_path / filename_b
    path_a.write_text(code_a, encoding="utf-8")
    path_b.write_text(code_b, encoding="utf-8")

    lines_a = code_a.count("\n") + 1
    lines_b = code_b.count("\n") + 1

    frag_a = CloneFragment(
        source_file=str(path_a),
        begin_line=begin,
        end_line=begin + lines_a - 1,
        tokens=100,
        code_snippet=code_a,
    )
    frag_b = CloneFragment(
        source_file=str(path_b),
        begin_line=begin,
        end_line=begin + lines_b - 1,
        tokens=100,
        code_snippet=code_b,
    )
    return ClonePair(fragment_a=frag_a, fragment_b=frag_b, shared_tokens=100)


class TestMetrics:
    """Testes completos para o módulo metrics."""

    def test_compute_clone_counts_type1_only(self, tmp_path: Path) -> None:
        """Dois fragmentos com código idêntico → type1_count=1, type2_count=0."""
        code = "def hello():\n    return 42\n"
        pair = _make_pair(tmp_path, code, code)

        result = compute_clone_counts([pair])

        assert isinstance(result, CloneMetrics)
        assert result.total_clones == 1
        assert result.type1_count == 1
        assert result.type2_count == 0

    def test_compute_clone_counts_type2_only(self, tmp_path: Path) -> None:
        """Fragmentos com estrutura igual mas nomes diferentes → type2_count=1."""
        code_a = "def foo(x, y):\n    return x + y\n"
        code_b = "def bar(a, b):\n    return a + b\n"
        pair = _make_pair(tmp_path, code_a, code_b)

        result = compute_clone_counts([pair])

        assert result.total_clones == 1
        assert result.type1_count == 0
        assert result.type2_count == 1

    def test_compute_clone_counts_mixed(self, tmp_path: Path) -> None:
        """Mix de Tipo 1 e Tipo 2 é acumulado corretamente."""
        code_same = "x = 1\ny = 2\n"
        code_a2 = "def calc(n):\n    return n * 2\n"
        code_b2 = "def compute(m):\n    return m * 2\n"

        pair1 = _make_pair(tmp_path, code_same, code_same, "same_a.py", "same_b.py")
        pair2 = _make_pair(tmp_path, code_a2, code_b2, "calc_a.py", "calc_b.py")

        result = compute_clone_counts([pair1, pair2])

        assert result.total_clones == 2
        assert result.type1_count == 1
        assert result.type2_count == 1

    def test_most_cloned_files_ordering(self, tmp_path: Path) -> None:
        """O arquivo que aparece mais vezes deve aparecer primeiro no ranking."""
        hot_file = tmp_path / "hot.py"
        hot_file.write_text("x = 1\n")
        cold_file = tmp_path / "cold.py"
        cold_file.write_text("y = 2\n")
        other_file = tmp_path / "other.py"
        other_file.write_text("z = 3\n")

        def _frag(path: Path, begin: int) -> CloneFragment:
            return CloneFragment(
                source_file=str(path), begin_line=begin, end_line=begin,
                tokens=50, code_snippet="x = 1",
            )

        pairs = [
            ClonePair(fragment_a=_frag(hot_file, 1), fragment_b=_frag(cold_file, 1), shared_tokens=50),
            ClonePair(fragment_a=_frag(hot_file, 2), fragment_b=_frag(other_file, 1), shared_tokens=50),
        ]

        result = most_cloned_files(pairs, top_n=3)
        files_ordered = [name for name, _ in result]

        assert files_ordered[0] == str(hot_file)

    def test_most_cloned_functions(self, tmp_path: Path) -> None:
        """Nomes de funções Python e JS são extraídos dos snippets corretamente."""
        pairs = [
            ClonePair(
                fragment_a=CloneFragment("a.py", 1, 3, 50, "def process(data):\n    return data"),
                fragment_b=CloneFragment("b.py", 1, 3, 50, "def process(d):\n    return d"),
                shared_tokens=50,
            ),
            ClonePair(
                fragment_a=CloneFragment("c.js", 1, 2, 40, "function render() { return null; }"),
                fragment_b=CloneFragment("d.js", 1, 2, 40, "function render() { return ''; }"),
                shared_tokens=40,
            ),
        ]

        result = most_cloned_functions(pairs, top_n=5)
        func_names = [name for name, _ in result]

        assert "process" in func_names
        assert "render" in func_names

    def test_clone_density(self, tmp_path: Path) -> None:
        """clone_density calcula corretamente a razão linhas_duplicadas / total."""
        code = "line1\nline2\nline3\nline4\nline5\n"  # count("\n")+1 = 6 linhas por fragmento
        pair = _make_pair(tmp_path, code, code)

        # frag_a e frag_b são fragmentos distintos: 6 + 6 = 12 linhas duplicadas
        density = clone_density([pair], total_lines=100)

        assert abs(density - 0.12) < 1e-9

    def test_clone_density_zero_total_lines(self) -> None:
        """clone_density retorna 0.0 quando total_lines <= 0."""
        assert clone_density([], total_lines=0) == 0.0
        assert clone_density([], total_lines=-5) == 0.0

    def test_empty_input_handling(self) -> None:
        """Funções de métricas não quebram com lista vazia."""
        result = compute_clone_counts([])

        assert result.total_clones == 0
        assert result.type1_count == 0
        assert result.type2_count == 0
        assert result.total_files_affected == 0
        assert result.total_lines_duplicated == 0

        assert most_cloned_files([]) == []
        assert most_cloned_functions([]) == []
        assert clone_density([], total_lines=1000) == 0.0
