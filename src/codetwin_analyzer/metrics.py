from dataclasses import dataclass
from typing import List

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