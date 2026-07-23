# Sistema de Pontuação PPGI

Este sistema calcula a pontuação de docentes do Programa de Pós-Graduação em Informática (PPGI) baseado em suas produções científicas (periódicos e conferências) extraídas do currículo Lattes.

## 📋 Pré-requisitos

### Dependências Python
Instale as dependências necessárias a partir do arquivo `requirements.txt` na raiz do projeto:

```powershell
pip install -r ..\requirements.txt
```

As principais bibliotecas necessárias são:
- `pandas` - Manipulação de dados
- `tqdm` - Barras de progresso
- `networkx` - Análise de grafos
- `Levenshtein` - Comparação de strings

### Arquivos Necessários

#### 1. Arquivos de Entrada (pasta `DadosPPGI/input/`)
- **`ppgi2024.list`**: Lista de docentes com seus números Lattes
  - Formato: `<numero_lattes>, <nome_completo>`
  - Exemplo: `00000000000, Giovanni Ventorim Comarela`

- **`qualis-journals.csv`**: Classificação Qualis de periódicos (localizado em `../Classificador/qualis-unificado.csv`)
- **`qualis-conferences.csv`**: Classificação Qualis de conferências (localizado em `../Classificador/qualis_conferencias.csv`)

#### 2. Currículos Lattes (pasta `DadosPPGI/curriculos/`)
- Arquivos XML dos currículos Lattes de cada docente
- Nomenclatura: `<numero_lattes>.xml`
- Exemplo: `00000000000.xml`, `11111111111.xml`

#### 3. Arquivos de Configuração (pasta `DadosPPGI/`)
- **`config.json`**: Configurações gerais do sistema
  - Períodos de análise para conferências e periódicos
  - Caminhos dos arquivos de entrada/saída
  - Referência ao arquivo de pontuação

- **`config-pontuacao.json`**: Regras de pontuação e produção mínima
  - Intervalo para verificação de produção mínima
  - Valores de nota para cada estrato Qualis
  - Tags válidas para produção mínima
  - Nota mínima exigida

## 🚀 Como Executar

O sistema é executado em **duas partes sequenciais**. A segunda parte depende da saída da primeira.

### Parte 1: Processamento dos Currículos Lattes

Esta parte lê os currículos Lattes, extrai as produções (periódicos e conferências), classifica-as segundo o Qualis e gera um arquivo CSV intermediário.

```powershell
cd PPGI
python main-part1.py DadosPPGI/config.json
```

**O que faz:**
1. Lê a lista de docentes do arquivo `.list`
2. Para cada docente, carrega o currículo Lattes (XML)
3. Extrai as produções nos períodos configurados:
   - Conferências: `ano_inicio_conferencia` até `ano_fim_conferencia`
   - Periódicos: `ano_inicio_periodico` até `ano_fim_periodico`
4. Classifica as produções usando os arquivos Qualis
5. Gera ocorrências enriquecidas e a deduplicação auditável

**Saída gerada:**
- `DadosPPGI/saida/2024_publicacoes_ocorrencias.csv`: única entrada da Parte 2
- `DadosPPGI/saida/2024_publicacoes_unicas.csv`: registros canônicos
- `DadosPPGI/saida/2024_deduplicacao_decisoes.csv` e `2024_deduplicacao_revisao.csv`: auditoria

### Parte 2: Cálculo de Pontuação

Esta parte lê o CSV gerado na Parte 1, calcula a pontuação de cada docente segundo as regras definidas e gera os relatórios finais.

```powershell
python main-part2.py DadosPPGI/config.json
```

**O que faz:**
1. Executa uma pré-verificação das revisões de Qualis e deduplicação.
2. Lê o arquivo de ocorrências definido por `arquivo_publicacoes_ocorrencias` somente se a pré-verificação permitir a pontuação.
3. Para cada docente:
   - Agrupa as produções por estrato Qualis
   - Verifica a produção mínima (periódicos A1-A4 no intervalo especificado)
   - Calcula a nota segundo os valores definidos no `config-pontuacao.json`
   - Valida se atende aos critérios mínimos
4. Gera os arquivos de saída

**Saídas geradas:**
- `DadosPPGI/saida/<ano>_docente.csv`: Pontuação individual de cada docente
  - Colunas: Docente, Bolsista de Produtividade, Nota Docente, Produção Mínima, Validação de Regras
- `DadosPPGI/saida/<ano>_grupo.csv`: Pontuação geral do grupo/programa.
- `DadosPPGI/saida/<ano>_execucao.json`: estado atômico da execução.

### Pré-verificação e estado da execução

A Parte 2 verifica revisões antes de calcular notas. Uma revisão Qualis de
conferência no intervalo da nota bloqueia a execução. Uma revisão de
deduplicação que tenha uma ocorrência no intervalo da nota também bloqueia a
execução. As resoluções existentes em
`publicacoes_deduplicacao_overrides.csv` são aplicadas antes dessa verificação.

Quando há bloqueio, o comando termina com código `2`. Ele mostra as quantidades
de bloqueios, os caminhos de `*_qualis_revisao.csv` e
`*_deduplicacao_revisao.csv`, e o caminho do manifesto. Ele não publica CSVs
de pontuação novos. A resolução manual de Qualis é trabalho do Plano 2.

O manifesto `<ano>_execucao.json` contém `schema_versao`, `status`, horários,
caminho da configuração, hashes SHA-256 das entradas, detalhes dos bloqueios,
relatórios publicados e hashes, ou dados do erro. Os estados são
`EM_EXECUCAO`, `SUCESSO`, `BLOQUEADO_REVISAO` e `ERRO`.

Os CSVs de pontuação existentes sempre representam a última execução com
sucesso. Eles são atuais somente quando o manifesto informa `SUCESSO` e os
hashes das entradas no manifesto correspondem aos arquivos de entrada atuais.

Os códigos de saída são:

- `0`: sucesso.
- `2`: revisões pendentes que bloqueiam a pontuação.
- `1`: erro inesperado.

### Decisões Qualis

As ocorrências usam o schema `2`. Cada conferência tem `qualis_input_id`,
`qualis_evento_id` e `qualis_registro_id`. Eles identificam, nesta ordem, o
texto informado, o evento oficial e a classificação no quadriênio.

O sistema aceita automaticamente um nome oficial exato ou uma sigla única que
seja compatível com o nome informado. Acrônimos ambíguos, conflitos entre nome
e sigla, e tipos incompatíveis vão para revisão. Um registro de outro
quadriênio também exige revisão e não fornece estrato até uma decisão manual.

`arquivo_overrides_qualis` aponta para `DadosPPGI/input/qualis_overrides.csv`.
O arquivo tem este cabeçalho:

```text
schema_versao,qualis_input_id,acao,qualis_registro_id,justificativa,decidido_por,decidido_em,politica_versao
```

Use `ASSOCIAR` com um ID de registro da fila, ou `SEM_CORRESPONDENCIA` sem ID.
Copie uma decisão revista para esse arquivo. Não use a fila de revisão como
entrada. A classificação vem sempre da base Qualis, nunca do arquivo manual.

### Métricas externas (opcional)

Esta etapa lê somente as publicações canônicas da Parte 1. Ela não muda a
pontuação nem os arquivos `*_grupo.csv`.

```powershell
cd PPGI
python main-metricas.py DadosPPGI/config-metricas.json
```

Use `--offline` para exportar somente dados do cache SQLite. O Google Scholar
é a única fonte das citações do ranking. Scopus fornece indexação, citações e
métricas de veículo como contexto. Crossref valida identidades por DOI.

Cada resultado mantém o provedor e o `snapshot_id`. Publicações ambíguas vão
para `*_metricas_revisao.csv`. O arquivo `*_metricas_ranking.csv` usa ranking
denso por citações Google Scholar.

## 📊 Regras de Pontuação

As regras são definidas no arquivo `config-pontuacao.json`:

### Produção Mínima
- **Intervalo**: 2021-2024
- **Quantidade mínima**: 1 publicação
- **Estratos válidos**: Periódicos A1, A2, A3 ou A4

### Cálculo da Nota
- **Intervalo**: 2023-2024
- **Nota mínima**: 2.25
- **Múltiplo**: 0.25

**OBS**: *O múltiplo é para o arredondamento da nota final. Ela é arredondada para baixo até o múltiplo de significância definido em config-pontuacao.json (campo nota-multiplo). Por exemplo, com múltiplo = 0.25 as notas possíveis são 0.00, 0.25, 0.50, 0.75, 1.00, etc. O arredondamento é sempre para baixo (truncamento). Ex.: nota calculada 2.37 → 2.25.*

**Valores por estrato:**
- **1.0 ponto**: Periódico A1, Periódico A2, Conferência A1, Conferência A2
- **0.75 pontos**: Periódico A3, Periódico A4, Conferência A3, Conferência A4

### Critério de Aprovação
**Regra:** B > 0 **OU** (C >= 2.25 **E** D >= 1)

Onde:
- **B**: Bolsista de Produtividade (PQ ou DT)
- **C**: Nota do Docente
- **D**: Quantidade de produções mínimas (Periódicos A1-A4)

## 📁 Estrutura de Diretórios

```
PPGI/
├── main-part1.py                    # Parte 1: Processamento dos currículos
├── main-part2.py                    # Parte 2: Cálculo de pontuação
├── README.md                        # Este arquivo
├── DadosPPGI/
│   ├── config.json                  # Configuração geral
│   ├── config-pontuacao.json        # Regras de pontuação
│   ├── curriculos/                  # Currículos Lattes (XML)
│   │   ├── 00000000000.xml
│   │   └── 11111111111.xml
│   ├── input/
│   │   ├── ppgi2024.list           # Lista de docentes
│   │   ├── qualis-journals.csv     # Qualis de periódicos
│   │   └── qualis-conferences.csv  # Qualis de conferências
│   └── saida/                       # Arquivos de saída
│       ├── 2024_recredenciamento.csv
│       ├── 2024_docente.csv
│       └── 2024_grupo.csv
└── PontuacaoPPGI/                   # Módulos do sistema
    ├── Conference.py
    ├── Journal.py
    ├── NotaInfo.py
    ├── PessoaPPGI.py
    ├── Pontuacao.py
    ├── PontuacaoTotal.py
    ├── Tabela.py
    └── utils.py
```

## ⚙️ Configuração

### Modificando Períodos de Análise

Edite `DadosPPGI/config.json`:

```json
{
    "ano_inicio_conferencia": 2023,
    "ano_fim_conferencia": 2024,
    "ano_inicio_periodico": 2021,
    "ano_fim_periodico": 2024,
    ...
}
```

### Modificando Regras de Pontuação

Edite `DadosPPGI/config-pontuacao.json`:

```json
{
    "prod-min": {
        "intervalo": [2021, 2024],
        "prod-min-qtd": 1,
        "valid-tags": ["Periódico A1", "Periódico A2", "Periódico A3", "Periódico A4"]
    },
    "nota": {
        "intervalo": [2023, 2024],
        "nota-min": 2.25,
        "valores": [
            {"valor": 1, "tags": ["Periódico A1", "Periódico A2", ...]},
            {"valor": 0.75, "tags": ["Periódico A3", "Periódico A4", ...]}
        ]
    }
}
```

## 🔍 Observações Importantes

1. **Dependência entre as partes**: A Parte 2 **deve** ser executada após a Parte 1, pois utiliza o arquivo CSV gerado como entrada.

2. **Conferências**: Apenas trabalhos completos são considerados no cálculo.

3. **Correções manuais**: Use somente `DadosPPGI/input/publicacoes_deduplicacao_overrides.csv`. Não edite o CSV de ocorrências.

4. **Qualis não identificado**: Produções sem classificação Qualis aparecerão com a tag "Qualis não identificado" no CSV intermediário.

5. **Classes compartilhadas**: Este sistema utiliza classes compartilhadas com o sistema PIIC, localizadas nas pastas `ArquivoInterno/` e `Classificador/`.

## Deduplicação de publicações

A Parte 1 é a única etapa que cria a identidade de uma publicação. Ela usa a
política `POLITICA_V2` e publica ocorrências, canônicos, membros, decisões,
revisão e o manifesto. O manifesto é publicado por último.

`ocorrencia_id` usa o identificador Lattes, o tipo XML e
`SEQUENCIA-PRODUCAO`. `conteudo_fingerprint` muda quando os dados
bibliográficos mudam. `publicacao_canonica_id` é derivado dos membros. Ele
muda quando os membros do grupo mudam.

DOI válido igual é a evidência mais forte. DOI válido diferente, tipo diferente
e ano diferente não agrupam automaticamente. Periódicos usam ISSN canônico.
Conferências usam `qualis_evento_id`. Títulos genéricos também precisam de
autores ou dados estruturais. Casos incertos entram na fila de revisão.

Use o arquivo de overrides com o cabeçalho versionado. Cada linha precisa de
IDs, fingerprints atuais, ação `AGRUPAR` ou `NAO_AGRUPAR`, justificativa e
dados da decisão. Após mudar overrides, execute novamente a Parte 1. A Parte
2 e as métricas verificam hashes no manifesto e param quando a saída está
desatualizada ou há revisão pendente.

Uma publicação canônica entra uma vez na nota do grupo. Cada docente membro
recebe uma vez o crédito individual. Conflitos de estrato ou de registro Qualis
ficam no registro canônico e bloqueiam a pontuação até revisão.

## Métricas externas

`main-metricas.py` cria um snapshot imutável. O snapshot guarda as entradas
canônicas, os vínculos e as respostas usadas no relatório. Repetir a exportação
de um snapshot não lê os CSV atuais e não consulta a rede.

O estado final é `CONCLUIDO`, `PARCIAL` ou `FALHOU`. O comando retorna 0 para
concluído, 2 para parcial e 1 para falha. Snapshots em execução ou falhos não
podem ser exportados.

## 📝 Exemplo de Execução Completa

```powershell
# 1. Instalar dependências (executar apenas uma vez)
cd c:\Users\Rafael\Documents\calculo-nota-a
pip install -r requirements.txt

# 2. Executar Parte 1
cd PPGI
python main-part1.py DadosPPGI/config.json

# 3. (Opcional) Registrar correções de deduplicação
# DadosPPGI/input/publicacoes_deduplicacao_overrides.csv

# 4. Executar Parte 2
python main-part2.py DadosPPGI/config.json

# 5. Verificar os resultados em DadosPPGI/saida/
```

## 🆘 Solução de Problemas

**Erro: "ModuleNotFoundError"**
- Certifique-se de ter instalado todas as dependências: `pip install -r ..\requirements.txt`
- Execute os scripts a partir da pasta `PPGI/`

**Erro: "FileNotFoundError"**
- Verifique se todos os caminhos no `config.json` estão corretos
- Certifique-se de que os arquivos XML dos currículos existem na pasta `curriculos/`

**Produções não aparecem**
- Verifique se os períodos no `config.json` estão corretos
- Confirme se as publicações estão dentro dos intervalos definidos

**Qualis não identificado**
- Verifique se os arquivos Qualis estão atualizados
- Confira se o ISSN/venue das publicações estão cadastrados nos arquivos Qualis
