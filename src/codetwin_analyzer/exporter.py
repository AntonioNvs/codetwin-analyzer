"""
Módulo para exportação de resultados de análise de code clones em múltiplos formatos.

Suporta JSON, CSV, relatório texto (ASCII) e relatório HTML autocontido.
"""

import csv
import json
import dataclasses

from pathlib import Path
from typing import Any, List, Optional, Union

from codetwin_analyzer.parser import CloneFragment, ClonePair
from codetwin_analyzer.metrics import CloneMetrics
from codetwin_analyzer.history import HistoryEntry


# ---------------------------------------------------------------------------
# JSON Encoder customizado
# ---------------------------------------------------------------------------

class CloneJSONEncoder(json.JSONEncoder):
    """
    JSONEncoder customizado que serializa dataclasses do codetwin_analyzer.

    Suporta: CloneFragment, ClonePair, CloneMetrics, HistoryEntry.
    Qualquer outro dataclass também é serializado via dataclasses.asdict.
    """

    def default(self, obj: Any) -> Any:
        if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
            return dataclasses.asdict(obj)
        return super().default(obj)


# ---------------------------------------------------------------------------
# Classe principal
# ---------------------------------------------------------------------------

class CloneExporter:
    """Exporta resultados de análise de clones em múltiplos formatos."""

    # -----------------------------------------------------------------------
    # JSON
    # -----------------------------------------------------------------------

    def to_json(
        self,
        data: Any,
        output_path: Optional[Union[str, Path]] = None,
    ) -> str:
        """
        Serializa dados (dataclasses, listas, dicts) para JSON.

        Args:
            data: Objeto a serializar — dataclass, lista ou dict.
            output_path: Caminho do arquivo de saída (opcional).
                         Se None, retorna apenas a string JSON.

        Returns:
            String JSON serializada.
        """
        json_str = json.dumps(data, cls=CloneJSONEncoder, indent=2, ensure_ascii=False)

        if output_path is not None:
            Path(output_path).write_text(json_str, encoding="utf-8")

        return json_str

    # -----------------------------------------------------------------------
    # CSV de pares de clones
    # -----------------------------------------------------------------------

    def to_csv(
        self,
        clone_pairs: List[ClonePair],
        output_path: Union[str, Path],
    ) -> None:
        """
        Exporta a lista de ClonePairs para CSV.

        Colunas: file_a, begin_line_a, end_line_a, file_b, begin_line_b,
                 end_line_b, tokens, type.

        Args:
            clone_pairs: Lista de pares de clones a exportar.
            output_path: Caminho do arquivo CSV de saída.
        """
        fieldnames = [
            "file_a", "begin_line_a", "end_line_a",
            "file_b", "begin_line_b", "end_line_b",
            "tokens", "type",
        ]

        with open(output_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()

            for pair in clone_pairs:
                writer.writerow({
                    "file_a": pair.fragment_a.source_file,
                    "begin_line_a": pair.fragment_a.begin_line,
                    "end_line_a": pair.fragment_a.end_line,
                    "file_b": pair.fragment_b.source_file,
                    "begin_line_b": pair.fragment_b.begin_line,
                    "end_line_b": pair.fragment_b.end_line,
                    "tokens": pair.shared_tokens,
                    "type": pair.type or "",
                })

    # -----------------------------------------------------------------------
    # Relatório texto (ASCII)
    # -----------------------------------------------------------------------

    def to_text_report(
        self,
        metrics: CloneMetrics,
        clone_pairs: List[ClonePair],
        history: Optional[List[HistoryEntry]] = None,
        output_path: Optional[Union[str, Path]] = None,
    ) -> str:
        """
        Gera um relatório texto formatado em ASCII com:
        (1) sumário de métricas, (2) tabela top-10 arquivos, (3) distribuição
        por tipo, (4) seção de histórico se fornecida.

        Args:
            metrics: Objeto CloneMetrics com contagens gerais.
            clone_pairs: Lista de pares de clones para calcular top arquivos.
            history: Lista opcional de HistoryEntry para a seção de histórico.
            output_path: Caminho do arquivo de saída (opcional).

        Returns:
            String do relatório gerado.
        """
        sep = "=" * 60
        lines: List[str] = []

        # 1. Sumário
        lines.append(sep)
        lines.append("  CODETWIN ANALYZER — RELATÓRIO DE CLONES")
        lines.append(sep)
        lines.append(f"  Total de clones detectados : {metrics.total_clones}")
        lines.append(f"  Clones Tipo 1              : {metrics.type1_count}")
        lines.append(f"  Clones Tipo 2              : {metrics.type2_count}")
        lines.append(f"  Arquivos afetados          : {metrics.total_files_affected}")
        lines.append(f"  Linhas duplicadas          : {metrics.total_lines_duplicated}")
        lines.append("")

        # 2. Tabela top-10 arquivos
        from codetwin_analyzer.metrics import most_cloned_files
        top_files = most_cloned_files(clone_pairs, top_n=10)

        lines.append("-" * 60)
        lines.append("  TOP 10 ARQUIVOS MAIS CLONADOS")
        lines.append("-" * 60)
        if top_files:
            lines.append(f"  {'Arquivo':<45} {'Clones':>6}")
            lines.append("  " + "-" * 53)
            for fname, count in top_files:
                short = fname[-43:] if len(fname) > 43 else fname
                lines.append(f"  {short:<45} {count:>6}")
        else:
            lines.append("  (nenhum arquivo com clones detectado)")
        lines.append("")

        # 3. Distribuição por tipo
        lines.append("-" * 60)
        lines.append("  DISTRIBUIÇÃO POR TIPO")
        lines.append("-" * 60)
        total = metrics.total_clones or 1
        t1_pct = metrics.type1_count / total * 100
        t2_pct = metrics.type2_count / total * 100
        other = total - metrics.type1_count - metrics.type2_count
        other_pct = other / total * 100
        lines.append(f"  Tipo 1 (exatos)       : {metrics.type1_count:>4}  ({t1_pct:.1f}%)")
        lines.append(f"  Tipo 2 (estruturais)  : {metrics.type2_count:>4}  ({t2_pct:.1f}%)")
        lines.append(f"  Tipo 3/4 (outros)     : {other:>4}  ({other_pct:.1f}%)")
        lines.append("")

        # 4. Seção de histórico (opcional)
        if history:
            lines.append("-" * 60)
            lines.append("  HISTÓRICO DE COMMITS (últimos registros)")
            lines.append("-" * 60)
            lines.append(f"  {'Commit':<10} {'Timestamp':<25} {'T1':>4} {'T2':>4} {'Total':>6}")
            lines.append("  " + "-" * 53)
            for entry in history[-10:]:
                sha_short = entry.commit_sha[:8] if entry.commit_sha else "--------"
                ts = entry.timestamp[:19] if entry.timestamp else "—"
                lines.append(
                    f"  {sha_short:<10} {ts:<25} "
                    f"{entry.type1_count:>4} {entry.type2_count:>4} {entry.total_clones:>6}"
                )
            lines.append("")

        lines.append(sep)
        report = "\n".join(lines)

        if output_path is not None:
            Path(output_path).write_text(report, encoding="utf-8")

        return report

    # -----------------------------------------------------------------------
    # CSV de métricas (uma linha)
    # -----------------------------------------------------------------------

    def metrics_to_csv(
        self,
        metrics: CloneMetrics,
        output_path: Union[str, Path],
    ) -> None:
        """
        Exporta os campos de CloneMetrics para um CSV de uma única linha de dados.

        Args:
            metrics: Objeto CloneMetrics a exportar.
            output_path: Caminho do arquivo CSV de saída.
        """
        fieldnames = [
            "total_clones", "type1_count", "type2_count",
            "total_files_affected", "total_lines_duplicated",
        ]

        with open(output_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerow({
                "total_clones": metrics.total_clones,
                "type1_count": metrics.type1_count,
                "type2_count": metrics.type2_count,
                "total_files_affected": metrics.total_files_affected,
                "total_lines_duplicated": metrics.total_lines_duplicated,
            })
