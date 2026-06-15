# Plano de Implementação — CodeTwin Analyzer (52 Commits)

## Contexto

Trabalho prático de Manutenção e Evolução de Software. Desenvolvimento de ferramenta CLI para detecção de code clones Tipos 1 e 2 usando GitHub API, SEART, python-fire e PMD CPD.

**Restrições do TP:**

- Mínimo 50 commits (total: 52)
- Mínimo 10 testes unitários
- GitHub Actions CI configurado
- README com 6+ seções obrigatórias
- 3 links de entrega (repo, testes, Actions)

**Distribuição e prazos:**

| Pessoa      | Tarefas     | %    | Linhas estimadas | Prazo            |
| ----------- | ----------- | ---- | ---------------- | ---------------- |
| Antônio    | 1–21 (21)  | ~40% | ~735             | 13/jun (amanhã) |
| Bernardo    | 22–32 (11) | ~21% | ~715             | 16/jun (terça)  |
| João Lucas | 33–42 (10) | ~19% | ~730             | 18/jun (quinta)  |
| Raphael     | 43–52 (10) | ~19% | ~720             | 20/jun (sábado) |

As fases são **sequenciais**: cada pessoa só começa quando a anterior terminar todas as suas tarefas.

---

## Estrutura de diretórios esperada ao final

```
codetwin-analyzer/
├── .github/workflows/ci.yml
├── src/codetwin_analyzer/
│   ├── __init__.py
│   ├── cli.py
│   ├── github_client.py
│   ├── seart_client.py
│   ├── cpd_runner.py
│   ├── parser.py
│   ├── metrics.py
│   ├── history.py
│   ├── exporter.py
│   └── utils.py
├── tests/
│   ├── __init__.py
│   ├── conftest.py
│   ├── test_utils.py
│   ├── test_github_client.py
│   ├── test_seart_client.py
│   ├── test_cpd_runner.py
│   ├── test_parser.py
│   ├── test_metrics.py
│   ├── test_history.py
│   ├── test_exporter.py
│   ├── test_cli.py
│   └── test_integration.py
├── .gitignore
├── requirements.txt
├── requirements-dev.txt
├── setup.py
├── PLAN.md
└── README.md
```

---

## Fase 1 — Antônio (Tarefas 1–21): Fundação e Módulos Core

### 1. `chore: inicializa estrutura do projeto com gitignore e requirements`

**Arquivos:**

- `.gitignore` — template Python (`__pycache__/`, `.venv/`, `*.pyc`, `.pytest_cache/`, `dist/`, `*.egg-info/`, `build/`, `.coverage`, `htmlcov/`)
- `requirements.txt` — `requests`, `python-fire`, `pyyaml`
- Diretórios vazios: `src/codetwin_analyzer/` e `tests/`

### 2. `chore: cria setup.py com configuracao basica do pacote`

**Arquivos:**

- `setup.py` — `setuptools.setup()` com `name="codetwin-analyzer"`, `version="0.1.0"`, `package_dir={"": "src"}`, `packages=find_packages(where="src")`, `install_requires` lido de requirements.txt, `python_requires=">=3.9"`

### 3. `feat: adiciona modulo __init__ com metadados do pacote`

**Arquivos:**

- `src/codetwin_analyzer/__init__.py` — constantes `__version__`, `__author__`, `__all__`, docstring
- `tests/__init__.py` — arquivo vazio

### 4. `feat: implementa modulo utils com funcoes auxiliares de filesystem`

**Arquivos:**

- `src/codetwin_analyzer/utils.py` — funções:
  - `sanitize_repo_name(url)` — extrai `owner/repo` de URL do GitHub (https, git suffix)
  - `ensure_dir(path)` — cria diretórios recursivamente
  - `temp_dir()` — context manager com `tempfile.TemporaryDirectory`
  - `find_files(directory, extensions)` — varre diretório e retorna paths filtrando por extensões

### 5. `feat: implementa github_client com autenticacao via token`

**Arquivos:**

- `src/codetwin_analyzer/github_client.py` — classe `GitHubClient`:
  - Construtor: `token` (default `$GITHUB_TOKEN`), `self.session = requests.Session()` com headers `Authorization`, `Accept`
  - `_get(url, params)` — GET com tratamento de erro, levanta `GitHubAPIError` em não-200
  - `get_default_branch(owner, repo)` — `GET /repos/{owner}/{repo}`, retorna `default_branch`
  - `get_repo_metadata(owner, repo)` — retorna dict com stars, forks, language, created_at, updated_at, size, open_issues, license

### 6. `feat: adiciona download de repositorio ao github_client`

**Arquivos:**

- `src/codetwin_analyzer/github_client.py` — adicionar métodos:
  - `download_repository(owner, repo, destination)` — `GET /repos/{owner}/{repo}/zipball/{branch}`, baixa ZIP com stream, extrai com `zipfile.ZipFile`
  - `get_branches(owner, repo)` — `GET /repos/{owner}/{repo}/branches`, retorna lista de nomes
  - `get_commits(owner, repo, since=None, until=None)` — `GET /repos/{owner}/{repo}/commits`, paginação, retorna lista de dicts com sha, date, message, author

### 7. `feat: implementa seart_client com busca basica de repositorios`

**Arquivos:**

- `src/codetwin_analyzer/seart_client.py` — classe `SEARTClient`:
  - Construtor: `base_url = "https://seart-ghs.si.usi.ch/api"`, `self.session = requests.Session()`
  - `search_repositories(language, min_stars=0, max_results=100)` — chama endpoint de busca SEART, retorna lista de `full_name`

### 8. `feat: adiciona filtros avancados e retry ao seart_client`

**Arquivos:**

- `src/codetwin_analyzer/seart_client.py` — estender `search_repositories`:
  - Parâmetros adicionais: `created_after`, `created_before`, `min_size_kb`, `max_size_kb`, `license_filter`
  - Retry com backoff exponencial (max 3 tentativas, `time.sleep`)
  - Tratamento de erros HTTP com mensagens descritivas

### 9. `feat: implementa cpd_runner para execucao do PMD CPD`

**Arquivos:**

- `src/codetwin_analyzer/cpd_runner.py` — classe `CPDRunner`:
  - Construtor: `pmd_path` (default `shutil.which("pmd")`)
  - `run_cpd(source_dir, output_file, min_tokens=100, language=None)` — `subprocess.run` com args `--minimum-tokens`, `--language`, `--files`, `--format xml`, `--filelist` (ou diretório direto). Redireciona stdout para output_file.
  - Exceção `CPDExecutionError` em exit code != 0

### 10. `feat: adiciona deteccao automatica de linguagem ao cpd_runner`

**Arquivos:**

- `src/codetwin_analyzer/cpd_runner.py` — adicionar:
  - `detect_language(source_dir)` — mapeia extensões (`*.py` → `python`, `*.java` → `java`, `*.js` → `javascript`, `*.cs` → `cs`), retorna a linguagem mais comum
  - `run_with_auto_detect(source_dir, output_file, min_tokens=100)` — encadeia detect + run
  - Validação: se PMD não instalado, levanta erro com mensagem amigável

### 11. `feat: implementa parser de resultados XML do CPD`

**Arquivos:**

- `src/codetwin_analyzer/parser.py`:
  - Dataclass `CloneFragment`: `source_file`, `begin_line`, `end_line`, `tokens`, `code_snippet`
  - `parse_cpd_xml(file_path)` — usa `xml.etree.ElementTree`, extrai `<duplication>` elements, retorna `list[CloneFragment]`

### 12. `feat: adiciona agrupamento e classificacao de clones ao parser`

**Arquivos:**

- `src/codetwin_analyzer/parser.py` — adicionar:
  - Dataclass `ClonePair`: `fragment_a`, `fragment_b`, `shared_tokens`, `type` (str, inicial None)
  - `group_into_pairs(fragments)` — agrupa fragmentos em pares pelo grupo de duplicação do XML
  - `classify_clone_type(pair)` — Tipo 1: tokens idênticos; Tipo 2: normaliza identificadores e literais, compara sequências normalizadas

### 13. `feat: implementa modulo metrics com contagem de clones por tipo`

**Arquivos:**

- `src/codetwin_analyzer/metrics.py`:
  - Dataclass `CloneMetrics`: `total_clones`, `type1_count`, `type2_count`, `total_files_affected`, `total_lines_duplicated`
  - `compute_clone_counts(clone_pairs)` — itera pares, classifica cada um, acumula estatísticas e retorna `CloneMetrics`

### 14. `feat: adiciona metricas de frequencia ao modulo metrics`

**Arquivos:**

- `src/codetwin_analyzer/metrics.py` — adicionar:
  - `most_cloned_files(clone_pairs, top_n=10)` — conta aparições de cada arquivo, retorna top N
  - `most_cloned_functions(clone_pairs, top_n=10)` — regex `def\s+(\w+)|function\s+(\w+)` nos snippets
  - `clone_density(clone_pairs, total_lines)` — razão linhas duplicadas / total de linhas

### 15. `feat: cria CLI base com python-fire e comando analyze`

**Arquivos:**

- `src/codetwin_analyzer/cli.py` — classe `CodeTwinCLI`:
  - `analyze(repo_url, min_tokens=100, language=None, output=None)` — orquestra: sanitize URL → GitHubClient.download_repository → CPDRunner.run_with_auto_detect → parse_cpd_xml → print sumário
  - `def main():` — `fire.Fire(CodeTwinCLI)`
  - `if __name__ == "__main__": main()`

### 16. `feat: adiciona comando search a CLI`

**Arquivos:**

- `src/codetwin_analyzer/cli.py` — adicionar método:
  - `search(language, min_stars=10, max_results=10, analyze=False)` — usa SEARTClient, imprime lista formatada. Se `analyze=True`, executa pipeline em cada repo encontrado

### 17. `feat: adiciona comando metrics a CLI`

**Arquivos:**

- `src/codetwin_analyzer/cli.py` — adicionar método:
  - `metrics(repo_url, min_tokens=100)` — executa pipeline similar ao analyze mas exibe métricas formatadas: contagem por tipo, top arquivos, densidade

### 18. `feat: adiciona tratamento de erros e logging basico a CLI`

**Arquivos:**

- `src/codetwin_analyzer/cli.py` — adicionar:
  - Configuração de `logging`: console handler (INFO) + file handler (DEBUG)
  - Flags `--verbose` (DEBUG) e `--quiet` (WARNING)
  - Try/except para `GitHubAPIError`, `CPDExecutionError`, `requests.ConnectionError`, `requests.Timeout` com mensagens amigáveis

### 19. `test: cria conftest.py com fixtures compartilhadas`

**Arquivos:**

- `tests/conftest.py` — fixtures pytest:
  - `sample_cpd_xml` — fixture `tmp_path` que escreve XML CPD válido com 3 duplicações (2 Tipo 1, 1 Tipo 2)
  - `sample_clone_fragments` — retorna lista hardcoded de `CloneFragment`
  - `sample_clone_pairs` — retorna lista hardcoded de `ClonePair`
  - `mock_github_session` — monkeypatch de `requests.Session.get` com mock configurável

### 20. `test: implementa testes unitarios para modulo utils`

**Arquivos:**

- `tests/test_utils.py` — classe `TestUtils`:
  - `test_sanitize_repo_name_https` — `https://github.com/owner/repo` → `owner/repo`
  - `test_sanitize_repo_name_git_suffix` — `owner/repo.git` → `owner/repo`
  - `test_ensure_dir_creates_nested` — `tmp_path`, cria subdiretórios
  - `test_find_files_filters_by_extension` — cria arquivos `.py` e `.txt`, verifica filtro
  - `test_find_files_empty_dir` — retorna lista vazia
  - `test_temp_dir_cleanup` — diretório removido após saída do context manager

### 21. `test: implementa testes unitarios para modulo parser`

**Arquivos:**

- `tests/test_parser.py` — classe `TestParser` (9 testes implementados):
  - `test_parse_cpd_xml_valid` — verifica número correto de fragmentos
  - `test_parse_cpd_xml_with_namespace` — **suporte a namespace do PMD 7.x** (`xmlns="https://pmd-code.org/schema/cpd-report"`)
  - `test_parse_cpd_xml_empty` — XML sem duplicações → lista vazia
  - `test_parse_cpd_xml_malformed` — XML inválido → `ParseError`
  - `test_classify_type1` — código idêntico (arquivos reais em `tmp_path`) → Tipo 1
  - `test_classify_type2_renamed_identifiers` — estrutura igual, nomes diferentes (arquivos reais) → Tipo 2
  - `test_classify_with_unreadable_file` — arquivos inacessíveis → Tipo 3/4 (fallback conservador)
  - `test_group_into_pairs` — verifica agrupamento correto
  - `test_type_statistics` — verifica contagem por tipo (Tipo 3/4 com arquivos reais)

> ⚠️ **Atenção:** `classify_clone_type` agora lê arquivos reais do disco via `extract_code_from_file`. Testes que usam `CloneFragment` com paths fictícios sempre resultam em `"Tipo 3/4"`. SEMPRE use `tmp_path` e escreva arquivos reais ao testar classificação de clones.

---

## Fase 2 — Bernardo (Tarefas 22–32): Testes e Métricas Avançadas

### 22. `test: implementa testes unitarios para github_client`

**Arquivos:**

- `tests/test_github_client.py` — classe `TestGitHubClient`:
  - `test_init_with_token` — verifica headers Authorization
  - `test_init_without_token_uses_env` — monkeypatch `GITHUB_TOKEN`
  - `test_get_success` — mock retorna 200 com JSON
  - `test_get_http_error` — mock 404, assert `GitHubAPIError`
  - `test_get_default_branch` — mock response com `default_branch: "main"`
  - `test_get_repo_metadata_returns_expected_keys` — verifica campos do dict
  - `test_download_repository` — mock ZIP download, verifica extração

> ℹ️ A fixture `mock_github_session` (monkeypatch de `requests.Session.get`) já existe em `conftest.py`. Reutilize-a nos testes.

### 23. `test: implementa testes unitarios para seart_client`

**Arquivos:**

- `tests/test_seart_client.py` — classe `TestSEARTClient`:
  - `test_search_repositories_basic` — mock HTTP, verifica parsing
  - `test_search_repositories_with_filters` — verifica query params enviados
  - `test_search_repositories_empty` — sem resultados → lista vazia
  - `test_search_retry_on_500` — 3 tentativas antes de erro
  - `test_get_repository_details` — mock de detalhes
  - `test_rate_limit_retry` — 429 → retry com backoff

### 24. `test: implementa testes unitarios para cpd_runner`

**Arquivos:**

- `tests/test_cpd_runner.py` — classe `TestCPDRunner`:
  - `test_run_cpd_success` — mock `subprocess.run` returncode 0
  - `test_run_cpd_failure_raises_error` — mock returncode != 0
  - `test_detect_language_python` — temp dir com `.py` → `python`
  - `test_detect_language_mixed` — maioria `.java` → `java`
  - `test_pmd_not_installed` — `shutil.which` retorna None → erro informativo
  - `test_run_with_auto_detect_chains_correctly` — integração detect + run

### 25. `test: implementa testes completos para modulo metrics`

**Arquivos:**

- `tests/test_metrics.py` — classe `TestMetrics`:
  - `test_compute_clone_counts_type1_only` — verifica contagem
  - `test_compute_clone_counts_type2_only` — verifica contagem
  - `test_compute_clone_counts_mixed` — verifica ambos
  - `test_most_cloned_files_ordering` — ordenação correta
  - `test_most_cloned_functions` — extração de nomes de função
  - `test_clone_density` — cálculo correto da densidade
  - `test_empty_input_handling` — listas vazias não quebram

> ⚠️ `compute_clone_counts` chama `classify_clone_type` que exige **arquivos reais em disco**. Para testar contagem de Tipo 1 e Tipo 2, crie arquivos em `tmp_path` com os snippets corretos e aponte os `CloneFragment.source_file` para esses paths. Paths fictícios sempre resultam em `"Tipo 3/4"`.

### 26. `feat: adiciona estatisticas sumarias ao modulo metrics`

**Arquivos:**

- `src/codetwin_analyzer/metrics.py` — adicionar:
  - `statistical_summary(clone_pairs)` — dict com: `mean_clone_size`, `median_clone_size`, `stddev_clone_size`, `min_clone_size`, `max_clone_size`, `total_unique_files`, `type1_ratio`, `type2_ratio`. Usa módulo `statistics`. Trata lista vazia.

### 27. `feat: adiciona matriz de similaridade entre arquivos ao metrics`

**Arquivos:**

- `src/codetwin_analyzer/metrics.py` — adicionar:
  - `inter_file_similarity(clone_pairs)` — para cada par de arquivos, score: `(2 * duplicated_lines) / (total_A + total_B)`
  - `token_overlap_matrix(clone_pairs)` — similaridade Jaccard entre conjuntos de tokens
  - `repository_clone_index(clone_pairs, total_files, total_lines)` — índice único (0 a 1)

> 📝 **Escopo opcional:** Tasks 26–30 são métricas avançadas que estendem o que `most_cloned_files` e `clone_density` já cobrem. Se o prazo apertar, podem ser adiadas sem quebrar a CLI.

### 28. `test: implementa testes para metricas avancadas`

**Arquivos:**

- `tests/test_metrics.py` — estender:
  - `test_statistical_summary` — verifica média, mediana, desvio
  - `test_statistical_summary_empty` — lista vazia → valores padrão
  - `test_statistical_summary_single` — um clone → estatísticas corretas
  - `test_inter_file_similarity` — verifica scores
  - `test_repository_clone_index` — verifica fórmula
  - `test_token_overlap_matrix` — verifica Jaccard

### 29. `feat: adiciona metricas de clones por nivel de arquivo`

**Arquivos:**

- `src/codetwin_analyzer/metrics.py` — adicionar:
  - `file_level_clone_matrix(clone_pairs)` — matriz NxN como nested dict
  - `clone_coverage_per_file(clone_pairs)` — % linhas duplicadas por arquivo
  - `top_clone_files_by_type(clone_pairs)` — rankings separados Tipo 1 e Tipo 2

### 30. `test: implementa testes para metricas de arquivo`

**Arquivos:**

- `tests/test_metrics.py` — estender:
  - `test_file_level_clone_matrix` — verifica estrutura da matriz
  - `test_clone_coverage_per_file` — verifica porcentagens
  - `test_top_clone_files_by_type` — rankings separados corretos
  - `test_clone_coverage_boundary` — cobre 0% e 100%

### 31. `ci: configura GitHub Actions com testes e lint`

**Arquivos:**

- `.github/workflows/ci.yml` — job único `test`:
  - `ubuntu-latest`, Python 3.10
  - Steps: checkout, setup-python, `pip install -r requirements.txt && pip install -e . && pip install pytest flake8`, `flake8 src/`, `pytest tests/ -v --tb=short`
  - Triggers: `push` e `pull_request` para `main`

> ℹ️ O PMD **não** precisa ser instalado no ambiente de CI. Os testes de `cpd_runner` mockam `subprocess.run` e os demais módulos (`parser`, `metrics`, `utils`) não dependem do PMD.

### 32. `test: implementa testes de integracao para a CLI`

**Arquivos:**

- `tests/test_cli.py` — classe `TestCLI`:
  - `test_analyze_with_mock` — mock GitHubClient, CPD runner, verifica saída
  - `test_analyze_invalid_url` — URL inválida → mensagem de erro
  - `test_search_prints_results` — mock SEARTClient, verifica output
  - `test_metrics_command` — mock pipeline, verifica métricas no output
  - `test_verbose_flag` — flag `--verbose` ativa debug

---

## Fase 3 — João Lucas (Tarefas 33–42): Histórico e Exportação

### 33. `feat: implementa modulo history com estrutura base de rastreamento`

**Arquivos:**

- `src/codetwin_analyzer/history.py`:
  - Dataclass `HistoryEntry`: `commit_sha`, `timestamp`, `branch`, `type1_count`, `type2_count`, `total_clones`
  - Classe `CloneHistory`: construtor recebe `GitHubClient` instance
  - `_run_cpd_on_commit(owner, repo, commit_sha, temp_dir)` — baixa repo no commit específico, roda CPD, retorna contagens de clones

### 34. `feat: adiciona rastreamento de clones por intervalo de commits`

**Arquivos:**

- `src/codetwin_analyzer/history.py` — adicionar:
  - `track_commit_range(owner, repo, since=None, until=None, max_commits=50)` — (1) busca commits via `GitHubClient.get_commits`, (2) para cada commit baixa repo e roda CPD, (3) armazena `HistoryEntry` em `self.entries`, (4) log de progresso, (5) trata commits sem arquivos analisáveis (pula, registra zero clones)

### 35. `feat: adiciona analise de clones por branch ao history`

**Arquivos:**

- `src/codetwin_analyzer/history.py` — adicionar:
  - Dataclass `BranchComparison`: branch names, per-branch clone counts, diff de clone pairs
  - `compare_branches(owner, repo, branches)` — detecta clones na ponta de cada branch, compara
  - `track_default_branch_history(owner, repo, depth=20)` — analisa últimos N commits da branch default

### 36. `feat: implementa analise de tendencia temporal de clones`

**Arquivos:**

- `src/codetwin_analyzer/history.py` — adicionar:
  - Dataclass `TrendResult`: `type1_trend`, `type2_trend` (str), `type1_slope`, `type2_slope` (float)
  - `to_time_series()` — converte entries em lista `(timestamp, type1, type2)` ordenada
  - `compute_trend()` — regressão linear simples (cálculo manual com somatórios), retorna `TrendResult`

### 37. `test: implementa testes para modulo history`

**Arquivos:**

- `tests/test_history.py` — classe `TestCloneHistory`:
  - `test_track_commit_range_empty` — sem commits → lista vazia
  - `test_track_commit_range_with_mock` — mock `get_commits` e `download_repository`
  - `test_compare_branches_same_code` — código idêntico em duas branches
  - `test_to_time_series_ordering` — ordenação cronológica
  - `test_compute_trend_increasing` — entries com contagem crescente
  - `test_compute_trend_decreasing` — entries com contagem decrescente
  - `test_compute_trend_stable` — entries com contagem constante

### 38. `feat: implementa modulo exporter com exportacao JSON e CSV`

**Arquivos:**

- `src/codetwin_analyzer/exporter.py` — classe `CloneExporter`:
  - `CloneJSONEncoder` — `json.JSONEncoder` customizado para dataclasses (CloneFragment, ClonePair, CloneMetrics, HistoryEntry)
  - `to_json(data, output_path=None)` — serializa para string ou arquivo
  - `to_csv(clone_pairs, output_path)` — colunas: `file_a, begin_line_a, end_line_a, file_b, begin_line_b, end_line_b, tokens, type`. Usa `csv.DictWriter`.

### 39. `feat: adiciona exportacao de relatorios formatados ao exporter`

**Arquivos:**

- `src/codetwin_analyzer/exporter.py` — adicionar:
  - `to_text_report(metrics, clone_pairs, history=None, output_path=None)` — relatório texto com: (1) sumário, (2) tabela ASCII top 10 arquivos, (3) distribuição por tipo, (4) seção de histórico se existir
  - `metrics_to_csv(metrics, output_path)` — CSV de uma linha com campos do CloneMetrics

### 40. `feat: adiciona exportacao de relatorio HTML ao exporter`

**Arquivos:**

- `src/codetwin_analyzer/exporter.py` — adicionar:
  - `to_html_report(metrics, clone_pairs, history=None, output_path=None)` — HTML autocontido: (1) tabela de sumário com CSS inline, (2) lista de top clones com snippets formatados em `<pre>`, (3) seção de timeline se history existir. Sem dependências externas (sem JS, sem CDN CSS).

### 41. `feat: integra modulos history e exporter a CLI`

**Arquivos:**

- `src/codetwin_analyzer/cli.py` — modificar:
  - Adicionar comando `history(repo_url, depth=20)` — executa `CloneHistory.track_default_branch_history` e exibe tendência
  - Adicionar `--format` (choices: json/csv/text/html) e `--output` ao `analyze`
  - Se `--output` especificado, usa `CloneExporter`; senão, print stdout
  - Adicionar `--history` ao `analyze` (aciona rastreamento de histórico)

### 42. `test: implementa testes para modulo exporter`

**Arquivos:**

- `tests/test_exporter.py` — classe `TestCloneExporter`:
  - `test_to_json_serializes` — verifica estrutura JSON
  - `test_to_json_writes_to_file` — `tmp_path`
  - `test_to_csv_has_correct_headers` — verifica header row
  - `test_to_csv_writes_all_rows` — verifica número de linhas
  - `test_to_text_report_contains_summary` — verifica conteúdo
  - `test_to_html_report_valid` — verifica `<!DOCTYPE`, `<html>`, `<body>`
  - `test_metrics_to_csv` — verifica linha única

---

## Fase 4 — Raphael (Tarefas 43–52): Polimento, Documentação e Entrega

### 43. `feat: implementa comando report que combina analise e historico`

**Arquivos:**

- `src/codetwin_analyzer/cli.py` — adicionar método:
  - `report(repo_url, min_tokens=100, with_history=True, format="text", output=None)` — pipeline completo: download → CPD → parse → metrics → history (se with_history) → export. Recuperação de erros por etapa (se uma etapa falha, reporta o que sucedeu e o que falhou).

### 44. `feat: adiciona logging colorido e barra de progresso a CLI`

**Arquivos:**

- `src/codetwin_analyzer/cli.py` — melhorar:
  - Cores ANSI no console handler (INFO=azul, WARNING=amarelo, ERROR=vermelho)
  - `--progress` — indicador textual de etapas (1/5 download, 2/5 cpd, ...)
  - Mensagens de erro refinadas com sugestões de recuperação

### 45. `feat: adiciona suporte a multiplas linguagens ao cpd_runner`

**Arquivos:**

- `src/codetwin_analyzer/cpd_runner.py` — estender `detect_language`:
  - Mapeamento completo: `py→python`, `java→java`, `js→javascript`, `cs→cs`, `cpp/c++/hpp→cpp`, `rb→ruby`, `go→go`, `kt→kotlin`, `swift→swift`, `php→php`, `r→r`
  - Testar todas as extensões em `tests/test_cpd_runner.py`

### 46. `test: implementa testes de cobertura para cpd_runner multi-linguagem`

**Arquivos:**

- `tests/test_cpd_runner.py` — estender:
  - `test_detect_language_java` — `.java` → `java`
  - `test_detect_language_javascript` — `.js` → `javascript`
  - `test_detect_language_cpp` — `.cpp`/`.c++` → `cpp`
  - `test_detect_language_go` — `.go` → `go`
  - `test_detect_language_unknown` — sem extensões reconhecidas → erro informativo

### 47. `test: implementa teste de integracao fim-a-fim`

**Arquivos:**

- `tests/test_integration.py` — classe `TestEndToEnd` (marcada `@pytest.mark.integration`):
  - `test_full_pipeline_small_repo` — baixa repo público pequeno real, roda pipeline completo, verifica saída
  - `test_json_export_roundtrip` — exporta JSON, verifica parse reverso
  - `test_search_and_analyze` — busca SEART + análise de 1 repo

### 48. `docs: atualiza README com documentacao completa de uso`

**Arquivos:**

- `README.md` — atualizar com TODAS as seções exigidas:
  1. Membros do grupo (já existe)
  2. Explicação do objetivo da ferramenta (já existe)
  3. Explicação das tecnologias (já existe)
  4. **Instruções de instalação**: `pip install -e .`, pré-requisito PMD (`sudo apt install pmd` ou download)
  5. **Instruções de uso**: exemplos de todos os comandos (`analyze`, `search`, `metrics`, `history`, `report`) com flags
  6. **Instruções para executar testes**: `pytest tests/ -v`, como pular testes de integração

### 49. `docs: adiciona docstrings em todos os modulos publicos`

**Arquivos:**

- Todos os módulos em `src/codetwin_analyzer/` — adicionar docstrings Google-style em TODAS funções, classes e métodos públicos:
  - One-line summary
  - `Args:` com tipo e descrição de cada parâmetro
  - `Returns:` descrição do valor de retorno
  - `Raises:` exceções possíveis
  - Docstrings de módulo no topo de cada arquivo

### 50. `ci: expande matriz de CI para Python 3.9, 3.10 e 3.11`

**Arquivos:**

- `.github/workflows/ci.yml` — melhorias:
  - Matrix `python-version: ["3.9", "3.10", "3.11"]`
  - Cache pip: `~/.cache/pip`
  - Step `codecov` (upload coverage report)
  - Job separado `lint` com `flake8` e `isort --check-only`
- `requirements-dev.txt` — `pytest>=7.0`, `pytest-cov`, `flake8`, `isort`

### 51. `chore: adiciona console_scripts e classificadores ao setup.py`

**Arquivos:**

- `setup.py` — adicionar:
  - `entry_points={"console_scripts": ["codetwin-analyzer=codetwin_analyzer.cli:main"]}`
  - Trove classifiers: `Programming Language :: Python :: 3.9/3.10/3.11`, `License :: OSI Approved :: MIT License`, `Development Status :: 3 - Alpha`
- `src/codetwin_analyzer/cli.py` — garantir função `main()` existente
- `requirements.txt` — versões pinadas (`requests>=2.28.0`, `python-fire>=0.5.0`, `pyyaml>=6.0`)

### 52. `chore: polimento final e verificacao pre-entrega`

**Ações (sem novos arquivos, apenas verificações e ajustes):**

- Verificar `.gitignore` cobre: `build/`, `dist/`, `*.egg-info/`, `.coverage`, `htmlcov/`, `*.xml` de CPD, `.pytest_cache/`
- Rodar `pytest --collect-only` — confirmar descoberta de todos os testes
- Rodar `pip install -e .` — confirmar instalação limpa
- Rodar `codetwin-analyzer --help` — confirmar entry point funcional
- Ajustes finais em imports, caminhos, e compatibilidade entre módulos

---

## Resumo

| Pessoa                | Tarefas     | %   | Linhas ~ |
| --------------------- | ----------- | --- | -------- |
| **Antônio**    | 1–21 (21)  | 40% | 735      |
| **Bernardo**    | 22–32 (11) | 21% | 715      |
| **João Lucas** | 33–42 (10) | 19% | 730      |
| **Raphael**     | 43–52 (10) | 19% | 720      |

- **Total: 52 commits** (≥50 exigido)
- **11 arquivos de teste** com ~50 funções de teste (≥10 exigido)
- **GitHub Actions CI** com matrix Python 3.9/3.10/3.11
- **README** com 6 seções conforme template do professor
- **Ordem sequencial**: Antônio → Bernardo → João Lucas → Raphael
