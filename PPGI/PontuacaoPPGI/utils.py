import json

import pandas as pd

from ArquivoInterno.enums.NaturezaTrabalho import NaturezaTrabalho
from ArquivoInterno.enums import NaturezaArtigo
from PontuacaoPPGI.Conference import Conference
from PontuacaoPPGI.Journal import Journal
from PontuacaoPPGI.NotaInfo import NotaInfo
from PontuacaoPPGI.PessoaPPGI import PessoaPPGI

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
        
        config_d['rec_in'] = json_parsed['arquivo_recredenciamento_corrigido']

        config_d['rec_out'] = json_parsed['arquivo_recredenciamento_saida']


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

def docentes_by_csv(csv_path):
    df = pd.read_csv(csv_path)

    docentes = {}

    for index, row in df.iterrows():
        nome = row['Docente']
        tipo = row['Tipo']
        if nome not in docentes:
            docentes[nome] = PessoaPPGI(nome)
        
        if tipo == 'Conferência':
            docentes[nome].insere_producao(Conference(int(row['Ano']), '', NaturezaTrabalho.COMPLETO, None, row['Título'], row['Local'], [nome], row['Qualis']))
        elif tipo == 'Periódico':
            docentes[nome].insere_producao(Journal(int(row['Ano']), '', '', NaturezaArtigo.COMPLETO, row['Título'], row['Local'], [nome], row['Qualis']))
        
    return list(docentes.values())


def gera_recredenciamento_csv(csv_out_path: str, docentes: list[PessoaPPGI]):
    all_prods = []

    # Header
    header = 'Docente Tipo Qualis Ano Local Título'.split()

    for docente in docentes:
        for producao in docente.get_producoes():
            classificacao = ''
            if  isinstance(producao, Journal):
                classificacao = 'Periódico'
                local = producao.get_revista()
            elif isinstance(producao, Conference):
                # Considera apenas trabalho completo
                if producao.get_natureza() is not NaturezaTrabalho.COMPLETO:
                    continue
                classificacao = 'Conferência'
                local = producao.get_venue()
            
            if classificacao != '':
                estrato = producao.get_estrato()
                if estrato == None:
                    estrato = 'Qualis não identificado'
                all_prods.append({header[0]: docente.get_nome(), header[1]: classificacao, header[2]: estrato, header[3]: producao.get_ano(), header[4]: local, header[5]: producao.get_titulo()})       

    df = pd.DataFrame(all_prods)
    df.to_csv(csv_out_path, index=False)


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
