"""
Testes unitários para o módulo codetwin_analyzer.exporter.
"""

import json
import csv
import pytest

from pathlib import Path
from codetwin_analyzer.exporter import CloneExporter
from codetwin_analyzer.metrics import CloneMetrics
from codetwin_analyzer.history import HistoryEntry
from codetwin_analyzer.parser import CloneFragment, ClonePair


@pytest.fixture
def sample_metrics():
    return CloneMetrics(
        total_clones=5,
        type1_count=3,
        type2_count=2,
        total_files_affected=4,
        total_lines_duplicated=120
    )


@pytest.fixture
def sample_history():
    return [
        HistoryEntry("sha1", "2024-01-01T10:00:00Z", "main", 1, 0, 1),
        HistoryEntry("sha2", "2024-01-02T10:00:00Z", "main", 2, 1, 3)
    ]


class TestCloneExporter:

    def test_to_json_serializes(self, sample_metrics, sample_clone_pairs, sample_history):
        exporter = CloneExporter()
        data = {
            "metrics": sample_metrics,
            "pairs": sample_clone_pairs,
            "history": sample_history
        }

        json_str = exporter.to_json(data)
        
        # Verifica se serializou sem erros e se é um JSON válido
        parsed = json.loads(json_str)
        assert parsed["metrics"]["total_clones"] == 5
        assert len(parsed["pairs"]) == 2
        assert len(parsed["history"]) == 2
        assert parsed["history"][0]["commit_sha"] == "sha1"

    def test_to_json_writes_to_file(self, tmp_path, sample_metrics):
        exporter = CloneExporter()
        out_file = tmp_path / "output.json"

        exporter.to_json(sample_metrics, output_path=out_file)

        assert out_file.exists()
        content = out_file.read_text(encoding="utf-8")
        parsed = json.loads(content)
        assert parsed["total_clones"] == 5

    def test_to_csv_has_correct_headers(self, tmp_path, sample_clone_pairs):
        exporter = CloneExporter()
        out_file = tmp_path / "output.csv"

        exporter.to_csv(sample_clone_pairs, out_file)

        assert out_file.exists()
        with open(out_file, "r", encoding="utf-8") as f:
            reader = csv.reader(f)
            headers = next(reader)
            
        expected_headers = [
            "file_a", "begin_line_a", "end_line_a",
            "file_b", "begin_line_b", "end_line_b",
            "tokens", "type"
        ]
        assert headers == expected_headers

    def test_to_csv_writes_all_rows(self, tmp_path, sample_clone_pairs):
        exporter = CloneExporter()
        out_file = tmp_path / "output.csv"

        exporter.to_csv(sample_clone_pairs, out_file)

        with open(out_file, "r", encoding="utf-8") as f:
            lines = f.readlines()
            
        # 1 linha de header + 2 linhas de dados
        assert len(lines) == 3

    def test_to_text_report_contains_summary(self, sample_metrics, sample_clone_pairs, sample_history):
        exporter = CloneExporter()
        report = exporter.to_text_report(sample_metrics, sample_clone_pairs, history=sample_history)

        assert "CODETWIN ANALYZER" in report
        assert "Total de clones detectados : 5" in report
        assert "Clones Tipo 1              : 3" in report
        assert "Clones Tipo 2              : 2" in report
        assert "TOP 10 ARQUIVOS MAIS CLONADOS" in report
        assert "DISTRIBUIÇÃO POR TIPO" in report
        assert "HISTÓRICO DE COMMITS" in report
        assert "sha1" in report
        assert "sha2" in report

    def test_to_html_report_valid(self, sample_metrics, sample_clone_pairs, sample_history):
        exporter = CloneExporter()
        report = exporter.to_html_report(sample_metrics, sample_clone_pairs, history=sample_history)

        assert report.startswith("<!DOCTYPE html>")
        assert "<html lang=\"pt-BR\">" in report
        assert "<head>" in report
        assert "<body>" in report
        assert "</html>" in report
        assert "Total de clones" in report
        assert "sha1" in report

    def test_metrics_to_csv(self, tmp_path, sample_metrics):
        exporter = CloneExporter()
        out_file = tmp_path / "metrics.csv"

        exporter.metrics_to_csv(sample_metrics, out_file)

        with open(out_file, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        assert len(rows) == 1
        assert rows[0]["total_clones"] == "5"
        assert rows[0]["type1_count"] == "3"
        assert rows[0]["type2_count"] == "2"
        assert rows[0]["total_files_affected"] == "4"
        assert rows[0]["total_lines_duplicated"] == "120"
