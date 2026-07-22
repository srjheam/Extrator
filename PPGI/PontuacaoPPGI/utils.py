import json
import os

import pandas as pd

from ArquivoInterno.enums.NaturezaTrabalho import NaturezaTrabalho
from ArquivoInterno.enums import NaturezaArtigo
from PontuacaoPPGI.Conference import Conference
from PontuacaoPPGI.Journal import Journal
from PontuacaoPPGI.NotaInfo import NotaInfo
from PontuacaoPPGI.PessoaPPGI import PessoaPPGI
from Deduplicacao import deduplicar_publicacoes
from Deduplicacao.core import ler_overrides

def config_json(json_path: str):
    config_d = {}
    with open(json_path, 'r') as f:
        json_parsed = json.load(f)

        config_d['ano_inicio_conferencia'] = json_parsed["ano_inicio_conferencia"]

        config_d['ano_fim_conferencia'] = json_parsed['ano_fim_conferencia']

        config_d['ano_inicio_periodico'] = json_parsed["ano_inicio_periodico"]

        config_d['ano_fim_periodico'] = json_parsed['ano_fim_periodico']

        config_d['lista_file'] = json_parsed['arquivo_lista_docentes']

        config_d['curriculo_dir'] = json_parsed['diretorio_curriculos']

        config_d['dir_out'] = json_parsed['diretorio_saida']

        config_d['docente_file'] = json_parsed['arquivo_nota_docente']

        config_d['geral_file'] = json_parsed['arquivo_nota_geral']

        config_d['qualis_j'] = json_parsed['arquivo_qualis_journal']

        config_d['qualis_c'] = json_parsed['arquivo_qualis_conference']

        config_d['nota_info'] = json_parsed['config_pontuacao']
        
        config_d['publicacoes_ocorrencias'] = json_parsed['arquivo_publicacoes_ocorrencias']
        config_d['overrides_deduplicacao'] = json_parsed.get('arquivo_overrides_deduplicacao', 'DadosPPGI/input/publicacoes_deduplicacao_overrides.csv')


    return config_d

def all_jornal_conferences(docentes: list[PessoaPPGI]):
    journals = []
    conferences = []

    for docente in docentes:
        for prod in docente.get_producoes():
            if isinstance(prod, Journal):
                journals.append(prod)
            elif isinstance(prod, Conference):
                if prod.get_natureza() is not NaturezaTrabalho.COMPLETO:
                    continue
                
                conferences.append(prod)

    return journals, conferences

def create_csv_writer(path, nota_info: NotaInfo):
    csv_file = open(path, 'w')

    min_intervalo = nota_info.get_prod_min_intervalo()
    print(f'Docente;Bolsista de Produtividade (PQ ou DT);Nota Docente;{nota_info.get_prod_min_tag()}({min_intervalo[0]}-{min_intervalo[1]});Regra: B > 0 OU (C >= {nota_info.get_nota_min_value()} E D >= {nota_info.get_prod_min_qtd()})', file=csv_file)

    return csv_file

def _linha_ocorrencia(docente, producao):
    metadados = producao.get_metadados() if hasattr(producao, 'get_metadados') else None
    p = getattr(metadados, 'proveniencia', None)
    autores = getattr(metadados, 'autores_detalhados', ())
    tipo = 'Periódico' if isinstance(producao, Journal) else 'Conferência'
    local = producao.get_revista() if tipo == 'Periódico' else producao.get_venue()
    resultado = producao.get_qualis_match() if isinstance(producao, Conference) else {}
    return {
        'schema_versao': '1', 'Docente': docente.get_nome(), 'tipo': tipo, 'ano': producao.get_ano(),
        'titulo': producao.get_titulo(), 'venue': local, 'revista': local if tipo == 'Periódico' else '',
        'issn': producao.get_issn() if tipo == 'Periódico' else getattr(metadados, 'issn', ''),
        'doi': getattr(metadados, 'doi', ''), 'isbn': getattr(metadados, 'isbn', ''),
        'autores': json.dumps([a.nome_citacao or a.nome for a in autores] or producao.get_autores(), ensure_ascii=False),
        'curriculo_id': getattr(p, 'curriculo_id', ''), 'arquivo_xml': getattr(p, 'arquivo_xml', ''),
        'sequencia': getattr(p, 'sequencia', 0), 'estrato': producao.get_estrato() or '',
        'qualis_status': (resultado or {}).get('qualis_status', ''),
        'qualis_requer_revisao': (resultado or {}).get('qualis_requer_revisao', False),
        'qualis_candidatos': (resultado or {}).get('qualis_candidatos', ''),
    }


def gera_publicacoes_ocorrencias_csv(csv_out_path, docentes):
    linhas = []
    for docente in docentes:
        for producao in docente.get_producoes():
            if isinstance(producao, Journal) or (isinstance(producao, Conference) and producao.get_natureza() is NaturezaTrabalho.COMPLETO):
                linhas.append(_linha_ocorrencia(docente, producao))
    pd.DataFrame(linhas).to_csv(csv_out_path, index=False, encoding='utf-8-sig')
    return linhas


def _producao_por_linha(linha, canonical_id=''):
    autores = json.loads(linha.get('autores') or '[]')
    ano = int(linha['ano'])
    if linha['tipo'] == 'Periódico':
        producao = Journal(ano, '', linha.get('issn', ''), NaturezaArtigo.COMPLETO, linha.get('titulo', ''), linha.get('revista') or linha.get('venue', ''), autores, linha.get('estrato') or None)
    else:
        producao = Conference(ano, '', NaturezaTrabalho.COMPLETO, None, linha.get('titulo', ''), linha.get('venue', ''), autores, linha.get('estrato') or None)
    producao._publicacao_canonica_id = canonical_id
    return producao


def docentes_por_ocorrencias(csv_path, overrides=()):
    linhas = pd.read_csv(csv_path, dtype=str, keep_default_na=False).to_dict('records')
    for linha in linhas:
        linha['ano'] = int(linha['ano'])
        linha['sequencia'] = int(linha.get('sequencia') or 0)
    resultado = deduplicar_publicacoes(linhas, overrides=overrides)
    linhas_por_id = {resultado.ids_ocorrencia[id(linha)]: linha for linha in linhas}
    docentes = {}
    vistos = set()
    for ocorrencia_id, canonica_id in resultado.canonica_por_ocorrencia.items():
        linha = linhas_por_id[ocorrencia_id]
        chave = (linha['Docente'], canonica_id)
        if chave in vistos: continue
        vistos.add(chave)
        docentes.setdefault(linha['Docente'], PessoaPPGI(linha['Docente'])).insere_producao(_producao_por_linha(linhas_por_id[canonica_id], canonica_id))
    return list(docentes.values()), resultado


def gera_deduplicacao_csvs(dir_out, prefixo, resultado):
    linhas = []
    for item in resultado.ocorrencias:
        item_id = resultado.ids_ocorrencia[id(item)]
        linha = dict(item) if isinstance(item, dict) else {}
        linha.update({'ocorrencia_id': item_id, 'publicacao_canonica_id': resultado.canonica_por_ocorrencia[item_id]})
        linhas.append(linha)
    colunas_ocorrencias = ['schema_versao', 'Docente', 'tipo', 'ano', 'titulo', 'venue', 'revista', 'issn', 'doi', 'isbn', 'autores', 'curriculo_id', 'arquivo_xml', 'sequencia', 'estrato', 'qualis_status', 'qualis_requer_revisao', 'qualis_candidatos', 'ocorrencia_id', 'publicacao_canonica_id']
    pd.DataFrame(linhas, columns=colunas_ocorrencias).to_csv(os.path.join(dir_out, prefixo + '_publicacoes_ocorrencias.csv'), index=False, encoding='utf-8-sig')
    canonicas = [linha for linha in linhas if linha['ocorrencia_id'] == linha['publicacao_canonica_id']]
    pd.DataFrame(canonicas, columns=colunas_ocorrencias).to_csv(os.path.join(dir_out, prefixo + '_publicacoes_unicas.csv'), index=False, encoding='utf-8-sig')
    colunas_decisao = ['ocorrencia_a', 'ocorrencia_b', 'decisao', 'motivo', 'score_titulo']
    pd.DataFrame([d.__dict__ for d in resultado.decisoes], columns=colunas_decisao).to_csv(os.path.join(dir_out, prefixo + '_deduplicacao_decisoes.csv'), index=False, encoding='utf-8-sig')
    pd.DataFrame([d.__dict__ for d in resultado.revisoes], columns=colunas_decisao).to_csv(os.path.join(dir_out, prefixo + '_deduplicacao_revisao.csv'), index=False, encoding='utf-8-sig')


# Compatibilidade de biblioteca para consumidores antigos. As etapas PPGI não
# usam esta função e não aceitam este formato como entrada.
def gera_recredenciamento_csv(csv_out_path, docentes):
    linhas = []
    for docente in docentes:
        for producao in docente.get_producoes():
            if isinstance(producao, Journal):
                linhas.append({'Docente': docente.get_nome(), 'Tipo': 'Periódico', 'Qualis': producao.get_estrato() or 'Qualis não identificado', 'Ano': producao.get_ano(), 'Local': producao.get_revista(), 'Título': producao.get_titulo()})
            elif isinstance(producao, Conference) and producao.get_natureza() is NaturezaTrabalho.COMPLETO:
                linhas.append({'Docente': docente.get_nome(), 'Tipo': 'Conferência', 'Qualis': producao.get_estrato() or 'Qualis não identificado', 'Ano': producao.get_ano(), 'Local': producao.get_venue(), 'Título': producao.get_titulo()})
    pd.DataFrame(linhas, columns=['Docente', 'Tipo', 'Qualis', 'Ano', 'Local', 'Título']).to_csv(csv_out_path, index=False)


def gera_qualis_revisao_csv(csv_out_path: str, docentes: list[PessoaPPGI]):
    """Exporta diagnósticos de conferências sem decisão automática."""
    linhas = []
    for docente in docentes:
        for producao in docente.get_producoes():
            if not isinstance(producao, Conference):
                continue
            resultado = producao.get_qualis_match() or {}
            if not resultado.get("qualis_requer_revisao"):
                continue
            linhas.append({
                "Docente": docente.get_nome(),
                "Título": producao.get_titulo(),
                "Ano": producao.get_ano(),
                "Evento informado": producao.get_venue(),
                "Status": resultado.get("qualis_status"),
                "Candidatos": resultado.get("qualis_candidatos"),
                "Score primeiro": resultado.get("qualis_score_fuzzy"),
                "Margem segundo": resultado.get("qualis_score_margem"),
                "Motivo": resultado.get("qualis_obs") or resultado.get("qualis_llm_motivo"),
            })
    colunas = ["Docente", "Título", "Ano", "Evento informado", "Status", "Candidatos", "Score primeiro", "Margem segundo", "Motivo"]
    pd.DataFrame(linhas, columns=colunas).to_csv(csv_out_path, index=False, encoding="utf-8-sig")
