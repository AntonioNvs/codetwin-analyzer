import shutil
import subprocess

from pathlib import Path
from collections import Counter
from typing import Optional, Union


class CPDExecutionError(Exception):
    """Exceção customizada levantada quando a execução do PMD CPD falha."""
    pass


class CPDRunner:
    def __init__(self, pmd_path: Optional[str] = None):
        """
        Inicializa o runner do PMD CPD.
        Se o caminho para o PMD não for fornecido, tenta localizá-lo no PATH do sistema.
        """
        self.pmd_path = pmd_path or shutil.which("pmd")

        if not self.pmd_path:
            raise FileNotFoundError(
                "O executável 'pmd' não foi encontrado no seu sistema.\n"
                "Para usar o CodeTwin Analyzer, você precisa ter o PMD instalado.\n\n"
                "Instruções de instalação:\n"
                "1. Baixe o PMD em: https://pmd.github.io/\n"
                "2. Extraia o arquivo ZIP.\n"
                "3. Adicione a pasta 'bin' do PMD à variável PATH do seu sistema, "
                "ou passe o caminho completo do executável ao instanciar o CPDRunner."
            )

    def detect_language(self, source_dir: Union[str, Path]) -> Optional[str]:
        """
        Varre o diretório, mapeia as extensões e retorna a linguagem mais comum.
        """
        ext_mapping = {
            ".py": "python",
            ".java": "java",
            ".js": "javascript",
            ".ts": "typescript",
            ".cs": "cs",
            ".c": "c",
            ".cpp": "cpp",
            ".hpp": "cpp",
            ".c++": "cpp",
            ".go": "go",
            ".rb": "ruby",
            ".kt": "kotlin",
            ".swift": "swift",
            ".php": "php",
            ".r": "r"
        }

        ext_counts = Counter()

        for file_path in Path(source_dir).rglob("*.*"):
            if file_path.is_file():
                ext_counts[file_path.suffix.lower()] += 1

        lang_counts = Counter()
        for ext, count in ext_counts.items():
            if ext in ext_mapping:
                lang_counts[ext_mapping[ext]] += count

        if not lang_counts:
            return None

        most_common_lang = lang_counts.most_common(1)[0][0]
        return most_common_lang

    def run_cpd(
        self,
        source_dir: Union[str, Path],
        output_file: Union[str, Path],
        min_tokens: int = 100,
        language: Optional[str] = None
    ) -> None:
        """
        Executa o PMD Copy-Paste-Detector (CPD) no diretório especificado
        e salva a saída em um arquivo XML.
        """
        cmd = [
            self.pmd_path, "cpd",
            "--minimum-tokens", str(min_tokens),
            "-d", str(source_dir),
            "--format", "xml"
        ]

        if language:
            cmd.extend(["--language", language])

        with open(output_file, "w", encoding="utf-8") as out_f:
            try:
                result = subprocess.run(
                    cmd,
                    stdout=out_f,
                    stderr=subprocess.PIPE,
                    text=True,
                    check=False
                )
            except FileNotFoundError:
                raise CPDExecutionError(f"Falha ao tentar executar o comando: {self.pmd_path}")

            if result.returncode not in (0, 4):
                raise CPDExecutionError(
                    f"A execução do CPD falhou (Exit code {result.returncode}).\n"
                    f"Detalhes do erro: {result.stderr.strip()}"
                )

    def run_with_auto_detect(
        self,
        source_dir: Union[str, Path],
        output_file: Union[str, Path],
        min_tokens: int = 100
    ) -> None:
        """
        Detecta automaticamente a linguagem do repositório e executa o CPD.
        """
        language = self.detect_language(source_dir)

        if not language:
            raise ValueError(
                f"Não foi possível detectar automaticamente uma linguagem suportada "
                f"no diretório: {source_dir}"
            )

        self.run_cpd(source_dir, output_file, min_tokens, language)
