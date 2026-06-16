import re
import statistics

from typing import List, Tuple, Dict, Any
from collections import Counter
from dataclasses import dataclass

from src.codetwin_analyzer.parser import ClonePair, classify_clone_type


@dataclass
class CloneMetrics:
    """Armazena as estatísticas e métricas gerais dos clones detectados."""
    total_clones: int
    type1_count: int
    type2_count: int
    total_files_affected: int
    total_lines_duplicated: int


def _unique_fragment_lines(clone_pairs: List[ClonePair]) -> int:
    """Soma as linhas dos fragmentos únicos para evitar double-counting
    quando um mesmo fragmento aparece em múltiplos pares (grupos com N > 2)."""
    seen = set()
    total = 0
    for pair in clone_pairs:
        for frag in (pair.fragment_a, pair.fragment_b):
            key = (frag.source_file, frag.begin_line, frag.end_line)
            if key not in seen:
                seen.add(key)
                total += (frag.end_line - frag.begin_line) + 1
    return total


def compute_clone_counts(clone_pairs: List[ClonePair]) -> CloneMetrics:
    """
    Itera sobre os pares de clones, classifica cada um deles e
    acumula as métricas gerais do repositório.
    """
    type1_count = 0
    type2_count = 0
    unique_files = set()

    for pair in clone_pairs:
        if not pair.type:
            classify_clone_type(pair)

        if pair.type == "Tipo 1":
            type1_count += 1
        elif pair.type == "Tipo 2":
            type2_count += 1

        unique_files.add(pair.fragment_a.source_file)
        unique_files.add(pair.fragment_b.source_file)

    total_lines_duplicated = _unique_fragment_lines(clone_pairs)

    return CloneMetrics(
        total_clones=len(clone_pairs),
        type1_count=type1_count,
        type2_count=type2_count,
        total_files_affected=len(unique_files),
        total_lines_duplicated=total_lines_duplicated,
    )


def most_cloned_files(clone_pairs: List[ClonePair], top_n: int = 10) -> List[Tuple[str, int]]:
    """
    Conta quantos blocos clonados únicos cada arquivo possui.
    Deduplica por (source_file, begin_line, end_line) para evitar
    inflação quando um fragmento aparece em múltiplos pares do mesmo grupo.
    """
    file_counter = Counter()
    seen = set()

    for pair in clone_pairs:
        for frag in (pair.fragment_a, pair.fragment_b):
            key = (frag.source_file, frag.begin_line, frag.end_line)
            if key not in seen:
                seen.add(key)
                file_counter[frag.source_file] += 1

    return file_counter.most_common(top_n)


def most_cloned_functions(clone_pairs: List[ClonePair], top_n: int = 10) -> List[Tuple[str, int]]:
    """
    Busca assinaturas de funções (Python, JS, TS, PHP, etc.) dentro dos
    snippets clonados usando Regex e retorna as Top N funções mais clonadas.
    Deduplica fragmentos por (source_file, begin_line, end_line).
    """
    function_counter = Counter()
    func_pattern = re.compile(r"def\s+(\w+)|function\s+(\w+)")
    seen_frags = set()

    for pair in clone_pairs:
        for fragment in (pair.fragment_a, pair.fragment_b):
            frag_key = (fragment.source_file, fragment.begin_line, fragment.end_line)
            if frag_key in seen_frags:
                continue
            seen_frags.add(frag_key)

            match = func_pattern.search(fragment.code_snippet)
            if match:
                func_name = match.group(1) or match.group(2)
                if func_name:
                    function_counter[func_name] += 1

    return function_counter.most_common(top_n)


def clone_density(clone_pairs: List[ClonePair], total_lines: int) -> float:
    """
    Calcula a razão (densidade) entre as linhas duplicadas e o total
    de linhas do repositório/projeto analisado.
    """
    if total_lines <= 0:
        return 0.0

    duplicated_lines = _unique_fragment_lines(clone_pairs)
    return duplicated_lines / total_lines


def statistical_summary(clone_pairs: List[ClonePair]) -> Dict[str, Any]:
    """
    Calcula estatísticas descritivas dos tamanhos (em linhas) dos clones detectados.
    Retorna um dicionário com média, mediana, desvio padrão, mínimo, máximo,
    total de arquivos únicos e razões por tipo.
    Trata lista vazia retornando zeros em todos os campos numéricos.
    """
    _EMPTY: Dict[str, Any] = {
        "mean_clone_size": 0.0,
        "median_clone_size": 0.0,
        "stddev_clone_size": 0.0,
        "min_clone_size": 0,
        "max_clone_size": 0,
        "total_unique_files": 0,
        "type1_ratio": 0.0,
        "type2_ratio": 0.0,
    }

    if not clone_pairs:
        return _EMPTY

    sizes: List[int] = []
    unique_files: set = set()
    type1_count = 0
    type2_count = 0

    for pair in clone_pairs:
        for frag in (pair.fragment_a, pair.fragment_b):
            sizes.append((frag.end_line - frag.begin_line) + 1)
            unique_files.add(frag.source_file)

        clone_type = pair.type or ""
        if clone_type == "Tipo 1":
            type1_count += 1
        elif clone_type == "Tipo 2":
            type2_count += 1

    total = len(clone_pairs)
    stddev = statistics.stdev(sizes) if len(sizes) > 1 else 0.0

    return {
        "mean_clone_size": statistics.mean(sizes),
        "median_clone_size": statistics.median(sizes),
        "stddev_clone_size": stddev,
        "min_clone_size": min(sizes),
        "max_clone_size": max(sizes),
        "total_unique_files": len(unique_files),
        "type1_ratio": type1_count / total,
        "type2_ratio": type2_count / total,
    }


def inter_file_similarity(clone_pairs: List[ClonePair]) -> Dict[str, Dict[str, float]]:
    """
    Calcula um score de similaridade entre pares de arquivos.
    Para cada par (A, B): score = (2 * linhas_duplicadas_AB) / (total_linhas_A + total_linhas_B).
    Retorna nested dict: {arquivo_a: {arquivo_b: score}}.
    """
    shared: Dict[tuple, int] = {}
    totals: Dict[str, int] = {}

    for pair in clone_pairs:
        fa, fb = pair.fragment_a, pair.fragment_b
        lines_a = (fa.end_line - fa.begin_line) + 1
        lines_b = (fb.end_line - fb.begin_line) + 1

        key = (fa.source_file, fb.source_file)
        shared[key] = shared.get(key, 0) + lines_a + lines_b
        totals[fa.source_file] = totals.get(fa.source_file, 0) + lines_a
        totals[fb.source_file] = totals.get(fb.source_file, 0) + lines_b

    result: Dict[str, Dict[str, float]] = {}
    for (file_a, file_b), dup_lines in shared.items():
        denom = totals.get(file_a, 0) + totals.get(file_b, 0)
        score = dup_lines / denom if denom > 0 else 0.0
        result.setdefault(file_a, {})[file_b] = score
        result.setdefault(file_b, {})[file_a] = score

    return result


def token_overlap_matrix(clone_pairs: List[ClonePair]) -> Dict[str, Dict[str, float]]:
    """
    Calcula a similaridade de Jaccard entre os conjuntos de tokens de cada par de arquivos.
    Jaccard(A, B) = |A ∩ B| / |A ∪ B|.
    Os tokens são extraídos dos code_snippets de cada fragmento.
    Retorna nested dict: {arquivo_a: {arquivo_b: jaccard}}.
    """
    file_tokens: Dict[str, set] = {}

    for pair in clone_pairs:
        for frag in (pair.fragment_a, pair.fragment_b):
            tokens = set(frag.code_snippet.split())
            file_tokens.setdefault(frag.source_file, set()).update(tokens)

    result: Dict[str, Dict[str, float]] = {}
    files = list(file_tokens.keys())

    for i, file_a in enumerate(files):
        for file_b in files[i + 1:]:
            set_a = file_tokens[file_a]
            set_b = file_tokens[file_b]
            union = set_a | set_b
            jaccard = len(set_a & set_b) / len(union) if union else 0.0
            result.setdefault(file_a, {})[file_b] = jaccard
            result.setdefault(file_b, {})[file_a] = jaccard

    return result


def repository_clone_index(
    clone_pairs: List[ClonePair],
    total_files: int,
    total_lines: int,
) -> float:
    """
    Calcula um índice único (0 a 1) que representa o grau geral de clonagem do repositório.
    Combina a densidade de linhas duplicadas com a proporção de arquivos afetados.
    Retorna 0.0 se não houver clones ou os totais forem inválidos.
    """
    if not clone_pairs or total_files <= 0 or total_lines <= 0:
        return 0.0

    line_density = _unique_fragment_lines(clone_pairs) / total_lines

    unique_files: set = set()
    for pair in clone_pairs:
        unique_files.add(pair.fragment_a.source_file)
        unique_files.add(pair.fragment_b.source_file)
    file_ratio = len(unique_files) / total_files

    return (line_density + file_ratio) / 2.0


def file_level_clone_matrix(clone_pairs: List[ClonePair]) -> Dict[str, Dict[str, int]]:
    """
    Constrói uma matriz NxN (nested dict) com o número de pares clonados entre cada par de arquivos.
    Retorna {arquivo_a: {arquivo_b: contagem}} (simétrico).
    """
    matrix: Dict[str, Dict[str, int]] = {}

    for pair in clone_pairs:
        file_a = pair.fragment_a.source_file
        file_b = pair.fragment_b.source_file

        matrix.setdefault(file_a, {})
        matrix.setdefault(file_b, {})
        matrix[file_a][file_b] = matrix[file_a].get(file_b, 0) + 1
        matrix[file_b][file_a] = matrix[file_b].get(file_a, 0) + 1

    return matrix


def clone_coverage_per_file(clone_pairs: List[ClonePair]) -> Dict[str, float]:
    """
    Calcula a porcentagem de linhas duplicadas por arquivo.
    Usa o maior end_line observado como proxy do tamanho do arquivo.
    Retorna {arquivo: percentual (0.0 a 100.0)}.
    """
    duplicated: Dict[str, set] = {}
    file_max_line: Dict[str, int] = {}

    for pair in clone_pairs:
        for frag in (pair.fragment_a, pair.fragment_b):
            f = frag.source_file
            dup_lines = set(range(frag.begin_line, frag.end_line + 1))
            duplicated.setdefault(f, set()).update(dup_lines)
            file_max_line[f] = max(file_max_line.get(f, 0), frag.end_line)

    result: Dict[str, float] = {}
    for f, dup_lines in duplicated.items():
        total = file_max_line.get(f, 1)
        result[f] = (len(dup_lines) / total) * 100.0

    return result


def top_clone_files_by_type(
    clone_pairs: List[ClonePair],
    top_n: int = 10,
) -> Dict[str, List[Tuple[str, int]]]:
    """
    Retorna rankings separados dos arquivos mais clonados para Tipo 1 e Tipo 2.
    Retorna {\"Tipo 1\": [(arquivo, contagem), ...], \"Tipo 2\": [(arquivo, contagem), ...]}.
    """
    counters: Dict[str, Counter] = {"Tipo 1": Counter(), "Tipo 2": Counter()}

    for pair in clone_pairs:
        clone_type = pair.type or ""
        if clone_type in counters:
            counters[clone_type][pair.fragment_a.source_file] += 1
            counters[clone_type][pair.fragment_b.source_file] += 1

    return {
        "Tipo 1": counters["Tipo 1"].most_common(top_n),
        "Tipo 2": counters["Tipo 2"].most_common(top_n),
    }
