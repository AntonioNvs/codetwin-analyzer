import sys
import logging
import fire
import requests
from pathlib import Path
from typing import Optional

from codetwin_analyzer.utils import sanitize_repo_name, temp_dir
from codetwin_analyzer.github_client import GitHubClient, GitHubAPIError
from codetwin_analyzer.seart_client import SEARTClient, SEARTAPIError
from codetwin_analyzer.cpd_runner import CPDRunner, CPDExecutionError
from codetwin_analyzer.parser import parse_cpd_xml, group_into_pairs
from codetwin_analyzer.metrics import compute_clone_counts, most_cloned_files, clone_density

logger = logging.getLogger("codetwin_analyzer")

def setup_logging(verbose: bool, quiet: bool):
    """Configura os handlers de log para o console e para o arquivo."""
    if logger.hasHandlers():
        logger.handlers.clear()
        
    logger.setLevel(logging.DEBUG) 

    file_formatter = logging.Formatter('%(asctime)s - %(levelname)s - [%(module)s] %(message)s')
    file_handler = logging.FileHandler('codetwin.log', encoding='utf-8')
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(file_formatter)

    console_formatter = logging.Formatter('%(message)s') 
    console_handler = logging.StreamHandler(sys.stdout)
    
    if quiet:
        console_handler.setLevel(logging.WARNING)
    elif verbose:
        console_handler.setLevel(logging.DEBUG)
    else:
        console_handler.setLevel(logging.INFO)
        
    console_handler.setFormatter(console_formatter)

    logger.addHandler(file_handler)
    logger.addHandler(console_handler)


class CodeTwinCLI:
    """Interface de Linha de Comando (CLI) para o CodeTwin Analyzer."""

    def __init__(self, verbose: bool = False, quiet: bool = False):
        """
        Inicializa a CLI e configura o nível de verbosidade dos logs.
        
        Args:
            verbose: Ativa logs detalhados de depuração (DEBUG) no console.
            quiet: Suprime mensagens informativas, mostrando apenas avisos/erros (WARNING).
        """
        setup_logging(verbose, quiet)
        logger.debug("CodeTwin CLI instanciada (verbose=%s, quiet=%s)", verbose, quiet)

    def _handle_common_exceptions(self, exc: Exception):
        """Método auxiliar para centralizar as mensagens de erro amigáveis."""
        if isinstance(exc, GitHubAPIError):
            logger.error(f"Erro na API do GitHub: {exc}")
        elif isinstance(exc, SEARTAPIError):
            logger.error(f"Erro na API do SEART: {exc}")
        elif isinstance(exc, CPDExecutionError):
            logger.error(f"Falha ao executar o PMD CPD:\n{exc}")
        elif isinstance(exc, requests.exceptions.ConnectionError):
            logger.error("Erro de Conexão: Não foi possível acessar a internet. Verifique sua rede.")
        elif isinstance(exc, requests.exceptions.Timeout):
            logger.error("Timeout: O servidor demorou muito para responder. Tente novamente mais tarde.")
        elif isinstance(exc, FileNotFoundError):
            logger.error(f"Arquivo ou dependência não encontrada: {exc}")
        elif isinstance(exc, ValueError):
            logger.error(f"Erro de validação: {exc}")
        else:
            logger.exception(f"Erro inesperado: {exc}") 
            
        sys.exit(1)

    def analyze(
        self, 
        repo_url: str, 
        min_tokens: int = 100, 
        language: Optional[str] = None, 
        output: Optional[str] = None
    ):
        """Analisa um repositório do GitHub em busca de código duplicado."""
        logger.info(f"Iniciando análise para: {repo_url}")
        
        sanitized_name = sanitize_repo_name(repo_url)
        try:
            owner, repo = sanitized_name.split("/")
        except ValueError:
            logger.error("Erro: URL do repositório inválida. Use o formato https://github.com/owner/repo")
            sys.exit(1)

        output_file = output or "cpd_output.xml"

        try:
            github_client = GitHubClient()
            cpd_runner = CPDRunner()

            with temp_dir() as tmpdir:
                logger.info(f"Baixando código-fonte de {owner}/{repo}...")
                github_client.download_repository(owner, repo, destination=tmpdir)
                
                logger.info("Iniciando varredura com PMD CPD...")
                if language:
                    logger.debug(f"Forçando a linguagem: {language}")
                    cpd_runner.run_cpd(tmpdir, output_file, min_tokens, language)
                else:
                    logger.debug("Linguagem não fornecida. Iniciando autodetecção...")
                    cpd_runner.run_with_auto_detect(tmpdir, output_file, min_tokens)

            logger.info("Processando o XML e calculando estatísticas...")
            fragments = parse_cpd_xml(output_file)
            
            if not fragments:
                logger.info("Nenhum clone encontrado! A base de código está limpa.")
                return

            pairs = group_into_pairs(fragments)
            metrics = compute_clone_counts(pairs)
            top_files = most_cloned_files(pairs, top_n=5)

            print("\n" + "="*40)
            print(" SUMÁRIO DE ANÁLISE")
            print("="*40)
            print(f"Total de Clones Encontrados: {metrics.total_clones}")
            print(f"  - Tipo 1 (Idênticos):  {metrics.type1_count}")
            print(f"  - Tipo 2 (Similares):  {metrics.type2_count}")
            print(f"Total de Arquivos Afetados:  {metrics.total_files_affected}")
            print(f"Total de Linhas Duplicadas:  {metrics.total_lines_duplicated}")
            
            print("\n Top 5 Arquivos Mais Clonados:")
            for file_path, count in top_files:
                print(f"  - {Path(file_path).name}: {count} ocorrências")
                
            logger.info(f"Resultados salvos em: {output_file}")

        except Exception as e:
            self._handle_common_exceptions(e)

    def metrics(self, repo_url: str, min_tokens: int = 100):
        """Extrai um painel detalhado de métricas e densidade de clones de um repositório."""
        logger.info(f"Extraindo métricas avançadas para: {repo_url}")
        
        sanitized_name = sanitize_repo_name(repo_url)
        try:
            owner, repo = sanitized_name.split("/")
        except ValueError:
            logger.error("Erro: URL do repositório inválida.")
            sys.exit(1)

        output_file = "cpd_metrics_temp.xml"

        try:
            github_client = GitHubClient()
            cpd_runner = CPDRunner()

            with temp_dir() as tmpdir:
                logger.info(f"Baixando repositório {owner}/{repo}...")
                github_client.download_repository(owner, repo, destination=tmpdir)
                
                logger.debug("Detectando linguagem predominante...")
                language = cpd_runner.detect_language(tmpdir)
                if not language:
                    raise ValueError("Não foi possível detectar a linguagem do repositório de forma automática.")
                    
                logger.info(f"Linguagem predominante identificada: {language.capitalize()}")
                
                logger.debug("Contando linhas físicas de código fonte...")
                total_lines = 0
                ext_mapping = {
                    "python": [".py"], "java": [".java"], "javascript": [".js", ".jsx"],
                    "typescript": [".ts", ".tsx"], "cs": [".cs"], "c": [".c", ".h"],
                    "cpp": [".cpp", ".hpp", ".cc"], "go": [".go"], "ruby": [".rb"]
                }
                
                valid_extensions = ext_mapping.get(language, [])
                for file_path in Path(tmpdir).rglob("*.*"):
                    if file_path.is_file() and file_path.suffix.lower() in valid_extensions:
                        try:
                            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                                total_lines += sum(1 for _ in f)
                        except Exception:
                            continue

                logger.info("Rodando motor de análise sintática...")
                cpd_runner.run_cpd(tmpdir, output_file, min_tokens, language)

            fragments = parse_cpd_xml(output_file)
            
            if not fragments:
                print("\n" + "="*50)
                print(" RELATÓRIO DE MÉTRICAS - CÓDIGO LIMPO")
                print("="*50)
                print(f"Total de Linhas de Código: {total_lines}")
                print(f"Densidade de Clones:       0.00%")
                return

            pairs = group_into_pairs(fragments)
            counts = compute_clone_counts(pairs)
            top_files = most_cloned_files(pairs, top_n=5)
            density = clone_density(pairs, total_lines)

            print("\n" + "═"*50)
            print(" PAINEL DE MÉTRICAS DE CLONES")
            print("═"*50)
            print(f" Repositório:          {owner}/{repo}")
            print(f" Linguagem Base:       {language.capitalize()}")
            print(f" Total de Linhas (LOC): {total_lines}")
            print("\n TIPOS DE CLONES")
            print(" ─"*24)
            print(f"  Total de Ocorrências:   {counts.total_clones}")
            print(f"  - Tipo 1 (Idênticos):  {counts.type1_count}")
            print(f"  - Tipo 2 (Similares):  {counts.type2_count}")
            print("\n DENSIDADE")
            print(" ─"*24)
            print(f"  Linhas Duplicadas:      {counts.total_lines_duplicated}")
            print(f"  Densidade Geral:        {density * 100:.2f}% do projeto")
            print("\n TOP 5 ARQUIVOS CRÍTICOS")
            print(" ─"*24)
            for file_path, count in top_files:
                print(f"  • {Path(file_path).name}: {count} vezes")
            print("═"*50)
            
            Path(output_file).unlink(missing_ok=True)

        except Exception as e:
            self._handle_common_exceptions(e)

    def search(self, language: str, min_stars: int = 10, max_results: int = 10, analyze: bool = False):
        """Busca repositórios via SEART GHS e, opcionalmente, faz uma análise em lote."""
        logger.info(f"Buscando repositórios de '{language}' (Min. Stars: {min_stars})...")
        
        try:
            seart_client = SEARTClient()
            repos = seart_client.search_repositories(
                language=language, 
                min_stars=min_stars, 
                max_results=max_results
            )
            
            if not repos:
                logger.warning("Nenhum repositório encontrado com os critérios fornecidos.")
                return

            print(f"\nForam encontrados {len(repos)} repositórios:")
            for i, repo_name in enumerate(repos, 1):
                print(f"  {i}. {repo_name}")
                
            if not analyze:
                return
                
            print("\n" + "="*50)
            logger.info("Iniciando análise em lote (Batch Analysis)...")
            print("="*50)
            
            for repo_name in repos:
                repo_url = f"https://github.com/{repo_name}"
                safe_repo_name = repo_name.replace("/", "_")
                xml_output = f"{safe_repo_name}_cpd.xml"
                
                print("\n" + "-" * 40)
                logger.info(f"Inspecionando: {repo_name}")
                
                try:
                    self.analyze(repo_url=repo_url, language=language, output=xml_output)
                except SystemExit:
                    logger.warning(f"Pulo forçado: falha ao processar {repo_name}. Avançando para o próximo...")
                    continue
                    
            logger.info("Análise em lote concluída com sucesso!")

        except Exception as e:
            self._handle_common_exceptions(e)

def main():
    """Ponto de entrada principal para a CLI."""
    fire.Fire(CodeTwinCLI)  # type: ignore

if __name__ == "__main__":
    main()