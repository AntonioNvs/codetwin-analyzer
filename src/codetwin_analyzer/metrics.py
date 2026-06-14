import re

from typing import List, Tuple
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

def compute_clone_counts(clone_pairs: List[ClonePair]) -> CloneMetrics:
    """
    Itera sobre os pares de clones, classifica cada um deles e 
    acumula as métricas gerais do repositório.
    """
    type1_count = 0
    type2_count = 0
    unique_files = set()
    total_lines_duplicated = 0
    
    for pair in clone_pairs:
        if not pair.type:
            classify_clone_type(pair)
            
        if pair.type == "Tipo 1":
            type1_count += 1
        elif pair.type == "Tipo 2":
            type2_count += 1
            
        unique_files.add(pair.fragment_a.source_file)
        unique_files.add(pair.fragment_b.source_file)
        
        # Calcula a quantidade de linhas duplicadas no par
        # O +1 garante que contar da linha 10 à 15 resulte em 6 linhas (10,11,12,13,14,15)
        lines_a = (pair.fragment_a.end_line - pair.fragment_a.begin_line) + 1
        lines_b = (pair.fragment_b.end_line - pair.fragment_b.begin_line) + 1
        
        # Acumula o total (soma o tamanho do trecho A e do trecho B)
        total_lines_duplicated += (lines_a + lines_b)
        
    return CloneMetrics(
        total_clones=len(clone_pairs),
        type1_count=type1_count,
        type2_count=type2_count,
        total_files_affected=len(unique_files),
        total_lines_duplicated=total_lines_duplicated
    )

def most_cloned_files(clone_pairs: List[ClonePair], top_n: int = 10) -> List[Tuple[str, int]]:
    """
    Conta a frequência de aparição de cada arquivo nos pares de clones
    e retorna os Top N arquivos mais clonados.
    """
    file_counter = Counter()
    
    for pair in clone_pairs:
        file_counter[pair.fragment_a.source_file] += 1
        file_counter[pair.fragment_b.source_file] += 1
        
    return file_counter.most_common(top_n)

def most_cloned_functions(clone_pairs: List[ClonePair], top_n: int = 10) -> List[Tuple[str, int]]:
    """
    Busca assinaturas de funções (Python, JS, TS, PHP, etc.) dentro dos
    snippets clonados usando Regex e retorna as Top N funções mais clonadas.
    """
    function_counter = Counter()
    
    # Regex que captura: 'def nome_funcao' (ex: Python) ou 'function nome_funcao' (ex: JS)
    func_pattern = re.compile(r"def\s+(\w+)|function\s+(\w+)")
    
    for pair in clone_pairs:
        for fragment in (pair.fragment_a, pair.fragment_b):
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
        
    duplicated_lines = 0
    for pair in clone_pairs:
        lines_a = (pair.fragment_a.end_line - pair.fragment_a.begin_line) + 1
        lines_b = (pair.fragment_b.end_line - pair.fragment_b.begin_line) + 1
        duplicated_lines += (lines_a + lines_b)
        
    return duplicated_lines / total_lines