# ExtratorLattes

Este repositório contém um sistema completo para processar currículos da Plataforma Lattes (CNPq) e calcular pontuações acadêmicas baseadas em critérios específicos de programas de pós-graduação e editais de iniciação científica.

## 📋 Índice

- [Visão Geral](#visão-geral)
- [Estrutura do Projeto](#estrutura-do-projeto)
- [Módulos Principais](#módulos-principais)
  - [ArquivoInterno](#arquivointerno)
  - [Classificador](#classificador)
  - [QualisNovo](#qualisnovo)
- [Aplicações](#aplicações)
  - [PIIC](#piic---programa-de-iniciação-científica)
  - [PPGI](#ppgi---programa-de-pós-graduação)
- [Instalação](#instalação)
- [Como Usar](#como-usar)
- [Dependências](#dependências)
- [Contribuindo](#contribuindo)

---

## 🎯 Visão Geral

O sistema foi desenvolvido para automatizar o processo de avaliação de produção científica de pesquisadores, utilizando os dados disponíveis nos currículos Lattes em formato XML. O projeto implementa:

- **Parsing de currículos Lattes**: Extração estruturada de produções científicas.
- **Classificação Qualis**: Integração com o sistema Qualis CAPES para periódicos e conferências.
- **Cálculo de pontuação**: Aplicação de regras específicas de editais e programas.
- **Geração de relatórios**: Outputs em HTML, TXT e CSV.

---

## 📁 Estrutura do Projeto

```
calculo-nota-a/
├── ArquivoInterno/          # Módulo para parsing de currículos Lattes
├── Classificador/           # Classificação Qualis de publicações
├── QualisNovo/              # Geração de arquivos Qualis unificados
├── PIIC/                    # Aplicação para Programa de Iniciação Científica
├── PPGI/                    # Aplicação para Programa de Pós-Graduação
├── docs/                    # Documentação e diagramas
└── requirements.txt         # Dependências Python
```

---

## 🔧 Módulos Principais

### ArquivoInterno

Módulo responsável pelo parsing e extração de dados dos currículos Lattes em formato XML.

As classes e enums foram baseados no documento XSD disponibilizado na [plataforma lattes](https://lattes.cnpq.br/), ele define a configuração dos currículos em XML. Esse arquivo também pode ser encontrado na pasta **docs/**.

#### Componentes principais:

**`CurriculoXML.py`**
- Classe principal para ler e extrair informações de currículos Lattes
- Métodos para extração de diferentes tipos de produções:
  - `get_artigo()`: Artigos em periódicos.
  - `get_trabalho_evento()`: Trabalhos em eventos/conferências.
  - `get_livro()`: Livros publicados.
  - `get_capitulo_livro()`: Capítulos de livro.
  - `get_orientacao_md()`: Orientações de mestrado e doutorado.
  - `get_orientacao_mti()`: Orientações de TCC e iniciação científica.
  - `get_registro_patente()`: Registros de patentes.
  - `get_artistica_cultural()`: Produções artísticas e culturais.
  - E outros tipos de produções acadêmicas.

**`PessoaLATTES.py`**
- Classe que representa um pesquisador
- Métodos:
  - `carrega_curriculo()`: Carrega todas as produções de um período específico.
  - `get_producoes()`: Retorna lista de todas as produções.
  - `get_nivel_academico()`: Retorna nível acadêmico (graduação, mestrado, doutorado).

**`Producao.py`**
- Hierarquia de classes representando diferentes tipos de produções.

**Subpasta `enums/`**
- Enumerações para classificação de produções.

#### Exemplo de uso:

```python
from ArquivoInterno.CurriculoXML import CurriculoXML

# Carregar currículo
curriculo = CurriculoXML("caminho/para/curriculo.xml")

# Extrair nome
nome = curriculo.get_nome()

# Extrair artigos de 2020 a 2024
artigos = curriculo.get_artigo(2020, 2024)

# Extrair todas as produções
producoes = curriculo.get_all_producoes(2020, 2024)
```

---

### Classificador

Módulo para classificação de publicações usando o sistema Qualis CAPES.

#### Componentes:

**`Qualis.py`**
- Classifica periódicos científicos usando ISSN
- Métodos:
  - `get_estrato(issn)`: Retorna o estrato Qualis (A1, A2, B1, B2, etc.).
- Reconhece ISSNs nos formatos: `xxxxxxxx` ou `xxxx-xxxx`.

**`QualisConferencia.py`**
- Classifica conferências/eventos usando nome do evento.
- Métodos:
  - `get_estrato(venue)`: Retorna o estrato Qualis da conferência.
- Utiliza algoritmo de similaridade Levenshtein para matching fuzzy.
- Threshold de 85% de similaridade para matches.

#### Arquivos de dados:

- `qualis-unificado.csv`: Projeção oficial de periódicos para a Parte 1.
- `base/qualis_periodicos_2021_2024.csv`: Base canônica de periódicos.
- `qualis_conferencias.csv`: Base de conferências.

Use `QualisLens/scripts/atualizar_sucupira.py` para atualizar os eventos e os
periódicos oficiais. Esse fluxo não adiciona aliases de ISSN do Scopus, JCR ou
de outras fontes.

#### Exemplo de uso:

```python
from Classificador.Qualis import Qualis
from Classificador.QualisConferencia import QualisConferencia

# Classificar periódico
qualis_journal = Qualis("Classificador/qualis-unificado.csv")
estrato = qualis_journal.get_estrato("1234-5678")  # Retorna "A1", "B2", etc.

# Classificar conferência
qualis_conf = QualisConferencia("Classificador/qualis_conferencias.csv")
estrato = qualis_conf.get_estrato("International Conference on Software Engineering")
```

---

## 📊 Aplicações

### PIIC - Programa de Iniciação Científica

Aplicação para avaliação de orientadores em editais de iniciação científica.

#### Estrutura:

```
PIIC/
├── main.py                    # Script principal
├── DadosPIIC/                 # Dados de entrada
│   ├── config.json            # Configurações
│   ├── orientadores.csv       # Lista de orientadores
│   ├── tabela_edital_PIIC_2025.json  # Regras de pontuação
│   └── Curriculos/            # XMLs dos currículos
├── PontuacaoPIIC/             # Módulos de cálculo
└── Resultados/                # Relatórios gerados
```

#### Como executar:

```bash
cd PIIC
python main.py DadosPIIC/config.json
```

#### Saídas geradas:

- `{CPF}.html`: Relatório detalhado em HTML
- `{CPF}.txt`: Relatório em texto
- `resultados.csv`: Resumo de todos os orientadores

---

### PPGI - Programa de Pós-Graduação

Aplicação para avaliação de docentes em programas de pós-graduação.

#### Estrutura:

```
PPGI/
├── main-part1.py              # Processamento de produções
├── main-part2.py              # Cálculo de pontuação
├── DadosPPGI/                 # Dados de entrada
│   ├── config.json            # Configurações
│   ├── input/                 # Listas e classificações
│   │   ├── ppgi2024.list      # Lista de docentes
│   │   ├── qualis-journals.csv
│   │   └── qualis-conferences.csv
│   └── download/              # XMLs dos currículos
└── PontuacaoPPGI/             # Módulos de cálculo
```

#### Como executar:

```bash
cd PPGI
python main-part1.py DadosPPGI/config.json
python main-part2.py DadosPPGI/config-pontuacao.json
```

---

## 💻 Como Usar

### 1. Obter currículos Lattes em XML

Os currículos devem ser exportados da Plataforma Lattes em formato XML. Salve-os em um diretório específico (ex: `Curriculos/`).

### 2. Configurar os parâmetros

Edite o arquivo `config.json` da aplicação desejada (PIIC ou PPGI) com:
- Período de avaliação (ano inicial e final)
- Caminhos para arquivos de entrada
- Regras de pontuação

### 3. Executar a aplicação

```bash
# Para PIIC
python PIIC/main.py PIIC/DadosPIIC/config.json

# Para PPGI
python PPGI/main-part1.py PPGI/DadosPPGI/config.json
```

## 📦 Dependências

- **pandas**: Manipulação de dados tabulares
- **tqdm**: Barras de progresso
- **networkx**: Análise de grafos (usado em algumas análises)
- **Levenshtein**: Cálculo de similaridade de strings

Instale todas as dependências com:
```bash
pip install -r requirements.txt
```

---

## 📄 Licença

GNU General Public License v3.0.

---

## 🔍 Observações Importantes

- **Formato dos currículos**: Os currículos devem estar no formato XML exportado diretamente da Plataforma Lattes
- **Atualizações Qualis**: O sistema Qualis é atualizado periodicamente pela CAPES. Atualize os arquivos CSV conforme necessário
- **Validação de dados**: Sempre valide os resultados gerados, especialmente em casos de mudanças nas regras de avaliação

---
