import re
import xml.etree.ElementTree as ET

from pathlib import Path
from dataclasses import dataclass
from itertools import combinations
from collections import defaultdict
from typing import List, Union, Optional

@dataclass
class CloneFragment:
    """Representa um trecho de código que foi identificado como clone."""
    source_file: str
    begin_line: int
    end_line: int
    tokens: int
    code_snippet: str

@dataclass
class ClonePair:
    """Representa um par de fragmentos de código clonados."""
    fragment_a: CloneFragment
    fragment_b: CloneFragment
    shared_tokens: int
    type: Optional[str] = None


def parse_cpd_xml(file_path: Union[str, Path]) -> List[CloneFragment]:
    """
    Lê o arquivo XML gerado pelo PMD CPD, extrai os elementos <duplication>
    e retorna uma lista achatada de CloneFragments.
    """
    fragments = []
    
    tree = ET.parse(file_path)
    root = tree.getroot()
    
    for duplication in root.findall("duplication"):
        tokens = int(duplication.get("tokens", 0))
        
        codefragment_node = duplication.find("codefragment")
        code_snippet = ""
        if codefragment_node is not None and codefragment_node.text:
            code_snippet = codefragment_node.text.strip()
            
        for file_node in duplication.findall("file"):
            source_file = file_node.get("path", "")
            begin_line = int(file_node.get("line", 0))
            
            end_line_str = file_node.get("endline")
            if end_line_str:
                end_line = int(end_line_str)
            else:
                lines = int(duplication.get("lines", 0))
                end_line = begin_line + lines - 1 if lines > 0 else begin_line
            
            fragments.append(
                CloneFragment(
                    source_file=source_file,
                    begin_line=begin_line,
                    end_line=end_line,
                    tokens=tokens,
                    code_snippet=code_snippet
                )
            )
            
    return fragments


def group_into_pairs(fragments: List[CloneFragment]) -> List[ClonePair]:
    """
    Recebe a lista achatada de fragmentos e os agrupa em pares (ClonePair).
    Usa a combinação de (tokens, code_snippet) para identificar quais
    fragmentos pertencem ao mesmo grupo de duplicação do XML.
    """
    groups = defaultdict(list)
    for frag in fragments:
        groups[(frag.tokens, frag.code_snippet)].append(frag)
        
    pairs = []
    for group in groups.values():
        for frag_a, frag_b in combinations(group, 2):
            pairs.append(
                ClonePair(
                    fragment_a=frag_a,
                    fragment_b=frag_b,
                    shared_tokens=frag_a.tokens
                )
            )
            
    return pairs


def classify_clone_type(pair: ClonePair) -> None:
    """
    Analisa os snippets de um par e classifica o clone:
    - Tipo 1: Código exato (ignorando espaços/quebras de linha).
    - Tipo 2: Estrutura idêntica, mas variáveis/literais diferentes.
    """
    code_a = pair.fragment_a.code_snippet
    code_b = pair.fragment_b.code_snippet
    
    if not code_a or not code_b:
        pair.type = "Desconhecido"
        return

    if code_a.strip() == code_b.strip():
        pair.type = "Tipo 1"
        return

    def normalize_code(code: str) -> str:
        code = re.sub(r'".*?"|\'.*?\'', '<STR>', code)
        code = re.sub(r'\b\d+\b', '<NUM>', code)
        code = re.sub(r'\b[a-zA-Z_]\w*\b', '<ID>', code)
        return re.sub(r'\s+', '', code)

    norm_a = normalize_code(code_a)
    norm_b = normalize_code(code_b)
    
    if norm_a == norm_b:
        pair.type = "Tipo 2"
    else:
        pair.type = "Tipo 3/4"