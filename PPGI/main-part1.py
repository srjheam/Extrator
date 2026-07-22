import os
import sys

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
    qualis_conferencia = QualisConferencia(ppgi_config['qualis_c'])
    
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
