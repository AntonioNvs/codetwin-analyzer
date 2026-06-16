"""
Módulo para rastreamento histórico de clones de código em repositórios GitHub.

Permite analisar a evolução de code clones ao longo do tempo, comparando
commits, branches e calculando tendências temporais.
"""

import logging
import tempfile

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

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


@dataclass
class BranchComparison:
    """Resultado da comparação de clones entre duas ou mais branches."""
    branch_names: List[str]
    clone_counts: Dict[str, int]          # branch → total_clones
    type1_counts: Dict[str, int]          # branch → type1_count
    type2_counts: Dict[str, int]          # branch → type2_count
    diff_pairs: Dict[str, int]            # 'branch_a vs branch_b' → diferença de total_clones


@dataclass
class TrendResult:
    """Resultado da análise de tendência temporal de clones."""
    type1_trend: str    # 'crescente', 'decrescente' ou 'estável'
    type2_trend: str    # 'crescente', 'decrescente' ou 'estável'
    type1_slope: float  # inclinação da reta de regressão para Tipo 1
    type2_slope: float  # inclinação da reta de regressão para Tipo 2


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

    def compare_branches(
        self,
        owner: str,
        repo: str,
        branches: List[str],
        min_tokens: int = 100,
    ) -> BranchComparison:
        """
        Detecta clones na ponta de cada branch informada e compara as contagens.

        Para cada branch, baixa o repositório no seu estado mais recente, executa
        o CPD e registra as contagens. O campo diff_pairs indica a diferença absoluta
        de total_clones entre cada par de branches.

        Args:
            owner: Proprietário do repositório no GitHub.
            repo: Nome do repositório.
            branches: Lista de nomes de branches a comparar.
            min_tokens: Número mínimo de tokens para o CPD.

        Returns:
            BranchComparison com contagens por branch e diffs entre pares.
        """
        clone_counts: Dict[str, int] = {}
        type1_counts: Dict[str, int] = {}
        type2_counts: Dict[str, int] = {}

        with tempfile.TemporaryDirectory() as temp_dir:
            for branch in branches:
                logger.info(f"Analisando branch '{branch}' de {owner}/{repo}...")
                try:
                    counts = self._run_cpd_on_commit(
                        owner, repo, branch, temp_dir, min_tokens=min_tokens
                    )
                except Exception as e:
                    logger.warning(f"Erro ao analisar branch '{branch}': {e}. Usando zero.")
                    counts = {"type1_count": 0, "type2_count": 0, "total_clones": 0}

                clone_counts[branch] = counts["total_clones"]
                type1_counts[branch] = counts["type1_count"]
                type2_counts[branch] = counts["type2_count"]

        diff_pairs: Dict[str, int] = {}
        for i in range(len(branches)):
            for j in range(i + 1, len(branches)):
                key = f"{branches[i]} vs {branches[j]}"
                diff_pairs[key] = abs(clone_counts[branches[i]] - clone_counts[branches[j]])

        return BranchComparison(
            branch_names=list(branches),
            clone_counts=clone_counts,
            type1_counts=type1_counts,
            type2_counts=type2_counts,
            diff_pairs=diff_pairs,
        )

    def track_default_branch_history(
        self,
        owner: str,
        repo: str,
        depth: int = 20,
        min_tokens: int = 100,
    ) -> List[HistoryEntry]:
        """
        Analisa os últimos N commits da branch default do repositório.

        Atalho conveniente que resolve a branch padrão via GitHubClient e
        delega para track_commit_range com max_commits=depth.

        Args:
            owner: Proprietário do repositório no GitHub.
            repo: Nome do repositório.
            depth: Número de commits recentes a analisar (padrão: 20).
            min_tokens: Número mínimo de tokens para o CPD.

        Returns:
            Lista de HistoryEntry gerada nesta chamada.
        """
        default_branch = self.github_client.get_default_branch(owner, repo)
        logger.info(
            f"Rastreando branch default '{default_branch}' de {owner}/{repo} "
            f"(últimos {depth} commits)..."
        )
        return self.track_commit_range(
            owner, repo, max_commits=depth, min_tokens=min_tokens
        )

    def to_time_series(
        self,
    ) -> List[Tuple[str, int, int]]:
        """
        Converte as entradas do histórico em série temporal ordenada.

        Returns:
            Lista de tuplas (timestamp, type1_count, type2_count) ordenada
            cronologicamente pelo timestamp ISO 8601.
        """
        sorted_entries = sorted(
            self.entries,
            key=lambda e: e.timestamp or "",
        )
        return [(e.timestamp, e.type1_count, e.type2_count) for e in sorted_entries]

    def compute_trend(self) -> TrendResult:
        """
        Calcula a tendência temporal de clones por tipo usando regressão linear.

        A regressão é calculada manualmente via somatórios (sem dependências externas).
        Para menos de 2 pontos, retorna slope=0.0 e tendência 'estável'.

        Returns:
            TrendResult com slope e classificação de tendência para Tipo 1 e Tipo 2.
        """
        series = self.to_time_series()
        n = len(series)

        def _classify(slope: float) -> str:
            if slope > 0:
                return "crescente"
            elif slope < 0:
                return "decrescente"
            return "estável"

        def _linear_slope(ys: List[float]) -> float:
            """Calcula o slope (b) de y = a + b*x via mínimos quadrados."""
            xs = list(range(len(ys)))
            n = len(ys)
            sum_x = sum(xs)
            sum_y = sum(ys)
            sum_xy = sum(x * y for x, y in zip(xs, ys))
            sum_x2 = sum(x * x for x in xs)
            denom = n * sum_x2 - sum_x ** 2
            if denom == 0:
                return 0.0
            return (n * sum_xy - sum_x * sum_y) / denom

        if n < 2:
            return TrendResult(
                type1_trend="estável",
                type2_trend="estável",
                type1_slope=0.0,
                type2_slope=0.0,
            )

        type1_values = [float(t[1]) for t in series]
        type2_values = [float(t[2]) for t in series]

        slope1 = _linear_slope(type1_values)
        slope2 = _linear_slope(type2_values)

        return TrendResult(
            type1_trend=_classify(slope1),
            type2_trend=_classify(slope2),
            type1_slope=slope1,
            type2_slope=slope2,
        )
