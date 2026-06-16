import pytest

from pathlib import Path
from codetwin_analyzer.parser import CloneFragment, ClonePair
from codetwin_analyzer.metrics import (
    CloneMetrics,
    compute_clone_counts,
    most_cloned_files,
    most_cloned_functions,
    clone_density,
    statistical_summary,
    inter_file_similarity,
    token_overlap_matrix,
    repository_clone_index,
    file_level_clone_matrix,
    clone_coverage_per_file,
    top_clone_files_by_type,
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

    def test_statistical_summary(self) -> None:
        """statistical_summary retorna média, mediana e desvio corretos para múltiplos pares."""
        # Fragmentos com tamanhos: frag_a=5 linhas, frag_b=3 linhas (por par)
        pairs = [
            ClonePair(
                fragment_a=CloneFragment("a.py", 1, 5, 100, "code"),
                fragment_b=CloneFragment("b.py", 1, 3, 100, "code"),
                shared_tokens=100,
                type="Tipo 1",
            ),
            ClonePair(
                fragment_a=CloneFragment("c.py", 1, 5, 100, "code"),
                fragment_b=CloneFragment("d.py", 1, 3, 100, "code"),
                shared_tokens=100,
                type="Tipo 2",
            ),
        ]

        result = statistical_summary(pairs)

        # sizes = [5, 3, 5, 3] → mean=4.0, median=4.0
        assert result["mean_clone_size"] == 4.0
        assert result["median_clone_size"] == 4.0
        assert result["min_clone_size"] == 3
        assert result["max_clone_size"] == 5
        assert result["stddev_clone_size"] > 0
        assert result["total_unique_files"] == 4
        assert abs(result["type1_ratio"] - 0.5) < 1e-9
        assert abs(result["type2_ratio"] - 0.5) < 1e-9

    def test_statistical_summary_empty(self) -> None:
        """statistical_summary com lista vazia retorna zeros sem erro."""
        result = statistical_summary([])

        assert result["mean_clone_size"] == 0.0
        assert result["median_clone_size"] == 0.0
        assert result["stddev_clone_size"] == 0.0
        assert result["min_clone_size"] == 0
        assert result["max_clone_size"] == 0
        assert result["total_unique_files"] == 0
        assert result["type1_ratio"] == 0.0
        assert result["type2_ratio"] == 0.0

    def test_statistical_summary_single(self) -> None:
        """statistical_summary com um único par retorna estatísticas corretas sem erro de stdev."""
        pair = ClonePair(
            fragment_a=CloneFragment("x.py", 1, 10, 50, "code"),
            fragment_b=CloneFragment("y.py", 1, 10, 50, "code"),
            shared_tokens=50,
            type="Tipo 1",
        )

        result = statistical_summary([pair])

        assert result["mean_clone_size"] == 10.0
        assert result["min_clone_size"] == 10
        assert result["max_clone_size"] == 10
        assert result["stddev_clone_size"] == 0.0

    def test_inter_file_similarity(self) -> None:
        """inter_file_similarity retorna scores entre 0 e 1 para pares de arquivos."""
        pair = ClonePair(
            fragment_a=CloneFragment("alpha.py", 1, 10, 100, "code"),
            fragment_b=CloneFragment("beta.py", 1, 10, 100, "code"),
            shared_tokens=100,
        )

        result = inter_file_similarity([pair])

        assert "alpha.py" in result
        assert "beta.py" in result["alpha.py"]
        score = result["alpha.py"]["beta.py"]
        assert 0.0 <= score <= 1.0
        # score = (10+10)/(10+10) = 1.0
        assert abs(score - 1.0) < 1e-9

    def test_repository_clone_index(self) -> None:
        """repository_clone_index retorna valor entre 0 e 1 com fórmula correta."""
        pair = ClonePair(
            fragment_a=CloneFragment("a.py", 1, 10, 100, "code"),
            fragment_b=CloneFragment("b.py", 1, 10, 100, "code"),
            shared_tokens=100,
        )
        # linhas duplicadas = 10+10 = 20 → density = 20/200 = 0.1
        # arquivos únicos = 2 → file_ratio = 2/10 = 0.2
        # index = (0.1 + 0.2) / 2 = 0.15
        index = repository_clone_index([pair], total_files=10, total_lines=200)

        assert 0.0 <= index <= 1.0
        assert abs(index - 0.15) < 1e-9

    def test_token_overlap_matrix(self) -> None:
        """token_overlap_matrix retorna Jaccard correto entre snippets de arquivos."""
        pair = ClonePair(
            fragment_a=CloneFragment("p.py", 1, 2, 50, "def foo bar"),
            fragment_b=CloneFragment("q.py", 1, 2, 50, "def foo baz"),
            shared_tokens=50,
        )

        result = token_overlap_matrix([pair])

        # tokens p.py = {def, foo, bar}, q.py = {def, foo, baz}
        # intersecção = {def, foo} → |2|, união = {def, foo, bar, baz} → |4|
        # Jaccard = 2/4 = 0.5
        assert "p.py" in result
        assert "q.py" in result["p.py"]
        assert abs(result["p.py"]["q.py"] - 0.5) < 1e-9

    def test_file_level_clone_matrix(self) -> None:
        """file_level_clone_matrix constrói nested dict simétrico com contagens corretas."""
        pairs = [
            ClonePair(
                fragment_a=CloneFragment("a.py", 1, 5, 100, "code"),
                fragment_b=CloneFragment("b.py", 1, 5, 100, "code"),
                shared_tokens=100,
            ),
            ClonePair(
                fragment_a=CloneFragment("a.py", 10, 15, 100, "code"),
                fragment_b=CloneFragment("b.py", 10, 15, 100, "code"),
                shared_tokens=100,
            ),
        ]

        matrix = file_level_clone_matrix(pairs)

        assert "a.py" in matrix
        assert "b.py" in matrix
        assert matrix["a.py"]["b.py"] == 2
        assert matrix["b.py"]["a.py"] == 2

    def test_clone_coverage_per_file(self) -> None:
        """clone_coverage_per_file calcula porcentagem correta de linhas duplicadas."""
        # frag_a cobre linhas 1-5 num arquivo cujo max end_line é 5 → 100%
        # frag_b cobre linhas 1-5 num arquivo cujo max end_line é 10 → 50%
        pair = ClonePair(
            fragment_a=CloneFragment("full.py", 1, 5, 100, "code"),
            fragment_b=CloneFragment("half.py", 1, 5, 100, "code"),
            shared_tokens=100,
        )
        pair2 = ClonePair(
            fragment_a=CloneFragment("full.py", 1, 5, 100, "code"),
            fragment_b=CloneFragment("half.py", 6, 10, 100, "code"),
            shared_tokens=100,
        )

        result = clone_coverage_per_file([pair, pair2])

        assert abs(result["full.py"] - 100.0) < 1e-9
        assert abs(result["half.py"] - 100.0) < 1e-9

    def test_top_clone_files_by_type(self) -> None:
        """top_clone_files_by_type retorna rankings separados por Tipo 1 e Tipo 2."""
        pairs = [
            ClonePair(
                fragment_a=CloneFragment("a.py", 1, 5, 100, "code"),
                fragment_b=CloneFragment("b.py", 1, 5, 100, "code"),
                shared_tokens=100,
                type="Tipo 1",
            ),
            ClonePair(
                fragment_a=CloneFragment("a.py", 10, 15, 100, "code"),
                fragment_b=CloneFragment("c.py", 10, 15, 100, "code"),
                shared_tokens=100,
                type="Tipo 1",
            ),
            ClonePair(
                fragment_a=CloneFragment("d.py", 1, 5, 100, "code"),
                fragment_b=CloneFragment("e.py", 1, 5, 100, "code"),
                shared_tokens=100,
                type="Tipo 2",
            ),
        ]

        result = top_clone_files_by_type(pairs)

        type1_files = [name for name, _ in result["Tipo 1"]]
        type2_files = [name for name, _ in result["Tipo 2"]]

        # a.py aparece em 2 pares Tipo 1 → deve ser o primeiro
        assert type1_files[0] == "a.py"
        assert "d.py" in type2_files or "e.py" in type2_files
        # nenhum arquivo Tipo 2 deve aparecer no ranking Tipo 1
        assert "d.py" not in type1_files

    def test_clone_coverage_boundary(self) -> None:
        """clone_coverage_per_file retorna 0% para lista vazia e 100% para cobertura total."""
        assert clone_coverage_per_file([]) == {}

        pair = ClonePair(
            fragment_a=CloneFragment("x.py", 1, 1, 50, "x = 1"),
            fragment_b=CloneFragment("y.py", 1, 1, 50, "x = 1"),
            shared_tokens=50,
        )
        result = clone_coverage_per_file([pair])
        assert abs(result["x.py"] - 100.0) < 1e-9
        assert abs(result["y.py"] - 100.0) < 1e-9
