import xml.etree.ElementTree as ET

from pathlib import Path
from typing import List, Union
from dataclasses import dataclass

@dataclass
class CloneFragment:
    """Representa um trecho de código que foi identificado como clone."""
    source_file: str
    begin_line: int
    end_line: int
    tokens: int
    code_snippet: str


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