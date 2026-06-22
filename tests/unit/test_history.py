"""
Testes unitários para o módulo codetwin_analyzer.history.
Cobre: track_commit_range, compare_branches, to_time_series e compute_trend.
"""

import pytest

from unittest.mock import MagicMock, patch
from codetwin_analyzer.history import CloneHistory, HistoryEntry, TrendResult


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_github_client(commits=None):
    """Retorna um GitHubClient mockado com get_commits configurável."""
    client = MagicMock()
    client.get_commits.return_value = commits or []
    client.get_default_branch.return_value = "main"
    return client


def _make_entry(sha, timestamp, branch="main", t1=0, t2=0, total=0):
    return HistoryEntry(
        commit_sha=sha,
        timestamp=timestamp,
        branch=branch,
        type1_count=t1,
        type2_count=t2,
        total_clones=total,
    )


# ---------------------------------------------------------------------------
# Testes
# ---------------------------------------------------------------------------

class TestCloneHistory:

    # 1. track_commit_range_empty ----------------------------------------

    def test_track_commit_range_empty(self):
        """Sem commits no intervalo → retorna lista vazia e entries permanece vazio."""
        client = _make_github_client(commits=[])
        history = CloneHistory(client)

        result = history.track_commit_range("owner", "repo")

        assert result == []
        assert history.entries == []

    # 2. track_commit_range_with_mock ------------------------------------

    def test_track_commit_range_with_mock(self):
        """Com commits mockados, deve criar uma HistoryEntry por commit."""
        commits = [
            {"sha": "aaa111bbb222ccc3", "date": "2024-01-01T00:00:00Z", "message": "init"},
            {"sha": "bbb222ccc333ddd4", "date": "2024-01-02T00:00:00Z", "message": "fix"},
        ]
        client = _make_github_client(commits=commits)
        history = CloneHistory(client)

        # Substitui _run_cpd_on_commit para não depender de PMD/GitHub real
        history._run_cpd_on_commit = MagicMock(
            return_value={"type1_count": 2, "type2_count": 1, "total_clones": 3}
        )

        result = history.track_commit_range("owner", "repo", max_commits=10)

        assert len(result) == 2
        assert len(history.entries) == 2

        first = result[0]
        assert first.commit_sha == "aaa111bbb222ccc3"
        assert first.type1_count == 2
        assert first.type2_count == 1
        assert first.total_clones == 3

    # 3. compare_branches_same_code -------------------------------------

    def test_compare_branches_same_code(self):
        """Código idêntico em duas branches → diff_pairs deve ser 0."""
        client = _make_github_client()
        history = CloneHistory(client)

        # Ambas as branches retornam as mesmas contagens
        history._run_cpd_on_commit = MagicMock(
            return_value={"type1_count": 3, "type2_count": 1, "total_clones": 4}
        )

        result = history.compare_branches("owner", "repo", branches=["main", "dev"])

        assert result.clone_counts["main"] == 4
        assert result.clone_counts["dev"] == 4
        assert result.diff_pairs["main vs dev"] == 0

    # 4. to_time_series_ordering ----------------------------------------

    def test_to_time_series_ordering(self):
        """to_time_series deve retornar entries ordenadas cronologicamente."""
        client = _make_github_client()
        history = CloneHistory(client)

        # Inserimos em ordem inversa
        history.entries = [
            _make_entry("c3", "2024-03-01T00:00:00Z", t1=5, t2=2, total=7),
            _make_entry("c1", "2024-01-01T00:00:00Z", t1=1, t2=0, total=1),
            _make_entry("c2", "2024-02-01T00:00:00Z", t1=3, t2=1, total=4),
        ]

        series = history.to_time_series()

        assert len(series) == 3
        timestamps = [s[0] for s in series]
        assert timestamps == sorted(timestamps)
        # Primeiro ponto deve ser de janeiro
        assert series[0][0] == "2024-01-01T00:00:00Z"
        assert series[0][1] == 1   # type1
        assert series[0][2] == 0   # type2

    # 5. compute_trend_increasing ----------------------------------------

    def test_compute_trend_increasing(self):
        """Contagem crescente deve resultar em tendência 'crescente' e slope > 0."""
        client = _make_github_client()
        history = CloneHistory(client)

        history.entries = [
            _make_entry("a", "2024-01-01T00:00:00Z", t1=1, t2=0),
            _make_entry("b", "2024-02-01T00:00:00Z", t1=3, t2=1),
            _make_entry("c", "2024-03-01T00:00:00Z", t1=6, t2=2),
        ]

        result = history.compute_trend()

        assert isinstance(result, TrendResult)
        assert result.type1_trend == "crescente"
        assert result.type1_slope > 0
        assert result.type2_trend == "crescente"
        assert result.type2_slope > 0

    # 6. compute_trend_decreasing ----------------------------------------

    def test_compute_trend_decreasing(self):
        """Contagem decrescente deve resultar em tendência 'decrescente' e slope < 0."""
        client = _make_github_client()
        history = CloneHistory(client)

        history.entries = [
            _make_entry("a", "2024-01-01T00:00:00Z", t1=10, t2=5),
            _make_entry("b", "2024-02-01T00:00:00Z", t1=6,  t2=3),
            _make_entry("c", "2024-03-01T00:00:00Z", t1=2,  t2=1),
        ]

        result = history.compute_trend()

        assert result.type1_trend == "decrescente"
        assert result.type1_slope < 0
        assert result.type2_trend == "decrescente"
        assert result.type2_slope < 0

    # 7. compute_trend_stable --------------------------------------------

    def test_compute_trend_stable(self):
        """Contagem constante deve resultar em tendência 'estável' e slope == 0."""
        client = _make_github_client()
        history = CloneHistory(client)

        history.entries = [
            _make_entry("a", "2024-01-01T00:00:00Z", t1=4, t2=2),
            _make_entry("b", "2024-02-01T00:00:00Z", t1=4, t2=2),
            _make_entry("c", "2024-03-01T00:00:00Z", t1=4, t2=2),
        ]

        result = history.compute_trend()

        assert result.type1_trend == "estável"
        assert result.type1_slope == 0.0
        assert result.type2_trend == "estável"
        assert result.type2_slope == 0.0
