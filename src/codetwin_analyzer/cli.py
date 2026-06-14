import sys
import fire

from pathlib import Path
from typing import Optional

from codetwin_analyzer.utils import sanitize_repo_name, temp_dir
from codetwin_analyzer.parser import parse_cpd_xml, group_into_pairs
from codetwin_analyzer.cpd_runner import CPDRunner, CPDExecutionError
from codetwin_analyzer.seart_client import SEARTClient, SEARTAPIError
from codetwin_analyzer.github_client import GitHubClient, GitHubAPIError
from codetwin_analyzer.metrics import compute_clone_counts, most_cloned_files

class CodeTwinCLI:
    """Interface de Linha de Comando (CLI) para o CodeTwin Analyzer."""

    def analyze(
        self, 
        repo_url: str, 
        min_tokens: int = 100, 
        language: Optional[str] = None, 
        output: Optional[str] = None
    ):
        """
        Analisa um repositório do GitHub em busca de código duplicado.

        Args:
            repo_url: URL do repositório no GitHub (ex: https://github.com/owner/repo).
            min_tokens: Quantidade mínima de tokens para considerar como clone (default: 100).
            language: Linguagem específica para forçar a análise (default: auto-detect).
            output: Caminho para salvar o XML final (default: cpd_output.xml no diretório atual).
        """
        print(f"Iniciando CodeTwin Analyzer para: {repo_url}")
        
        sanitized_name = sanitize_repo_name(repo_url)
        try:
            owner, repo = sanitized_name.split("/")
        except ValueError:
            print(f"Erro: URL do repositório inválida. Use o formato https://github.com/owner/repo")
            sys.exit(1)

        output_file = output or "cpd_output.xml"

        try:
            github_client = GitHubClient()
            cpd_runner = CPDRunner()

            with temp_dir() as tmpdir:
                print(f"Baixando repositório {owner}/{repo}...")
                github_client.download_repository(owner, repo, destination=tmpdir)
                
                print("Executando PMD CPD (Detecção de Clones)...")
                if language:
                    cpd_runner.run_cpd(tmpdir, output_file, min_tokens, language)
                else:
                    cpd_runner.run_with_auto_detect(tmpdir, output_file, min_tokens)

            print("Processando resultados e calculando métricas...")
            fragments = parse_cpd_xml(output_file)
            
            if not fragments:
                print("\n✅ Nenhum clone encontrado! A base de código está limpa.")
                return

            pairs = group_into_pairs(fragments)
            metrics = compute_clone_counts(pairs)
            top_files = most_cloned_files(pairs, top_n=5)

            print("\n" + "="*40)
            print("📈 SUMÁRIO DE ANÁLISE")
            print("="*40)
            print(f"Total de Clones Encontrados: {metrics.total_clones}")
            print(f"  - Clones Exatos (Tipo 1):  {metrics.type1_count}")
            print(f"  - Clones Similares (Tipo 2): {metrics.type2_count}")
            print(f"Total de Arquivos Afetados:  {metrics.total_files_affected}")
            print(f"Total de Linhas Duplicadas:  {metrics.total_lines_duplicated}")
            
            print("\nTop 5 Arquivos Mais Clonados:")
            for file_path, count in top_files:
                clean_name = Path(file_path).name
                print(f"  - {clean_name}: {count} ocorrências")
                
            print(f"\nArquivo XML detalhado salvo em: {output_file}")

        except (GitHubAPIError, CPDExecutionError, ValueError, FileNotFoundError) as e:
            print(f"\n❌ Erro durante a execução:\n{e}")
            sys.exit(1)


    def search(
        self, 
        language: str, 
        min_stars: int = 10, 
        max_results: int = 10, 
        analyze: bool = False
    ):
        """
        Busca repositórios no GitHub via SEART GHS e, opcionalmente, analisa todos eles.

        Args:
            language: Linguagem principal desejada (ex: java, python).
            min_stars: Quantidade mínima de estrelas (default: 10).
            max_results: Quantidade máxima de repositórios para retornar (default: 10).
            analyze: Se True, baixa e executa o PMD CPD em cada repositório encontrado (default: False).
        """
        print(f"🔎 Buscando repositórios de '{language}' com no mínimo {min_stars} estrelas...")
        
        try:
            seart_client = SEARTClient()
            repos = seart_client.search_repositories(
                language=language, 
                min_stars=min_stars, 
                max_results=max_results
            )
            
            if not repos:
                print("Nenhum repositório encontrado com esses critérios.")
                return

            print(f"\nForam encontrados {len(repos)} repositórios:")
            for i, repo_name in enumerate(repos, 1):
                print(f"  {i}. {repo_name}")
                
            if not analyze:
                return
                
            print("\n" + "="*50)
            print("Iniciando análise em lote (Batch Analysis)...")
            print("="*50)
            
            for repo_name in repos:
                repo_url = f"https://github.com/{repo_name}"
                safe_repo_name = repo_name.replace("/", "_")
                xml_output = f"{safe_repo_name}_cpd.xml"
                
                print(f"\n🔄 Inspecionando: {repo_name}")
                print("-" * 40)
                
                try:
                    self.analyze(
                        repo_url=repo_url, 
                        language=language, 
                        output=xml_output
                    )
                except SystemExit:
                    print(f"Pulo forçado para o próximo repositório devido a um erro na análise de {repo_name}.")
                    continue
                    
            print("\n🏁 Análise em lote concluída com sucesso!")

        except SEARTAPIError as e:
            print(f"\n❌ Erro ao consultar o SEART GHS:\n{e}")
            sys.exit(1)

def main():
    """Ponto de entrada principal para a CLI."""
    fire.Fire(CodeTwinCLI) #type: ignore

if __name__ == "__main__":
    main()