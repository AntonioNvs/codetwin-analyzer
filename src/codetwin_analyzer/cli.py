import sys
import logging
import fire
import requests

from pathlib import Path
from typing import Optional
from dotenv import load_dotenv

from codetwin_analyzer.utils import sanitize_repo_name, temp_dir
from codetwin_analyzer.github_client import GitHubClient, GitHubAPIError
from codetwin_analyzer.seart_client import SEARTClient, SEARTAPIError
from codetwin_analyzer.cpd_runner import CPDRunner, CPDExecutionError
from codetwin_analyzer.parser import parse_cpd_xml, group_into_pairs
from codetwin_analyzer.metrics import compute_clone_counts, most_cloned_files, clone_density
from codetwin_analyzer.history import CloneHistory
from codetwin_analyzer.exporter import CloneExporter

logger = logging.getLogger("codetwin_analyzer")

load_dotenv()


class ColorFormatter(logging.Formatter):
    """Formatter para adicionar cores ANSI baseadas no nível de log."""
    COLORS = {
        logging.DEBUG: "\033[36m",      # Cyan
        logging.INFO: "\033[34m",       # Azul
        logging.WARNING: "\033[33m",    # Amarelo
        logging.ERROR: "\033[31m",      # Vermelho
        logging.CRITICAL: "\033[1;31m", # Vermelho Negrito
    }
    RESET = "\033[0m"

    def format(self, record):
        # Evita modificar o record original se houver múltiplos handlers
        msg = super().format(record)
        color = self.COLORS.get(record.levelno, self.RESET)
        return f"{color}{msg}{self.RESET}"


def setup_logging(verbose: bool, quiet: bool):
    """Configura os handlers de log para o console e para o arquivo."""
    if logger.hasHandlers():
        logger.handlers.clear()

    logger.setLevel(logging.DEBUG)

    file_formatter = logging.Formatter('%(asctime)s - %(levelname)s - [%(module)s] %(message)s')
    file_handler = logging.FileHandler('codetwin.log', encoding='utf-8')
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(file_formatter)

    console_formatter = ColorFormatter('%(message)s')
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

    def __init__(self, verbose: bool = False, quiet: bool = False, progress: bool = False):
        """
        Inicializa a CLI e configura o nível de verbosidade dos logs.

        Args:
            verbose: Ativa logs detalhados de depuração (DEBUG) no console.
            quiet: Suprime mensagens informativas, mostrando apenas avisos/erros (WARNING).
            progress: Exibe o progresso das etapas (1/5, etc.) nos comandos.
        """
        setup_logging(verbose, quiet)
        self.progress = progress
        logger.debug("CodeTwin CLI instanciada (verbose=%s, quiet=%s, progress=%s)", verbose, quiet, progress)

    def _get_step_prefix(self, step: int, total: int = 5) -> str:
        return f"[{step}/{total}] " if self.progress else ""

    def _handle_common_exceptions(self, exc: Exception):
        """Método auxiliar para centralizar as mensagens de erro amigáveis."""
        if isinstance(exc, GitHubAPIError):
            logger.error(f"Erro na API do GitHub: {exc}\n  -> Sugestão: Verifique se o repositório existe e se o seu GITHUB_TOKEN (se aplicável) tem permissão de leitura.")
        elif isinstance(exc, SEARTAPIError):
            logger.error(f"Erro na API do SEART: {exc}\n  -> Sugestão: A API pode estar instável. Aguarde alguns instantes e tente novamente com os mesmos ou outros filtros.")
        elif isinstance(exc, CPDExecutionError):
            logger.error(f"Falha ao executar o PMD CPD:\n{exc}\n  -> Sugestão: Certifique-se de que o PMD está instalado, acessível no PATH do sistema, e de que é a versão suportada.")
        elif isinstance(exc, requests.exceptions.ConnectionError):
            logger.error("Erro de Conexão: Não foi possível acessar a internet.\n  -> Sugestão: Verifique sua conexão com a rede ou configurações de proxy.")
        elif isinstance(exc, requests.exceptions.Timeout):
            logger.error("Timeout: O servidor demorou muito para responder.\n  -> Sugestão: Tente novamente mais tarde ou verifique a estabilidade da sua internet.")
        elif isinstance(exc, FileNotFoundError):
            logger.error(f"Arquivo ou dependência não encontrada: {exc}\n  -> Sugestão: Verifique se o arquivo especificado existe e se os caminhos estão corretos.")
        elif isinstance(exc, ValueError):
            logger.error(f"Erro de validação: {exc}\n  -> Sugestão: Verifique os parâmetros passados para o comando e tente novamente.")
        else:
            logger.exception(f"Erro inesperado: {exc}\n  -> Sugestão: Se o erro persistir, abra uma issue no repositório do CodeTwin Analyzer relatando o ocorrido.")

        sys.exit(1)

    def analyze(
        self,
        repo_url: str,
        min_tokens: int = 100,
        language: Optional[str] = None,
        format: str = "text",
        output: Optional[str] = None,
        history: bool = False
    ):
        """Analisa um repositório do GitHub em busca de código duplicado."""
        logger.info(f"Iniciando análise para: {repo_url}")

        sanitized_name = sanitize_repo_name(repo_url)
        try:
            owner, repo = sanitized_name.split("/")
        except ValueError:
            logger.error("Erro: URL do repositório inválida. Use o formato https://github.com/owner/repo")
            sys.exit(1)

        xml_output = "cpd_output_temp.xml"

        try:
            github_client = GitHubClient()
            cpd_runner = CPDRunner()

            with temp_dir() as tmpdir:
                logger.info(f"Baixando código-fonte de {owner}/{repo}...")
                github_client.download_repository(owner, repo, destination=tmpdir)

                logger.info("Iniciando varredura com PMD CPD...")
                if language:
                    logger.debug(f"Forçando a linguagem: {language}")
                    cpd_runner.run_cpd(tmpdir, xml_output, min_tokens, language)
                else:
                    logger.debug("Linguagem não fornecida. Iniciando autodetecção...")
                    cpd_runner.run_with_auto_detect(tmpdir, xml_output, min_tokens)

                logger.info("Processando o XML e calculando estatísticas...")
                fragments = parse_cpd_xml(xml_output)

                if not fragments:
                    logger.info("Nenhum clone encontrado! A base de código está limpa.")
                    return

                pairs = group_into_pairs(fragments)
                metrics = compute_clone_counts(pairs)

            hist_entries = None
            if history:
                logger.info("Rastreando histórico de clones...")
                clone_history = CloneHistory(github_client)
                hist_entries = clone_history.track_default_branch_history(
                    owner, repo, depth=20, min_tokens=min_tokens
                )

            exporter = CloneExporter()
            if output:
                if format == "json":
                    exporter.to_json({"metrics": metrics, "history": hist_entries}, output)
                elif format == "csv":
                    exporter.to_csv(pairs, output)
                elif format == "html":
                    exporter.to_html_report(metrics, pairs, hist_entries, output)
                else:
                    exporter.to_text_report(metrics, pairs, hist_entries, output)
                logger.info(f"Resultados exportados para: {output}")
            else:
                if format == "json":
                    print(exporter.to_json({"metrics": metrics, "history": hist_entries}))
                elif format == "csv":
                    logger.error("Formato CSV requer um arquivo de saída (--output).")
                    sys.exit(1)
                elif format == "html":
                    print(exporter.to_html_report(metrics, pairs, hist_entries))
                else:
                    print("\n" + exporter.to_text_report(metrics, pairs, hist_entries))

            Path(xml_output).unlink(missing_ok=True)

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

            # Variáveis de controle para o relatório final
            fragments = []
            total_lines = 0
            language = ""
            counts = None
            top_files = []
            density = 0.0

            with temp_dir() as tmpdir:
                logger.info(f"Baixando repositório {owner}/{repo}...")
                github_client.download_repository(owner, repo, destination=tmpdir)

                logger.debug("Detectando linguagem predominante...")
                language = cpd_runner.detect_language(tmpdir)
                if not language:
                    raise ValueError("Não foi possível detectar a linguagem do repositório de forma automática.")

                logger.info(f"Linguagem predominante identificada: {language.capitalize()}")

                logger.debug("Contando linhas físicas de código fonte...")
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

                logger.info("Processando o XML, lendo arquivos locais e calculando estatísticas...")
                fragments = parse_cpd_xml(output_file)

                if fragments:
                    pairs = group_into_pairs(fragments)
                    # AGORA SIM: Roda a classificação abrindo os arquivos reais antes que o 'with' acabe!
                    counts = compute_clone_counts(pairs)
                    top_files = most_cloned_files(pairs, top_n=5)
                    density = clone_density(pairs, total_lines)

            # --- O bloco 'with' fecha aqui e limpa o /tmp ---

            if not fragments or not counts:
                print("\n" + "=" * 50)
                print(" RELATÓRIO DE MÉTRICAS - CÓDIGO LIMPO")
                print("=" * 50)
                print(f"Total de Linhas de Código: {total_lines}")
                print("Densidade de Clones:       0.00%")
                return

            print("\n" + "═" * 50)
            print(" PAINEL DE MÉTRICAS DE CLONES (VERIFICAÇÃO COMPLETA)")
            print("═" * 50)
            print(f" Repositório:          {owner}/{repo}")
            print(f" Linguagem Base:       {language.capitalize()}")
            print(f" Total de Linhas (LOC): {total_lines}")
            print("\n TIPOS DE CLONES DETECTADOS")
            print(" ─" * 24)
            print(f"  Total de Ocorrências:   {counts.total_clones}")
            print(f"  - Tipo 1 (Idênticos):  {counts.type1_count}")
            print(f"  - Tipo 2 (Similares):  {counts.type2_count}")
            print("\n DENSIDADE")
            print(" ─" * 24)
            print(f"  Linhas Duplicadas:      {counts.total_lines_duplicated}")
            print(f"  Densidade Geral:        {density * 100:.2f}% do projeto")
            print("\n TOP 5 ARQUIVOS CRÍTICOS")
            print(" ─" * 24)
            for file_path, count in top_files:
                print(f"  • {Path(file_path).name}: {count} vezes")
            print("═" * 50)

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

            print("\n" + "=" * 50)
            logger.info("Iniciando análise em lote (Batch Analysis)...")
            print("=" * 50)

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

    def history(self, repo_url: str, depth: int = 20, min_tokens: int = 100):
        """Analisa o histórico de clones da branch default e exibe a tendência."""
        logger.info(f"Iniciando análise de histórico para: {repo_url} (depth={depth})")

        sanitized_name = sanitize_repo_name(repo_url)
        try:
            owner, repo = sanitized_name.split("/")
        except ValueError:
            logger.error("Erro: URL do repositório inválida.")
            sys.exit(1)

        try:
            github_client = GitHubClient()
            clone_history = CloneHistory(github_client)

            entries = clone_history.track_default_branch_history(
                owner, repo, depth=depth, min_tokens=min_tokens
            )

            if not entries:
                logger.info("Nenhum histórico analisável encontrado.")
                return

            trend = clone_history.compute_trend()

            print("\n" + "=" * 50)
            print(" ANÁLISE DE TENDÊNCIA DE CLONES")
            print("=" * 50)
            print(f"Repositório: {owner}/{repo}")
            print(f"Commits analisados: {len(entries)}")
            print("-" * 50)
            print(f"Tendência Tipo 1: {trend.type1_trend.upper()} (slope: {trend.type1_slope:.2f})")
            print(f"Tendência Tipo 2: {trend.type2_trend.upper()} (slope: {trend.type2_slope:.2f})")
            print("=" * 50)

        except Exception as e:
            self._handle_common_exceptions(e)

    def report(
        self,
        repo_url: str,
        min_tokens: int = 100,
        with_history: bool = True,
        format: str = "text",
        output: Optional[str] = None
    ):
        """Executa um pipeline completo gerando um relatório."""
        logger.info(f"Iniciando pipeline de relatório para: {repo_url}")

        sanitized_name = sanitize_repo_name(repo_url)
        try:
            owner, repo = sanitized_name.split("/")
        except ValueError:
            logger.error("Erro: URL do repositório inválida.")
            sys.exit(1)

        xml_output = "cpd_report_temp.xml"
        metrics = None
        pairs = []
        hist_entries = None
        
        status = {
            "download": "Pendente",
            "cpd": "Pendente",
            "parse": "Pendente",
            "metrics": "Pendente",
            "history": "Pendente" if with_history else "Ignorado",
            "export": "Pendente"
        }

        try:
            github_client = GitHubClient()
            cpd_runner = CPDRunner()

            with temp_dir() as tmpdir:
                try:
                    logger.info(f"{self._get_step_prefix(1, 5)}Baixando código-fonte...")
                    github_client.download_repository(owner, repo, destination=tmpdir)
                    status["download"] = "Sucesso"
                except Exception as e:
                    status["download"] = f"Falha ({e})"

                if status["download"] == "Sucesso":
                    try:
                        logger.info(f"{self._get_step_prefix(2, 5)}Detectando linguagem e executando PMD CPD...")
                        cpd_runner.run_with_auto_detect(tmpdir, xml_output, min_tokens)
                        status["cpd"] = "Sucesso"
                    except Exception as e:
                        status["cpd"] = f"Falha ({e})"
                else:
                    status["cpd"] = "Ignorado"

                if status["cpd"] == "Sucesso":
                    try:
                        logger.info(f"{self._get_step_prefix(3, 5)}Processando resultados do CPD...")
                        fragments = parse_cpd_xml(xml_output)
                        if fragments:
                            pairs = group_into_pairs(fragments)
                        status["parse"] = "Sucesso"
                    except Exception as e:
                        status["parse"] = f"Falha ({e})"
                else:
                    status["parse"] = "Ignorado"

                if status["parse"] == "Sucesso":
                    try:
                        logger.info(f"{self._get_step_prefix(4, 5)}Calculando métricas...")
                        if pairs:
                            metrics = compute_clone_counts(pairs)
                        status["metrics"] = "Sucesso"
                    except Exception as e:
                        status["metrics"] = f"Falha ({e})"
                else:
                    status["metrics"] = "Ignorado"

            if with_history:
                try:
                    logger.info(f"{self._get_step_prefix(5, 5)}Rastreando histórico de clones...")
                    clone_history = CloneHistory(github_client)
                    hist_entries = clone_history.track_default_branch_history(
                        owner, repo, depth=20, min_tokens=min_tokens
                    )
                    status["history"] = "Sucesso"
                except Exception as e:
                    status["history"] = f"Falha ({e})"
            else:
                logger.info(f"{self._get_step_prefix(5, 5)}Histórico ignorado (with_history=False).")

            try:
                logger.info("Exportando relatório final...")
                exporter = CloneExporter()
                if output:
                    if format == "json":
                        exporter.to_json({"metrics": metrics, "history": hist_entries}, output)
                    elif format == "csv":
                        if pairs:
                            exporter.to_csv(pairs, output)
                        else:
                            logger.warning("Nenhum clone para exportar em CSV.")
                    elif format == "html":
                        exporter.to_html_report(metrics, pairs, hist_entries, output)
                    else:
                        exporter.to_text_report(metrics, pairs, hist_entries, output)
                    logger.info(f"Relatório exportado para: {output}")
                else:
                    if format == "json":
                        print(exporter.to_json({"metrics": metrics, "history": hist_entries}))
                    elif format == "csv":
                        logger.error("Formato CSV requer um arquivo de saída (--output).")
                    elif format == "html":
                        print(exporter.to_html_report(metrics, pairs, hist_entries))
                    else:
                        print("\n" + exporter.to_text_report(metrics, pairs, hist_entries))
                status["export"] = "Sucesso"
            except Exception as e:
                status["export"] = f"Falha ({e})"

        finally:
            Path(xml_output).unlink(missing_ok=True)
            print("\n" + "=" * 50)
            print(" STATUS DO PIPELINE DE RELATÓRIO")
            print("=" * 50)
            for step, res in status.items():
                print(f" {step.capitalize():<10}: {res}")
            print("=" * 50)


def main():
    """Ponto de entrada principal para a CLI."""
    fire.Fire(CodeTwinCLI)


if __name__ == "__main__":
    main()
