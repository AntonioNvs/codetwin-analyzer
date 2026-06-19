# CodeTwin Analyzer: Análise de Code Clone - Type 1 & 2

## Membros do grupo

- Antônio Caetano Neves Neto
- Bernardo Dutra Lemos
- João Lucas Simões Moreira
- Raphael Aroldo Carreiro Mendes

## Explicação do objetivo da ferramenta

Ferramenta de linha de comando que identifique possíves *code clones* do tipo 1 e 2, dado um link de um repositório do GitHub. As tecnologias a serem utilizadas serão o [Github API](https://docs.github.com/en/rest) e [Github Search Tool](https://seart-ghs.si.usi.ch) para a leitura do código dos repositórios, a [python-fire](https://github.com/google/python-fire) para leitura da CLI e [pmd](https://github.com/pmd/pmd) para a análise estática do repositório, na qual irá retornar os dados de *code clones* solicitados.

Será apresentado as métricas de *code clones*, como número atual de cada tipo, funções frequentes, visualizações de histórico dos *code clones* por tempo/commit/branch, entre outras possíveis métricas.

## Explicação das tecnologias

- [Github API](https://docs.github.com/en/rest): Automatiza o download dos repositórios e a coleta de metadados necessários para o conjunto de dados.
- [Github Search Tool (SEART)](https://seart-ghs.si.usi.ch): Filtra repositórios por critérios específicos (linguagem, estrelas, data) para criar um dataset qualificado.
- [python-fire](https://github.com/google/python-fire): Transforma funções de análise em ferramentas de linha de comando para facilitar a execução de testes e automações.
- [pmd](https://github.com/pmd/pmd): Atua como o motor de análise estática, utilizando seu módulo Copy-Paste Detector (CPD) para identificar as duplicatas de código.

## Instruções de instalação

```bash
# 1. Clone o repositório
git clone <repo-url>
cd codetwin-analyzer

# 2. Crie e ative o ambiente virtual
python -m venv venv
source venv/bin/activate  # No Linux/Mac
# ou: venv\Scripts\activate no Windows

# 3. Instale o pacote em modo editável e instale dependências
pip install -e .

# 4. Instale o PMD (pré-requisito externo)
# Opção A (Ubuntu/Debian):
sudo apt install pmd

# Opção B (Download Manual):
# Baixe em https://pmd.github.io/, extraia o ZIP e adicione a pasta bin/ ao PATH:
# export PATH="$PATH:/caminho/para/pmd-bin-7.25.0/bin"
```

### Configuração Opcional (Token do GitHub)

Copie o arquivo de exemplo e preencha seu token do GitHub (para evitar rate limit):
```bash
cp .example.env .env
# Edite .env e preencha a variável GITHUB_TOKEN="seu_token"
```

## Instruções de uso

O sistema pode ser utilizado através do comando `codetwin-analyzer` ou via python (`python -m codetwin_analyzer.cli`). Você pode adicionar `--progress=True` em qualquer comando para ver o passo-a-passo.

### 1. Comando `analyze`
Analisa um repositório rapidamente, identificando clones e fornecendo um sumário.
```bash
codetwin-analyzer analyze https://github.com/pallets/flask --min-tokens=100 --format=text
```
*Parâmetros úteis*: `--format` (`text`, `json`, `csv`, `html`), `--output` (caminho para salvar).

### 2. Comando `search`
Busca repositórios via SEART GHS, permitindo rodar análises em lote.
```bash
# Buscar repositórios em python e analisá-los sequencialmente
codetwin-analyzer search python --min-stars=500 --max-results=5 --analyze=True
```

### 3. Comando `metrics`
Extrai métricas estatísticas avançadas (densidade, top arquivos clonados, etc).
```bash
codetwin-analyzer metrics https://github.com/pallets/flask --min-tokens=100
```

### 4. Comando `history`
Analisa a evolução dos clones através do histórico de commits da branch principal.
```bash
codetwin-analyzer history https://github.com/pallets/flask --depth=20 --min-tokens=100
```
*Calcula e exibe a tendência de crescimento ou queda dos Clones Tipo 1 e Tipo 2.*

### 5. Comando `report`
Executa o pipeline completo que une métricas, histórico e gera um relatório unificado com tolerância a falhas.
```bash
codetwin-analyzer report https://github.com/pallets/flask --min-tokens=100 --with-history=True --format=html --output=relatorio.html --progress=True
```

## Instruções para executar testes

Para rodar todos os testes unitários e de integração com a saída detalhada (`-v`):
```bash
pytest tests/ -v
```

### Como pular os testes de integração
Os testes de integração realizam downloads de repositórios reais da internet e executam o pipeline de ponta a ponta, o que pode levar tempo. Para executar apenas os testes unitários rápidos:
```bash
pytest tests/ -v -m "not integration"
```
