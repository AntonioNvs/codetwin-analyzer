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