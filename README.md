# TP: Análise de Code Clone - Type 1 & 2

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
