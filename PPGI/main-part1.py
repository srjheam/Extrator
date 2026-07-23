import os
import sys
import hashlib
import json

# Adiciona o diretório pai aos caminhos de importação
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import argparse
import PontuacaoPPGI.utils as ppgiu

from Classificador.Qualis import Qualis
from PontuacaoPPGI.PessoaPPGI import PessoaPPGI
from Classificador.QualisConferencia import QualisConferencia


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Arquivo de configuração")
    parser.add_argument('config', type=argparse.FileType('r'), help="Arquivo de configuração")

    args = parser.parse_args()

    ppgi_config = ppgiu.config_json(args.config.name)
    
    # 1. reading
    docentes = []
    qualis_journal = Qualis(ppgi_config['qualis_j'])
    qualis_conferencia = QualisConferencia(ppgi_config['qualis_c'], overrides_path=ppgi_config['overrides_qualis'])
    
    with open(ppgi_config['lista_file']) as f:
        for line in f:
            print('Processing', line.strip())            
            if line.strip().startswith('#'):
                continue
            lattesId, name = [x.strip() for x in line.strip().split(',')]
            if lattesId != '':
                docente = PessoaPPGI(name)
                docente.carrega_producoes_by_lattes(os.path.join(ppgi_config['curriculo_dir'], lattesId + '.xml'), int(ppgi_config['ano_inicio_conferencia']), int(ppgi_config['ano_fim_conferencia']), int(ppgi_config['ano_inicio_periodico']), int(ppgi_config['ano_fim_periodico']), True)
                docente.atualiza_estratos(qualis_journal, qualis_conferencia)

                docentes.append(docente)

    os.makedirs(ppgi_config['dir_out'], exist_ok=True)
    ocorrencias_path = ppgi_config['publicacoes_ocorrencias']
    ppgiu.gera_publicacoes_ocorrencias_csv(ocorrencias_path, docentes)
    linhas = ppgiu.pd.read_csv(ocorrencias_path, dtype=str, keep_default_na=False).to_dict('records')
    for linha in linhas:
        linha['ano'] = int(linha['ano'])
        linha['sequencia'] = int(linha.get('sequencia') or 0)
    resultado = ppgiu.deduplicar_publicacoes(linhas, overrides=ppgiu.ler_overrides(ppgi_config['overrides_deduplicacao']))
    prefixo = str(ppgi_config['ano_fim_conferencia'])
    ppgiu.gera_deduplicacao_csvs(ppgi_config['dir_out'], prefixo, resultado)
    revisao_nome = str(ppgi_config['ano_fim_conferencia']) + '_qualis_revisao.csv'
    ppgiu.gera_qualis_revisao_csv(os.path.join(ppgi_config['dir_out'], revisao_nome), docentes)
    # Publish this file last. Consumers use it as the completion marker.
    files = [f'{prefixo}_publicacoes_ocorrencias.csv', f'{prefixo}_publicacoes_unicas.csv',
             f'{prefixo}_publicacoes_membros.csv', f'{prefixo}_deduplicacao_decisoes.csv',
             f'{prefixo}_deduplicacao_revisao.csv']
    def digest(path):
        with open(path, 'rb') as stream: return hashlib.sha256(stream.read()).hexdigest()
    out = ppgi_config['dir_out']
    manifest = {'schema_versao': '3', 'politica_versao': '2',
                'arquivos': {name: digest(os.path.join(out, name)) for name in files},
                'sha256_overrides_deduplicacao': digest(ppgi_config['overrides_deduplicacao']),
                'quantidade_revisoes': len(resultado.revisoes), 'quantidade_ocorrencias': len(resultado.ocorrencias),
                'quantidade_publicacoes_canonicas': len(resultado.publicacoes_unicas),
                'status': 'REVISAO_PENDENTE' if resultado.revisoes else 'SUCESSO', 'metricas': resultado.metricas}
    with open(os.path.join(out, f'{prefixo}_deduplicacao_manifest.json'), 'w', encoding='utf-8') as stream:
        json.dump(manifest, stream, ensure_ascii=False, indent=2, sort_keys=True)
