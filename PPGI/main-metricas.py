"""Executa métricas externas após a Parte 1, sem mudar a pontuação."""
import argparse, csv, json, os, sys
from types import SimpleNamespace
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from Metricas import RepositorioMetricasSQLite, enriquecer_publicacoes
from Metricas.providers import CrossrefProvider, GoogleScholarProvider, OpenAlexProvider
from Metricas.reports import exportar

def ler_csv(caminho):
    with open(caminho, newline='', encoding='utf-8-sig') as f: return list(csv.DictReader(f))
def main():
    p=argparse.ArgumentParser(); p.add_argument('config', nargs='?', default='DadosPPGI/config-metricas.json'); p.add_argument('--offline', action='store_true'); p.add_argument('--refresh', action='store_true'); p.add_argument('--snapshot-id'); a=p.parse_args()
    if a.offline and a.refresh:
        p.error('--offline não pode ser usado com --refresh')
    with open(a.config, encoding='utf-8') as f: c=json.load(f)
    unicas=ler_csv(c['arquivo_publicacoes_unicas']); ocorrencias=ler_csv(c['arquivo_publicacoes_ocorrencias']) if os.path.exists(c['arquivo_publicacoes_ocorrencias']) else []
    pendentes_ocorrencias=set()
    if os.path.exists(c['arquivo_deduplicacao_revisao']):
        for r in ler_csv(c['arquivo_deduplicacao_revisao']): pendentes_ocorrencias.update((r.get('ocorrencia_a',''),r.get('ocorrencia_b','')))
    pendentes={x.get('publicacao_canonica_id','') for x in ocorrencias if x.get('ocorrencia_id','') in pendentes_ocorrencias}
    scholar_config=c.get('google_scholar', {})
    providers={
        'crossref':CrossrefProvider(),
        'google_scholar':GoogleScholarProvider(
            intervalo_minimo=float(scholar_config.get('intervalo_minimo_segundos', 2.5)),
            jitter=float(scholar_config.get('jitter_segundos', 1.0)),
        ),
        'openalex':OpenAlexProvider(),
    }
    repo=RepositorioMetricasSQLite(c['arquivo_cache'])
    if a.snapshot_id:
        if a.refresh:
            p.error('--refresh não pode ser usado com --snapshot-id')
        if not repo.existe_snapshot(a.snapshot_id):
            p.error('snapshot_id não encontrado')
        resultado=SimpleNamespace(snapshot_id=a.snapshot_id)
    else:
        nomes_citacoes=c.get('provedores_citacoes', c.get('provedores', ['google_scholar', 'openalex']))
        nomes_identidade=c.get('provedores_identidade', [])
        desconhecidos=(set(nomes_citacoes) | set(nomes_identidade)) - set(providers)
        if desconhecidos:
            p.error('provedor desconhecido: ' + ', '.join(sorted(desconhecidos)))
        resultado=enriquecer_publicacoes(
            unicas,
            [providers[x] for x in nomes_citacoes],
            repo,
            modo='offline' if a.offline else 'online',
            revisao_deduplicacao=pendentes,
            refresh=a.refresh,
            estrategia_provedores=c.get('estrategia_provedores', 'fallback'),
            provedores_independentes=[providers[x] for x in nomes_identidade],
        )
    prefixo=Path(c['arquivo_publicacoes_unicas']).name.split('_')[0]
    exportar(repo, resultado.snapshot_id, c['diretorio_saida'], prefixo, ocorrencias); print(resultado.snapshot_id)
if __name__ == '__main__': main()
