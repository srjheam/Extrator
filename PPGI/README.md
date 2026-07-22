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
1. Lê o arquivo de ocorrências definido por `arquivo_publicacoes_ocorrencias`
2. Para cada docente:
   - Agrupa as produções por estrato Qualis
   - Verifica a produção mínima (periódicos A1-A4 no intervalo especificado)
   - Calcula a nota segundo os valores definidos no `config-pontuacao.json`
   - Valida se atende aos critérios mínimos
3. Gera os arquivos de saída

**Saídas geradas:**
- `DadosPPGI/saida/<ano>_docente.csv`: Pontuação individual de cada docente
  - Colunas: Docente, Bolsista de Produtividade, Nota Docente, Produção Mínima, Validação de Regras
- `DadosPPGI/saida/<ano>_grupo.csv`: Pontuação geral do grupo/programa. Não é gerado quando há revisão Qualis pendente no intervalo.

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
