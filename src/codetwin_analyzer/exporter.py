"""
Módulo para exportação de resultados de análise de code clones em múltiplos formatos.

Suporta JSON, CSV, relatório texto (ASCII) e relatório HTML autocontido.
"""

import csv
import json
import dataclasses

from pathlib import Path
from typing import Any, List, Optional, Union

from codetwin_analyzer.parser import ClonePair
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

    # -----------------------------------------------------------------------
    # Relatório HTML
    # -----------------------------------------------------------------------

    def to_html_report(
        self,
        metrics: CloneMetrics,
        clone_pairs: List[ClonePair],
        history: Optional[List[HistoryEntry]] = None,
        output_path: Optional[Union[str, Path]] = None,
    ) -> str:
        """
        Gera um relatório HTML autocontido com CSS inline.

        Conteúdo:
        (1) tabela de sumário com CSS inline,
        (2) lista dos top clones com snippets em <pre>,
        (3) seção de timeline de histórico (se fornecida).

        Sem dependências externas (sem JS, sem CDN CSS).

        Args:
            metrics: Objeto CloneMetrics com contagens gerais.
            clone_pairs: Lista de pares de clones para exibir snippets.
            history: Lista opcional de HistoryEntry para a seção de timeline.
            output_path: Caminho do arquivo HTML de saída (opcional).

        Returns:
            String HTML gerada.
        """
        from codetwin_analyzer.metrics import most_cloned_files
        import html as html_lib

        top_files = most_cloned_files(clone_pairs, top_n=10)

        css = (
            "body{font-family:Arial,sans-serif;margin:2rem;color:#222;background:#f9f9f9}"
            "h1{color:#2c3e50;border-bottom:2px solid #2c3e50;padding-bottom:.4rem}"
            "h2{color:#34495e;margin-top:2rem}"
            "table{border-collapse:collapse;width:100%;max-width:800px}"
            "th{background:#2c3e50;color:#fff;padding:.5rem 1rem;text-align:left}"
            "td{padding:.4rem 1rem;border-bottom:1px solid #ddd}"
            "tr:nth-child(even) td{background:#f0f0f0}"
            "pre{background:#1e1e1e;color:#d4d4d4;padding:1rem;border-radius:4px;"
            "overflow-x:auto;font-size:.85rem;max-height:200px}"
            ".badge{display:inline-block;padding:.2rem .6rem;border-radius:3px;"
            "font-size:.8rem;font-weight:bold}"
            ".t1{background:#27ae60;color:#fff}.t2{background:#2980b9;color:#fff}"
            ".t34{background:#7f8c8d;color:#fff}"
            ".clone-item{background:#fff;border:1px solid #ddd;border-radius:4px;"
            "padding:1rem;margin-bottom:1rem}"
        )

        def _badge(clone_type: Optional[str]) -> str:
            cls = {"Tipo 1": "t1", "Tipo 2": "t2"}.get(clone_type or "", "t34")
            label = clone_type or "Tipo 3/4"
            return f'<span class="badge {cls}">{html_lib.escape(label)}</span>'

        summary_rows = [
            ("Total de clones", metrics.total_clones),
            ("Clones Tipo 1", metrics.type1_count),
            ("Clones Tipo 2", metrics.type2_count),
            ("Arquivos afetados", metrics.total_files_affected),
            ("Linhas duplicadas", metrics.total_lines_duplicated),
        ]
        summary_html = "<table><tr><th>M\u00e9trica</th><th>Valor</th></tr>"
        for label, val in summary_rows:
            summary_html += f"<tr><td>{html_lib.escape(str(label))}</td><td>{val}</td></tr>"
        summary_html += "</table>"

        top_html = "<table><tr><th>Arquivo</th><th>Clones</th></tr>"
        for fname, cnt in top_files:
            top_html += f"<tr><td>{html_lib.escape(fname)}</td><td>{cnt}</td></tr>"
        if not top_files:
            top_html += "<tr><td colspan='2'>(nenhum)</td></tr>"
        top_html += "</table>"

        clones_html = ""
        for pair in clone_pairs[:20]:
            snippet = html_lib.escape(pair.fragment_a.code_snippet or "")
            fa = html_lib.escape(pair.fragment_a.source_file)
            fb = html_lib.escape(pair.fragment_b.source_file)
            clones_html += (
                f'<div class="clone-item">'
                f"{_badge(pair.type)} "
                f"<strong>{fa}</strong>:{pair.fragment_a.begin_line}&ndash;{pair.fragment_a.end_line}"
                f" &harr; <strong>{fb}</strong>:{pair.fragment_b.begin_line}&ndash;{pair.fragment_b.end_line}"
                f"<pre>{snippet}</pre></div>"
            )

        history_html = ""
        if history:
            history_html = "<h2>Timeline de Commits</h2>"
            history_html += (
                "<table><tr><th>Commit</th><th>Timestamp</th>"
                "<th>Tipo 1</th><th>Tipo 2</th><th>Total</th></tr>"
            )
            for entry in history:
                sha = html_lib.escape(entry.commit_sha[:8] if entry.commit_sha else "\u2014")
                ts = html_lib.escape(entry.timestamp[:19] if entry.timestamp else "\u2014")
                history_html += (
                    f"<tr><td>{sha}</td><td>{ts}</td>"
                    f"<td>{entry.type1_count}</td>"
                    f"<td>{entry.type2_count}</td>"
                    f"<td>{entry.total_clones}</td></tr>"
                )
            history_html += "</table>"

        html_content = (
            "<!DOCTYPE html>\n"
            "<html lang=\"pt-BR\">\n"
            "<head>\n"
            "  <meta charset=\"UTF-8\">\n"
            "  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\">\n"
            "  <title>CodeTwin Analyzer \u2014 Relat\u00f3rio de Clones</title>\n"
            f"  <style>{css}</style>\n"
            "</head>\n"
            "<body>\n"
            "  <h1>CodeTwin Analyzer \u2014 Relat\u00f3rio de Clones</h1>\n"
            "  <h2>Sum\u00e1rio</h2>\n"
            f"  {summary_html}\n"
            "  <h2>Top 10 Arquivos Mais Clonados</h2>\n"
            f"  {top_html}\n"
            "  <h2>Clones Detectados</h2>\n"
            f"  {clones_html if clones_html else '<p>(nenhum clone detectado)</p>'}\n"
            f"  {history_html}\n"
            "</body>\n"
            "</html>"
        )

        if output_path is not None:
            Path(output_path).write_text(html_content, encoding="utf-8")

        return html_content
