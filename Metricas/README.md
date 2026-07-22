# Métricas de publicações

O pacote enriquece as publicações canônicas geradas pela Parte 1 do PPGI.
Ele não altera a pontuação.

## Fontes

A cadeia padrão de citações é:

```text
Google Scholar
  → resultado bibliográfico resolvido: usa google_scholar.citations
  → resultado não resolvido: consulta OpenAlex
```

Uma contagem Scholar igual a zero é um resultado válido. Ela não aciona o
fallback. Quando o OpenAlex é usado, a métrica continua identificada como
`openalex.cited_by_count`.

Crossref executa como fonte auxiliar de identidade. Seus resultados não
interrompem a cadeia de citações.

## Associação Scholar

A pesquisa usa `intitle:"título"`. Um vínculo exige:

- título normalizado igual;
- ano compatível, quando disponível;
- autores disponíveis não incompatíveis;
- autor ou veículo compatível quando a publicação não tem DOI.

Resultados múltiplos compatíveis recebem `AMBIGUO`. Páginas de verificação
recebem `LIMITE_EXCEDIDO`.

O provedor espera 2,5 segundos mais um jitter de até 1 segundo entre
requisições. Esses valores são configuráveis em `config-metricas.json`.
O agente HTTP pode ser definido pela variável `GOOGLE_SCHOLAR_USER_AGENT`.

## Referências de implementação

O formato de consulta por título segue o projeto público
[qLattes](https://github.com/nabormendonca/qlattes), licenciado sob MIT.

Os snapshots, o intervalo entre requisições e os seletores conhecidos do
Google Scholar foram estudados na extensão
[Scholar Watch](https://chromewebstore.google.com/detail/scholar-watch/maljdgiokfadogmhohcbkeoglbajecjl).
O Scholar Watch não publica licença de código. Esta implementação é própria e
não copia seu código.

## Relatórios

`*_metricas_ranking.csv` classifica publicações dentro de cada fonte. O arquivo
não soma e não converte contagens de fontes diferentes.
