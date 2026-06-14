import os

from pathlib import Path
from codetwin_analyzer.utils import (
    sanitize_repo_name,
    ensure_dir,
    temp_dir,
    find_files,
)

class TestUtils:
    def test_sanitize_repo_name_https(self):
        """Testa se a extração funciona com URLs HTTPS padrão do GitHub."""
        url = "https://github.com/owner/repo"
        assert sanitize_repo_name(url) == "owner/repo"

    def test_sanitize_repo_name_git_suffix(self):
        """Testa se o sufixo .git é removido corretamente da URL ou caminho."""
        url = "git@github.com:owner/repo.git"
        assert sanitize_repo_name(url) == "owner/repo"
        
        plain_path = "owner/repo.git"
        assert sanitize_repo_name(plain_path) == "owner/repo"

    def test_ensure_dir_creates_nested(self, tmp_path):
        """Testa se diretórios aninhados (nested) são criados recursivamente."""
        nested_dir = tmp_path / "subdir_a" / "subdir_b" / "subdir_c"
        
        assert not nested_dir.exists()
        
        ensure_dir(nested_dir)
        
        assert nested_dir.exists()
        assert nested_dir.is_dir()

    def test_find_files_filters_by_extension(self, tmp_path):
        """Testa se a busca de arquivos filtra corretamente pelas extensões fornecidas."""
        (tmp_path / "main.py").write_text("print('hello')", encoding="utf-8")
        (tmp_path / "utils.py").write_text("# utilidades", encoding="utf-8")
        (tmp_path / "readme.txt").write_text("doc", encoding="utf-8")
        
        sub_folder = tmp_path / "core"
        sub_folder.mkdir()
        (sub_folder / "engine.py").write_text("pass", encoding="utf-8")
        (sub_folder / "config.json").write_text("{}", encoding="utf-8")

        py_files = find_files(tmp_path, extensions=["py"])
        
        py_file_names = [f.name for f in py_files]
        
        assert len(py_file_names) == 3
        assert "main.py" in py_file_names
        assert "utils.py" in py_file_names
        assert "engine.py" in py_file_names
        assert "readme.txt" not in py_file_names
        assert "config.json" not in py_file_names

    def test_find_files_empty_dir(self, tmp_path):
        """Testa se buscar arquivos em um diretório vazio retorna uma lista vazia."""
        files = find_files(tmp_path, extensions=["py", "txt"])
        assert files == []

    def test_temp_dir_cleanup(self):
        """Testa se o diretório temporário é excluído após fechar o context manager."""
        stored_path = None
        
        with temp_dir() as tmpdirname:
            stored_path = Path(tmpdirname)
            assert stored_path.exists()
            assert stored_path.is_dir()
            
        assert not stored_path.exists()