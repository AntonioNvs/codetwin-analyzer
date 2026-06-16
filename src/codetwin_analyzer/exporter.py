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
