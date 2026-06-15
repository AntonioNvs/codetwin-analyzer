import pytest
import xml.etree.ElementTree as ET

from codetwin_analyzer.parser import (
    parse_cpd_xml,
    group_into_pairs,
    classify_clone_type,
    ClonePair,
    CloneFragment,
)


class TestParser:
    def test_parse_cpd_xml_valid(self, sample_cpd_xml):
        """Verifica se o parser lê o XML corretamente e extrai o número exato de fragmentos."""
        fragments = parse_cpd_xml(sample_cpd_xml)

        assert isinstance(fragments, list)
        assert len(fragments) == 6

        first_frag = fragments[0]
        assert first_frag.source_file == "/src/app/main.py"
        assert first_frag.begin_line == 5
        assert first_frag.end_line == 14
        assert first_frag.tokens == 120
        assert "def hello_world():" in first_frag.code_snippet

    def test_parse_cpd_xml_with_namespace(self, sample_cpd_xml_namespaced):
        """Verifica se o parser lida com o namespace padrão do PMD 7.x."""
        fragments = parse_cpd_xml(sample_cpd_xml_namespaced)

        assert len(fragments) == 4
        assert fragments[0].source_file == "/src/app/main.py"

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

    def test_classify_type1(self, tmp_path):
        """Testa se blocos de códigos idênticos (lidos do disco) são classificados como Tipo 1."""
        snippet = "def calculate_total(price):\n    return price * 1.1\n"

        file_a = tmp_path / "file_a.py"
        file_b = tmp_path / "file_b.py"
        file_a.write_text("import os\n" + snippet, encoding="utf-8")
        file_b.write_text("# comment\n" + snippet, encoding="utf-8")

        frag_a = CloneFragment(str(file_a), 2, 3, 50, snippet)
        frag_b = CloneFragment(str(file_b), 2, 3, 50, snippet)

        pair = ClonePair(fragment_a=frag_a, fragment_b=frag_b, shared_tokens=50)

        classify_clone_type(pair)
        assert pair.type == "Tipo 1"

    def test_classify_type2_renamed_identifiers(self, tmp_path):
        """Testa se códigos com variáveis alteradas, mas estrutura idêntica, são Tipo 2."""
        code_a = "def save_user(username):\n    db.insert(username)\n    return 1\n"
        code_b = "def save_client(client_name):\n    db.insert(client_name)\n    return 2\n"

        file_a = tmp_path / "file_a.py"
        file_b = tmp_path / "file_b.py"
        file_a.write_text(code_a, encoding="utf-8")
        file_b.write_text(code_b, encoding="utf-8")

        frag_a = CloneFragment(str(file_a), 1, 3, 40, code_a)
        frag_b = CloneFragment(str(file_b), 1, 3, 40, code_b)

        pair = ClonePair(fragment_a=frag_a, fragment_b=frag_b, shared_tokens=40)

        classify_clone_type(pair)
        assert pair.type == "Tipo 2"

    def test_classify_with_unreadable_file(self):
        """Verifica se clones com arquivos inacessíveis são marcados como Tipo 3/4."""
        snippet = "x = 10\ny = 20\n"
        frag_a = CloneFragment("/nonexistent/a.py", 1, 2, 30, snippet)
        frag_b = CloneFragment("/nonexistent/b.py", 1, 2, 30, snippet)

        pair = ClonePair(fragment_a=frag_a, fragment_b=frag_b, shared_tokens=30)

        classify_clone_type(pair)
        assert pair.type == "Tipo 3/4"

    def test_group_into_pairs(self, sample_clone_fragments):
        """Testa se o agrupamento em pares funciona por duplication_id."""
        target_fragments = [sample_clone_fragments[0], sample_clone_fragments[1]]

        pairs = group_into_pairs(target_fragments)

        assert len(pairs) == 1
        assert pairs[0].fragment_a.source_file == "auth.py"
        assert pairs[0].fragment_b.source_file == "auth_backup.py"
        assert pairs[0].shared_tokens == 105

    def test_group_into_pairs_respects_duplication_id(self, sample_clone_fragments):
        """Fragmentos com duplication_id diferente não devem formar pares entre si."""
        all_frags = sample_clone_fragments  # frags 0,1 id=0; frag 2 id=1

        pairs = group_into_pairs(all_frags)

        # Apenas 1 par: fragmentos 0+1 (id=0). Fragmento 2 (id=1) fica sozinho.
        assert len(pairs) == 1
        sources = {pairs[0].fragment_a.source_file, pairs[0].fragment_b.source_file}
        assert sources == {"auth.py", "auth_backup.py"}

    def test_type_statistics(self, tmp_path):
        """Verifica se a classificação diferencia um clone Tipo 3/4 (estrutura diferente)."""
        code_a = "x = 10\ny = 20\nreturn x + y\n"
        code_b = "x = 10\n# Comentario extra ou linha deletada\nreturn x + y\n"

        file_a = tmp_path / "a.py"
        file_b = tmp_path / "b.py"
        file_a.write_text(code_a, encoding="utf-8")
        file_b.write_text(code_b, encoding="utf-8")

        frag_a = CloneFragment(str(file_a), 1, 3, 30, code_a)
        frag_b = CloneFragment(str(file_b), 1, 3, 30, code_b)

        pair = ClonePair(fragment_a=frag_a, fragment_b=frag_b, shared_tokens=30)

        classify_clone_type(pair)
        assert pair.type == "Tipo 3/4"
