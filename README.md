# ExtratorLattes

O ExtratorLattes lê currículos XML da Plataforma Lattes e produz dados para
avaliação de programas de pós-graduação. A pipeline atual do PPGI classifica
publicações, deduplica registros entre docentes, calcula pontuações e, de modo
opcional, gera métricas externas.

## Pipeline PPGI

```text
XML Lattes
  -> Parte 1: classificação Qualis e deduplicação
  -> publicações canônicas e arquivos de auditoria
  -> Parte 2: pré-verificação e pontuação
  -> relatórios de docentes e do programa

publicações canônicas
  -> Métricas externas opcionais
  -> snapshot SQLite e ranking de citações
```

1. A Parte 1 lê os XMLs, classifica periódicos e eventos, e deduplica
   publicações entre docentes.
2. A Parte 2 só calcula a pontuação quando não existem revisões pendentes de
   Qualis ou deduplicação no intervalo avaliado.
3. As métricas externas não alteram a pontuação.

## Componentes

- `ArquivoInterno/`: leitura do XML Lattes e metadados de proveniência.
- `Classificador/`: classificação Qualis de periódicos e integração do
  QualisLens para eventos.
- `QualisLens/`: associação conservadora de eventos ao Qualis CAPES e scripts
  para atualizar as bases Sucupira.
- `Deduplicacao/`: formação de publicações canônicas e fila de revisão.
- `Metricas/`: snapshots, cache SQLite e relatórios de métricas externas.
- `PPGI/`: comandos da pipeline de avaliação do PPGI.
- `PIIC/`: aplicação independente para editais de iniciação científica.

## Executar o PPGI

Instale as dependências na raiz do repositório:

```bash
python -m pip install -r requirements.txt
```

Depois, execute os comandos a partir de `PPGI/`:

```bash
python main-part1.py DadosPPGI/config.json
python main-part2.py DadosPPGI/config.json

# Opcional: métricas externas e ranking
python main-metricas.py DadosPPGI/config-metricas.json
```

Consulte [PPGI/README.md](PPGI/README.md) para as entradas, as saídas, os
arquivos de revisão e os códigos de saída.

## Classificação Qualis

Periódicos usam a projeção em `Classificador/qualis-unificado.csv`. Eventos
usam as bases canônicas do QualisLens para os quadriênios 2017–2020 e
2021–2024.

O matching de eventos é conservador. Ele aceita correspondência exata ou fuzzy
somente quando os sinais textuais e estruturais são suficientes. Casos ambíguos
não recebem estrato automático. Eles entram em revisão manual.

Atualize as bases oficiais com:

```bash
python QualisLens/scripts/atualizar_sucupira.py \
  --area COMPUTAÇÃO \
  --quadrienio 2021-2024
```

O comando valida os arquivos antes de publicar as bases. Veja
[QualisLens/README.md](QualisLens/README.md) para o fluxo offline e os detalhes
da atualização.

## Métricas externas

O ranking usa citações do Google Scholar. Crossref auxilia a identificação por
DOI. Scopus pode fornecer indexação, citações e métricas de veículo como
contexto quando as credenciais estão disponíveis.

As métricas usam snapshots imutáveis e um cache SQLite. Elas não mudam os
relatórios de pontuação. Veja [Metricas/README.md](Metricas/README.md).

## Licença

GNU General Public License v3.0.
