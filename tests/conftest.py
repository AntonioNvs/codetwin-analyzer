import pytest

from unittest.mock import MagicMock
from codetwin_analyzer.parser import CloneFragment, ClonePair

@pytest.fixture
def sample_cpd_xml(tmp_path):
    """
    Cria um arquivo XML válido do PMD CPD temporário contendo 3 duplicações.
    O pytest limpa o diretório 'tmp_path' automaticamente após a execução dos testes.
    """
    xml_content = """<?xml version="1.0" encoding="UTF-8"?>
<pmd-cpd>
    <duplication lines="10" tokens="120">
        <file line="5" path="/src/app/main.py" endline="14"/>
        <file line="15" path="/src/app/backup.py" endline="24"/>
        <codefragment><![CDATA[def hello_world():
    print("Hello")
    return True]]></codefragment>
    </duplication>
    
    <duplication lines="15" tokens="150">
        <file line="20" path="/src/utils/math.py" endline="34"/>
        <file line="50" path="/src/utils/calc.py" endline="64"/>
        <codefragment><![CDATA[def add(a, b):
    return a + b]]></codefragment>
    </duplication>
    
    <duplication lines="8" tokens="110">
        <file line="10" path="/src/core/engine.py" endline="17"/>
        <file line="30" path="/src/core/engine_v2.py" endline="37"/>
        <codefragment><![CDATA[def process(data):
    x = data * 2
    return x]]></codefragment>
    </duplication>
</pmd-cpd>
"""
    xml_file = tmp_path / "sample_cpd.xml"
    xml_file.write_text(xml_content, encoding="utf-8")
    return xml_file


@pytest.fixture
def sample_clone_fragments():
    """Retorna uma lista padronizada de fragmentos para testes unitários."""
    return [
        CloneFragment(
            source_file="auth.py", 
            begin_line=10, 
            end_line=20, 
            tokens=105, 
            code_snippet="def login(user, psw):\n    return verify(user, psw)"
        ),
        CloneFragment(
            source_file="auth_backup.py", 
            begin_line=15, 
            end_line=25, 
            tokens=105, 
            code_snippet="def login(user, psw):\n    return verify(user, psw)"
        ),
        CloneFragment(
            source_file="auth_v2.py", 
            begin_line=5, 
            end_line=15, 
            tokens=105, 
            code_snippet="def login(u, p):\n    return verify(u, p)"
        )
    ]


@pytest.fixture
def sample_clone_pairs(sample_clone_fragments):
    """
    Retorna uma lista de ClonePairs pré-montada.
    Usa os fragmentos da fixture anterior para garantir consistência.
    """
    frag_a = sample_clone_fragments[0]
    frag_b = sample_clone_fragments[1]
    frag_c = sample_clone_fragments[2]
    
    return [
        # Par Tipo 1 (Snippets idênticos)
        ClonePair(
            fragment_a=frag_a,
            fragment_b=frag_b,
            shared_tokens=105,
            type="Tipo 1"
        ),
        # Par Tipo 2 (Snippets com estrutura igual, variáveis diferentes)
        ClonePair(
            fragment_a=frag_a,
            fragment_b=frag_c,
            shared_tokens=105,
            type="Tipo 2"
        )
    ]


@pytest.fixture
def mock_github_session(monkeypatch):
    """
    Realiza o monkeypatch no método get da sessão do requests.
    Retorna o mock para que cada teste possa alterar o status_code ou o json().
    """
    mock_get = MagicMock()
    
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"default_branch": "main"}
    
    mock_response.links = {}
    mock_response.text = "Mocked Response Body"
    
    mock_get.return_value = mock_response
    
    monkeypatch.setattr("requests.Session.get", mock_get)
    
    return mock_get