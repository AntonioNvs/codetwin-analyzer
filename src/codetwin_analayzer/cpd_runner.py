import shutil
import subprocess

from pathlib import Path
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
                "Executável 'pmd' não encontrado no PATH. "
                "Certifique-se de que o PMD está instalado ou forneça o caminho explícito."
            )

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
            "--files", str(source_dir),
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

            if result.returncode != 0:
                raise CPDExecutionError(
                    f"A execução do CPD falhou (Exit code {result.returncode}).\n"
                    f"Detalhes do erro: {result.stderr.strip()}"
                )