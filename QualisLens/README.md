# QualisLens

Ferramenta de linha de comando para associar publicações em anais de conferências às suas classificações **Qualis CAPES** (quadriênios 2017-2020 e 2021-2024), sem depender de modelos de linguagem para os casos mais simples.

## Contrato atual

O fluxo sem `--modelo` usa somente `EXATO`, `AUTO_FUZZY` e `REVISAO_MANUAL`.
Nunca acessa Ollama ou rede. `AUTO_FUZZY` exige score `>= 88`, margem `>= 8` e
sinais estruturais compatíveis. Casos ambíguos ficam em revisão; não recebem
estrato. A API legada é `QualisConferencia.get_match(venue, ano, sigla=None)` e
`get_estrato(venue, ano=None, sigla=None)`. Sem ano, ela avisa depreciação e usa
a semântica legada 2017-2020.

As bases canônicas ficam em `base/`. Use
`python QualisLens/scripts/import_sucupira_csv.py oficial.csv base/qualis_2017_2020.csv`
para importar CSV oficial. `base/metadata.json` registra origem e contagem.
`Classificador/qualis_conferencias.csv` é caminho histórico compatível; o PPGI
o redireciona para a fonte canônica.

---

## Índice

1. [Visão geral](#1-visão-geral)
2. [Formato de entrada](#2-formato-de-entrada)
3. [Formato de saída](#3-formato-de-saída)
4. [Algoritmo de matching](#4-algoritmo-de-matching)
5. [Como executar](#5-como-executar)
6. [Como rodar os testes](#6-como-rodar-os-testes)
7. [Estrutura do projeto](#7-estrutura-do-projeto)

---

## 1. Visão geral

O QualisLens resolve a classificação de cada publicação em três etapas de custo crescente:

```
entrada CSV  →  pré-processamento  →  busca exata  →  fuzzy matching  →  [LLM opcional]  →  saída CSV
```

- **Busca exata**: a maioria dos casos com sigla conhecida resolve aqui (ex.: `ICSE`, `SBRC`).
- **Fuzzy matching**: nomes abreviados, truncados ou com ordem diferente de palavras são resolvidos automaticamente quando o score de similaridade ≥ 75.
- **LLM (opcional)**: scores na faixa 68–74 são enviados a um modelo local (Ollama) para decisão semântica. Scores < 68 são marcados como `LLM_MISS` sem chamar o LLM (candidatos sem relevância).

---

## 2. Formato de entrada

CSV com separador vírgula e **codificação UTF-8**. Colunas obrigatórias:

| Coluna | Tipo | Descrição |
|---|---|---|
| `titulo_artigo` | texto | Título do artigo (usado como contexto pelo LLM) |
| `nome_conferencia` | texto | Nome da conferência — pode conter sigla prefixada (ex.: `SBRC - Simpósio...`) |
| `ano_publicacao` | inteiro | Ano de publicação — define qual base Qualis usar |

Coluna opcional (recomendada para melhorar a precisão):

| Coluna | Tipo | Descrição |
|---|---|---|
| `sigla_conferencia` | texto | Sigla oficial da conferência (ex.: `ICSE`, `AAAI`) |

### Exemplos por dificuldade

**Fácil** — sigla explícita, nome exato:
```csv
titulo_artigo,nome_conferencia,sigla_conferencia,ano_publicacao
Meu artigo,International Conference on Software Engineering,ICSE,2023
Outro artigo,SBRC - Simpósio Brasileiro de Redes de Computadores,SBRC,2022
```

**Médio** — nome parcialmente abreviado ou sem sigla:
```csv
titulo_artigo,nome_conferencia,sigla_conferencia,ano_publicacao
Artigo 1,ACM Conf. on Computer and Communications Security,CCS,2023
Artigo 2,"Int'l Symp. on Cluster, Cloud and Grid Computing",,2021
```

**Difícil** — nome muito abreviado, sem sigla:
```csv
titulo_artigo,nome_conferencia,sigla_conferencia,ano_publicacao
Artigo 1,C. on N Inf Proc. Sys.,,2023
Artigo 2,Ann. ACM Symp. on Theory of Comp.,,2022
```

**Dica:** se o campo `nome_conferencia` contiver a sigla prefixada no formato `SIGLA - Nome completo` ou `SIGLA: Nome`, o sistema a extrai automaticamente.

---

## 3. Formato de saída

O CSV de saída inclui todas as colunas originais mais as colunas produzidas pelo pipeline:

| Coluna | Descrição |
|---|---|
| `qualis_estrato` | Classificação Qualis (A1, A2 … B5, C) ou vazio se não resolvido |
| `qualis_nome_oficial` | Nome oficial da conferência na base Qualis |
| `qualis_quadrienio` | Quadriênio da classificação (`2017-2020` ou `2021-2024`) |
| `qualis_status` | Status do matching (ver tabela abaixo) |
| `qualis_score_fuzzy` | Score de similaridade textual do melhor candidato (0–100) |
| `passou_fuzzy` | `Sim` se resolvido sem LLM; `Não` se precisou de LLM |
| `confiabilidade` | Rótulo orientativo para revisão humana |
| `qualis_candidatos` | Top-3 candidatos do fuzzy com estrato e score |
| `qualis_llm_motivo` | Justificativa da decisão do LLM |
| `qualis_obs` | Observações (ex.: `extrapolado`, diferença de estrato entre quadriênios) |

### Status possíveis

| Status | Significado | Revisão humana? |
|---|---|---|
| `EXATO` | Match exato por sigla ou nome normalizado | Não |
| `AUTO_FUZZY` | Fuzzy score ≥ 75 — aceito automaticamente | Não |
| `LLM_OK` | LLM confirmou o candidato (score 68–74) | Não |
| `LLM_DUPLO_OK` | Dois modelos concordaram no candidato | Não |
| `LLM_LOW_OK` | LLM achou candidato mas score < 60 | **Sim** |
| `LLM_LOW_MISS` | LLM não achou; score < 60 | **Sim** |
| `LLM_MISS` | Nenhum candidato adequado / LLM indisponível | **Sim** |
| `LLM_DUPLO_DIVERGE` | Dois modelos discordaram | **Sim** |

---

## 4. Algoritmo de matching

### 4.1 Pré-processamento

Antes de qualquer comparação, o texto passa por normalização completa:

1. **Lowercase** — converte tudo para minúsculas.
2. **Remoção de acentos** — decomposição NFD (`Simpósio` → `simposio`).
3. **Remoção de pontuação** — `/`, `.`, `'`, `-`, `&` etc. viram espaço.
4. **Remoção de stopwords** em inglês (`on`, `of`, `the`, `in`, `and`, `for`, …).
5. **Colapso de espaços** duplicados.

Além disso:
- **Extração de sigla embutida**: `"SBRC - Simpósio Brasileiro…"` → sigla `SBRC` + nome separado.
- **Geração de acrônimo**: `"International Conference on Computer Vision"` → `ICCV` (primeira letra de cada token não-stopword).

### 4.2 Busca exata

Comparação por igualdade normalizada no quadriênio correspondente ao ano de publicação:

1. Tenta o quadriênio primário (ex.: 2021-2024 para ano 2022).
2. Tenta primeiro por **sigla**, depois por **nome**.
3. Se não encontrar, faz **fallback para o quadriênio alternativo** — cobre conferências classificadas em apenas um dos períodos. Resultado marcado com `extrapolado=True`.

### 4.3 Fuzzy matching híbrido

Quando a busca exata falha, o sistema:

**Pré-filtro:** seleciona até 25 candidatos via `token_set_ratio` (permissivo, não descarta por reordenação de palavras).

**Re-pontuação com score híbrido:**

```
score_final = max(
    token_set_ratio  × 1.00,   # robusto a subconjuntos e reordenação
    token_sort_ratio × 1.00,   # robusto à ordem diferente de palavras
    token_level_fuzzy × 0.95,  # detecta abreviações token-a-token
    acronimo_ratio    × 0.88,  # sinal secundário — acrônimos ≥ 3 chars
)
```

**Token-level fuzzy**: compara cada token da query contra todos os tokens do candidato usando `partial_ratio`, ponderando pelo comprimento do token. Exemplos de correspondências capturadas:

| Token da query | Candidato correspondido | `partial_ratio` |
|---|---|---|
| `comp` | `computing` | ~100% |
| `conf` | `conference` | ~100% |
| `symp` | `symposium` | ~88% |
| `intl` ou `int` | `international` | ~77% |

Se houver sigla (campo `sigla_conferencia`), candidatos por sigla também são adicionados ao pool.

### 4.4 Decisão por threshold

| Faixa de score | Ação |
|---|---|
| ≥ 75 | `AUTO_FUZZY` — aceito automaticamente |
| 68–74 | Encaminhado para LLM (ou `LLM_MISS` se LLM indisponível) |
| < 68 | `LLM_MISS` — candidatos descartados como ruído |

### 4.5 Revisão por LLM (opcional)

Ativado quando o score cai na faixa 68–74. O modelo recebe o nome original, o ano e os top-5 candidatos fuzzy, e deve:

1. Expandir semanticamente o nome abreviado.
2. Escolher o candidato mais plausível (ou `null` se nenhum serve).
3. Informar confiança (`alta` / `media` / `baixa`) e justificativa.

**Modo dupla verificação** (`--modelo modelo1 modelo2`): ambos os modelos são consultados. O resultado só é aceito com consenso; divergência → `LLM_DUPLO_DIVERGE` para revisão humana.

---

## 5. Como executar

### Pré-requisitos

```bash
# Criar ambiente virtual (apenas na primeira vez)
python3 -m venv .venv
source .venv/bin/activate

# Instalar dependências
pip install -r requirements.txt
```

### Sem LLM (recomendado no macOS sem modelo local)

Resolve todos os casos com match exato e fuzzy ≥ 75. Casos com score intermediário ficam com `LLM_MISS` para revisão manual.

```bash
cd qualislens

# Arquivo de saída gerado automaticamente como <entrada>_output.csv
python main.py --entrada ../test/easy/entrada.csv
python main.py --entrada ../test/mid/entrada.csv

# Especificar arquivo de saída
python main.py --entrada minha_lista.csv --saida resultado.csv
```

### Com LLM — modelo único

```bash
# Instalar Ollama: https://ollama.com
ollama pull llama3.2:3b

python main.py --entrada minha_lista.csv --modelo llama3.2:3b
```

### Com LLM — dupla verificação

```bash
ollama pull llama3.2:3b
ollama pull mistral:7b

python main.py --entrada minha_lista.csv --modelo llama3.2:3b mistral:7b
```

### Parâmetros

| Parâmetro | Obrigatório | Descrição |
|---|---|---|
| `--entrada` | Sim | Caminho para o CSV de entrada |
| `--saida` | Não | Caminho do CSV de saída (padrão: `<entrada>_output.csv`) |
| `--modelo` | Não | Modelo(s) Ollama. Omitir = sem LLM. Um modelo = simples. Dois = dupla verificação |

---

## 6. Como rodar os testes

Os testes cobrem o algoritmo completo **sem usar LLM** — nenhum modelo local precisa estar instalado.

```bash
# A partir da pasta QualisLens/
source .venv/bin/activate
pytest
```

Saída esperada: **143 passed**.

### O que cada arquivo de teste cobre

| Arquivo | O que testa |
|---|---|
| `tests/test_preprocessor.py` | Normalização de texto, extração de sigla embutida, geração de acrônimo, pré-processamento completo de linha |
| `tests/test_matcher.py` | `_token_level_fuzzy` (ponderação, abreviações), `_score_hibrido` (reordenação, subsets, acrônimo), pipeline `match()` completo |
| `tests/test_qualis_db.py` | Mapeamento ano→quadriênio, buscas exatas por sigla e nome, fallback cross-quadriênio, detecção de estrato diferente entre quadriênios |
| `tests/test_integration.py` | Fixtures `easy`/`mid`/`hard` — pipeline end-to-end sem LLM; testes de regressão com estrato esperado |

### Opções úteis

```bash
# Rodar apenas um módulo de testes
pytest tests/test_matcher.py -v

# Rodar apenas os casos difíceis
pytest tests/test_integration.py -v -k "hard"

# Ver cobertura de código
pytest --cov=../qualislens --cov-report=term-missing
```

### Fixtures de teste

Os dados de teste estão em `test/`:

| Pasta | Descrição |
|---|---|
| `test/easy/` | 5 casos com sigla explícita e nome exato — todos `EXATO` |
| `test/mid/` | 5 casos com nome parcialmente abreviado — mix de `EXATO` e `AUTO_FUZZY` |
| `test/hard/` | 5 casos muito abreviados, sem sigla — todos `AUTO_FUZZY` ≥ 75 sem LLM |

---

## 7. Estrutura do projeto

```
QualisLens/
├── qualislens/              # Código-fonte
│   ├── utils.py             # Utilitários compartilhados (strip_accents)
│   ├── constants.py         # Thresholds, status, caminhos padrão
│   ├── preprocessor.py      # Normalização, extração de sigla, geração de acrônimo
│   ├── matcher.py           # Busca exata + score híbrido fuzzy
│   ├── qualis_db.py         # Carga e consulta das bases Qualis (CSV)
│   ├── llm_reviewer.py      # Integração com Ollama (opcional)
│   ├── exporter.py          # Geração dos CSVs de saída e fila de revisão
│   └── main.py              # Ponto de entrada CLI
├── tests/                   # Testes automatizados (pytest, sem LLM)
│   ├── conftest.py          # Fixtures compartilhadas (QualisDB session-scoped)
│   ├── test_preprocessor.py
│   ├── test_matcher.py
│   ├── test_qualis_db.py
│   └── test_integration.py
├── test/                    # Fixtures de dados (CSVs de entrada e saída esperada)
│   ├── easy/
│   ├── mid/
│   └── hard/
├── base/                    # Bases Qualis em CSV
│   ├── qualis_2017_2020.csv
│   └── qualis_2021_2024.csv
├── requirements.txt         # Dependências Python
├── pytest.ini               # Configuração do pytest
└── README.md
```
