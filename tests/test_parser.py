import pytest
import xml.etree.ElementTree as ET

from codetwin_analyzer.parser import (
    parse_cpd_xml,
    group_into_pairs,
    classify_clone_type,
    ClonePair,
    CloneFragment
)

class TestParser:
    def test_parse_cpd_xml_valid(self, sample_cpd_xml):
        """
        Verifica se o parser lê o XML corretamente e extrai o número exato de fragmentos.
        O XML de exemplo possui 3 blocos <duplication>, cada um com 2 tags <file>,
        gerando um total de 6 fragmentos individuais.
        """
        fragments = parse_cpd_xml(sample_cpd_xml)
        
        assert isinstance(fragments, list)
        assert len(fragments) == 6
        
        first_frag = fragments[0]
        assert first_frag.source_file == "/src/app/main.py"
        assert first_frag.begin_line == 5
        assert first_frag.end_line == 14
        assert first_frag.tokens == 120
        assert "def hello_world():" in first_frag.code_snippet

    def test_parse_cpd_xml_empty(self, tmp_path):
        """Testa se um XML válido mas sem nenhuma duplicação retorna uma lista vazia."""
        empty_xml = tmp_path / "empty.xml"
        empty_xml.write_text("<pmd-cpd></pmd-cpd>", encoding="utf-8")
        
        fragments = parse_cpd_xml(empty_xml)
        assert fragments == []

    def test_parse_cpd_xml_malformed(self, tmp_path):
        """Testa se um XML malformado/corrompido levanta a exceção ParseError."""
        bad_xml = tmp_path / "bad.xml"
        bad_xml.write_text("<pmd-cpd><duplication>Tag nao fechada", encoding="utf-8")
        
        with pytest.raises(ET.ParseError):
            parse_cpd_xml(bad_xml)

    def test_classify_type1(self):
        """Testa se blocos de códigos idênticos são classificados como Tipo 1."""
        snippet = "def calculate_total(price):\n    return price * 1.1"
        
        frag_a = CloneFragment("file_a.py", 1, 2, 50, snippet)
        frag_b = CloneFragment("file_b.py", 10, 11, 50, snippet)
        
        pair = ClonePair(fragment_a=frag_a, fragment_b=frag_b, shared_tokens=50)
        
        classify_clone_type(pair)
        assert pair.type == "Tipo 1"

    def test_classify_type2_renamed_identifiers(self):
        """Testa se códigos com variáveis alteradas, mas estrutura idêntica, são Tipo 2."""
        snippet_a = "def save_user(username):\n    db.insert(username)\n    return 1"
        snippet_b = "def save_client(client_name):\n    db.insert(client_name)\n    return 2"
        
        frag_a = CloneFragment("file_a.py", 5, 7, 40, snippet_a)
        frag_b = CloneFragment("file_b.py", 20, 22, 40, snippet_b)
        
        pair = ClonePair(fragment_a=frag_a, fragment_b=frag_b, shared_tokens=40)
        
        classify_clone_type(pair)
        assert pair.type == "Tipo 2"

    def test_group_into_pairs(self, sample_clone_fragments):
        """
        Testa se o agrupamento em pares funciona. 
        Os dois primeiros fragmentos da fixture compartilham o mesmo snippet/tokens, 
        então devem formar exatamente 1 par.
        """
        target_fragments = [sample_clone_fragments[0], sample_clone_fragments[1]]
        
        pairs = group_into_pairs(target_fragments)
        
        assert len(pairs) == 1
        assert pairs[0].fragment_a.source_file == "auth.py"
        assert pairs[0].fragment_b.source_file == "auth_backup.py"
        assert pairs[0].shared_tokens == 105

    def test_type_statistics(self):
        """Verifica se a classificação diferencia um clone idêntico de um Tipo 3/4."""
        snippet_a = "x = 10\ny = 20\nreturn x + y"
        snippet_b = "x = 10\n# Comentario extra ou linha deletada\nreturn x + y"
        
        frag_a = CloneFragment("a.py", 1, 3, 30, snippet_a)
        frag_b = CloneFragment("b.py", 1, 3, 30, snippet_b)
        
        pair = ClonePair(fragment_a=frag_a, fragment_b=frag_b, shared_tokens=30)
        
        classify_clone_type(pair)
        assert pair.type == "Tipo 3/4"