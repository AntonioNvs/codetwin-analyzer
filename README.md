# CodeTwin Analyzer: Análise de Code Clone - Type 1 & 2

## Membros do grupo

- Antônio Caetano Neves Neto
- Bernardo Dutra Lemos
- João Lucas Simões Moreira
- Raphael Aroldo Carreiro Mendes

## Descrição do sistema

Ferramenta de linha de comando que identifique possíves *code clones* do tipo 1 e 2, dado um link de um repositório do GitHub. As tecnologias a serem utilizadas serão o [Github API](https://docs.github.com/en/rest:) e [Github Search Tool](https://seart-ghs.si.usi.ch) para a leitura do código dos repositórios, a [python-fire](https://github.com/google/python-fire) para leitura da CLI e [pmd](https://github.com/pmd/pmd) para a análise estática do repositório, na qual irá retornar os dados de *code clones* solicitados.

Será apresentado as métricas de *code clones*, como número atual de cada tipo, funções frequentes, visualizações de histórico dos *code clones* por tempo/commit/branch, entre outras possíveis métricas.

## Explicação das tecnologias

- [Github API](https://docs.github.com/en/rest:): Automatiza o download dos repositórios e a coleta de metadados necessários para o conjunto de dados.
- [Github Search Tool (SEART)](https://seart-ghs.si.usi.ch): Filtra repositórios por critérios específicos (linguagem, estrelas, data) para criar um dataset qualificado.
- [python-fire](https://github.com/google/python-fire): Transforma funções de análise em ferramentas de linha de comando para facilitar a execução de testes e automações.
- [pmd](https://github.com/pmd/pmd): Atua como o motor de análise estática, utilizando seu módulo Copy-Paste Detector (CPD) para identificar as duplicatas de código.

## Instalação

```bash
# 1. Clone o repositório
git clone <repo-url> && cd codetwin-analyzer

# 2. Crie e ative o ambiente virtual
python -m venv venv && source venv/bin/activate

# 3. Instale o pacote em modo editável
pip install -e .

# 4. Instale o PMD (pré-requisito externo)
#    Baixe em https://pmd.github.io/, extraia o ZIP e adicione a pasta bin/ ao PATH:
#    export PATH="$PATH:/caminho/para/pmd-bin-7.25.0/bin"
```

## Configuração

Copie o arquivo de exemplo e preencha seu token do GitHub:

```bash
cp .example.env .env
# Edite .env e substitua pelo seu token:
# GITHUB_TOKEN="ghp_seu_token_aqui"
```

O token precisa apenas da permissão `public_repo` (para repositórios públicos).

---

## Exemplos de Uso

### 1. Análise rápida de um repositório (`analyze`)

```bash
python -m codetwin_analyzer.cli analyze https://github.com/pallets/flask
```

Saída esperada:

```
Iniciando análise para: https://github.com/pallets/flask
Baixando código-fonte de pallets/flask...
Iniciando varredura com PMD CPD...
Processando o XML e calculando estatísticas...

========================================
 SUMÁRIO DE ANÁLISE
========================================
Total de Clones Encontrados: 327
  - Tipo 1 (Idênticos):  201
  - Tipo 2 (Similares):  126
Total de Arquivos Afetados:  42
Total de Linhas Duplicadas:  1847

 Top 5 Arquivos Mais Clonados:
  - test_basic.py: 28 ocorrências
  - test_blueprints.py: 22 ocorrências
  - test_templating.py: 18 ocorrências
  - test_cli.py: 12 ocorrências
  - blueprints.py: 8 ocorrências
```

**Parâmetros importantes:**

| Parâmetro       | Default            | Descrição                                                                                                                                                                    |
| ---------------- | ------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `--min-tokens` | `100`            | Sensibilidade do detector.**100 tokens ≈ 20-25 linhas de Python.** Valores ≤ 50 capturam boilerplate trivial (`import`/`assert` repetidos) e inflam os resultados. |
| `--language`   | auto               | Força a linguagem (`python`, `java`, `javascript`, `cpp`, `go`, `ruby`). Se omitido, detecta automaticamente pela extensão predominante.                         |
| `--output`     | `cpd_output.xml` | Caminho do arquivo XML intermediário gerado pelo PMD CPD.                                                                                                                     |

### 2. Painel detalhado de métricas (`metrics`)

```bash
python -m codetwin_analyzer.cli metrics https://github.com/pallets/flask
```

Gera um relatório completo com classificação por tipo, densidade e ranking de arquivos críticos. Útil para comparar repositórios com o mesmo threshold:

```bash
# Comparação entre projetos com threshold padronizado
python -m codetwin_analyzer.cli metrics https://github.com/pallets/flask --min-tokens=100
python -m codetwin_analyzer.cli metrics https://github.com/psf/requests --min-tokens=100
```

### 3. Busca de repositórios por linguagem (`search`)

```bash
# Listar repositórios Python com ≥ 50 estrelas
python -m codetwin_analyzer.cli search python --min-stars=50 --max-results=10

# Buscar e analisar automaticamente cada repositório encontrado
python -m codetwin_analyzer.cli search java --min-stars=100 --max-results=5 --analyze
```

---
