import re
import tempfile

from pathlib import Path
from contextlib import contextmanager
from typing import Generator, List, Union

def sanitize_repo_name(url: str) -> str:
    """
    Extrai o padrão 'owner/repo' de uma URL do GitHub.
    Lida com prefixos 'https://' ou 'git@' e sufixos '.git'.
    """

    match = re.search(r'(?:https?://github\.com/|git@github\.com:)?([^/]+)/([^/]+?)(?:\.git)?/?$', url.strip())

    if match:
        return f"{match.group(1)}/{match.group(2)}"
    
    return url

def ensure_dir(path: Union[str, Path]) -> None:
    """
    Cria diretórios recursivamente.
    Equivalente ao 'mkdir -p' no terminal.
    """
    Path(path).mkdir(parents=True, exist_ok=True)

@contextmanager
def temp_dir() -> Generator[str, None, None]:
    """
    Context manager que cria um diretório temporário e o deleta
    auitomaticamente após o uso.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir

def find_files(directory: Union[str, Path], extensions: List[str]) -> List[Path]:
    """
    Varre um diretório recursivamente e retorna uma lista de caminhos
    de arquivos filtrados pelas extensões fornecidas.
    """
    directory = Path(directory)
    found_files = []

    normalized_exts = [ext if ext.startswith('.') else f'.{ext}' for ext in extensions]

    for path in directory.rglob("*"):
        if path.is_file() and path.suffix in normalized_exts:
            found_files.append(path)

    return found_files