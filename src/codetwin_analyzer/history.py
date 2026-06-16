"""
Módulo para rastreamento histórico de clones de código em repositórios GitHub.

Permite analisar a evolução de code clones ao longo do tempo, comparando
commits, branches e calculando tendências temporais.
"""

import logging
import tempfile

from dataclasses import dataclass, field
from typing import List, Optional

from codetwin_analyzer.github_client import GitHubClient
from codetwin_analyzer.cpd_runner import CPDRunner
from codetwin_analyzer.parser import parse_cpd_xml, group_into_pairs, classify_clone_type

logger = logging.getLogger(__name__)


@dataclass
class HistoryEntry:
    """Representa a contagem de clones em um commit específico."""
    commit_sha: str
    timestamp: str
    branch: str
    type1_count: int
    type2_count: int
    total_clones: int


class CloneHistory:
    """
    Rastreia a evolução de clones de código ao longo do histórico de um repositório.

    Args:
        github_client: Instância autenticada de GitHubClient para comunicação com a API.
    """

    def __init__(self, github_client: GitHubClient):
        self.github_client = github_client
        self.entries: List[HistoryEntry] = []

    def _run_cpd_on_commit(
        self,
        owner: str,
        repo: str,
        commit_sha: str,
        temp_dir: str,
        min_tokens: int = 100,
    ) -> dict:
        """
        Baixa o repositório no estado de um commit específico, executa o CPD
        e retorna as contagens de clones por tipo.

        Args:
            owner: Proprietário do repositório no GitHub.
            repo: Nome do repositório.
            commit_sha: SHA do commit a ser analisado.
            temp_dir: Diretório temporário onde o repositório será extraído.
            min_tokens: Número mínimo de tokens para o CPD considerar um clone.

        Returns:
            Dict com chaves 'type1_count', 'type2_count' e 'total_clones'.
        """
        import os

        dest = os.path.join(temp_dir, commit_sha[:8])
        os.makedirs(dest, exist_ok=True)

        logger.debug(f"Baixando repositório {owner}/{repo} no commit {commit_sha[:8]}...")
        self.github_client.download_repository(owner, repo, dest, branch=commit_sha)

        output_xml = os.path.join(temp_dir, f"cpd_{commit_sha[:8]}.xml")

        try:
            runner = CPDRunner()
        except FileNotFoundError as e:
            logger.warning(f"PMD não disponível: {e}. Registrando zero clones para {commit_sha[:8]}.")
            return {"type1_count": 0, "type2_count": 0, "total_clones": 0}

        try:
            runner.run_with_auto_detect(dest, output_xml, min_tokens=min_tokens)
        except (ValueError, Exception) as e:
            logger.warning(
                f"Não foi possível executar CPD no commit {commit_sha[:8]}: {e}. "
                "Registrando zero clones."
            )
            return {"type1_count": 0, "type2_count": 0, "total_clones": 0}

        try:
            fragments = parse_cpd_xml(output_xml)
            pairs = group_into_pairs(fragments)
            for pair in pairs:
                classify_clone_type(pair)
        except Exception as e:
            logger.warning(f"Erro ao parsear resultados do CPD: {e}. Registrando zero clones.")
            return {"type1_count": 0, "type2_count": 0, "total_clones": 0}

        type1 = sum(1 for p in pairs if p.type == "Tipo 1")
        type2 = sum(1 for p in pairs if p.type == "Tipo 2")
        total = len(pairs)

        return {"type1_count": type1, "type2_count": type2, "total_clones": total}

    def track_commit_range(
        self,
        owner: str,
        repo: str,
        since: Optional[str] = None,
        until: Optional[str] = None,
        max_commits: int = 50,
        min_tokens: int = 100,
    ) -> List[HistoryEntry]:
        """
        Rastreia clones de código em um intervalo de commits do repositório.

        Para cada commit no intervalo: baixa o repositório, executa o CPD e
        armazena um HistoryEntry. Commits sem arquivos analisáveis recebem
        contagem zero e são pulados com aviso de log.

        Args:
            owner: Proprietário do repositório no GitHub.
            repo: Nome do repositório.
            since: Data ISO 8601 de início do intervalo (opcional).
            until: Data ISO 8601 de fim do intervalo (opcional).
            max_commits: Número máximo de commits a analisar.
            min_tokens: Número mínimo de tokens para o CPD.

        Returns:
            Lista de HistoryEntry gerada nesta chamada.
        """
        commits = self.github_client.get_commits(owner, repo, since=since, until=until)
        commits = commits[:max_commits]

        if not commits:
            logger.info(f"Nenhum commit encontrado para {owner}/{repo} no intervalo especificado.")
            return []

        logger.info(f"Analisando {len(commits)} commit(s) de {owner}/{repo}...")

        new_entries: List[HistoryEntry] = []

        with tempfile.TemporaryDirectory() as temp_dir:
            for idx, commit in enumerate(commits, start=1):
                sha = commit.get("sha", "")
                timestamp = commit.get("date", "")
                branch = commit.get("branch", "default")

                logger.info(f"[{idx}/{len(commits)}] Commit {sha[:8]} ({timestamp})")

                try:
                    counts = self._run_cpd_on_commit(
                        owner, repo, sha, temp_dir, min_tokens=min_tokens
                    )
                except Exception as e:
                    logger.warning(
                        f"Erro inesperado ao processar commit {sha[:8]}: {e}. "
                        "Registrando zero clones."
                    )
                    counts = {"type1_count": 0, "type2_count": 0, "total_clones": 0}

                entry = HistoryEntry(
                    commit_sha=sha,
                    timestamp=timestamp,
                    branch=branch,
                    type1_count=counts["type1_count"],
                    type2_count=counts["type2_count"],
                    total_clones=counts["total_clones"],
                )

                self.entries.append(entry)
                new_entries.append(entry)

        logger.info(f"Rastreamento concluído. {len(new_entries)} entrada(s) registrada(s).")
        return new_entries
