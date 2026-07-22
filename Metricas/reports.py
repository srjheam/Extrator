"""Exportações CSV. Métricas de fontes diferentes não são somadas."""
from __future__ import annotations
import csv, json, os

def _csv(path, rows, columns):
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        w=csv.DictWriter(f, fieldnames=columns, extrasaction="ignore"); w.writeheader(); w.writerows(rows)

def exportar(repo, snapshot_id, diretorio, prefixo, ocorrencias=()):
    os.makedirs(diretorio, exist_ok=True)
    identidades=repo.itens("identidade", snapshot_id); metricas=repo.itens("metrica_snapshot", snapshot_id); revisoes=repo.itens("revisao", snapshot_id)
    consultas=[{"schema_versao":"1", **x} for x in repo.consultas(snapshot_id)]
    bases={"identidades":identidades,"publicacoes":metricas,"veiculos":[],"revisao":revisoes,"consultas":consultas}
    for nome, linhas in bases.items():
        cols=sorted({k for x in linhas for k in x} | {"schema_versao","snapshot_id"})
        _csv(os.path.join(diretorio, f"{prefixo}_metricas_{nome}.csv"), linhas, cols)
    por_docente=[]
    vinculos_vistos=set()
    for o in ocorrencias:
        for m in metricas:
            if m["publicacao_canonica_id"] == o.get("publicacao_canonica_id"):
                chave=(o.get("Docente",""),m["publicacao_canonica_id"],m["provedor"],m["nome_metrica"],m.get("periodo_inicio",""),m.get("periodo_fim",""))
                if chave in vinculos_vistos: continue
                vinculos_vistos.add(chave)
                por_docente.append({"schema_versao":"1","snapshot_id":snapshot_id,"Docente":o.get("Docente",""), **m})
    _csv(os.path.join(diretorio, f"{prefixo}_metricas_docentes.csv"), por_docente, sorted({k for x in por_docente for k in x} | {"schema_versao","snapshot_id","Docente"}))
    resumo={}
    for m in metricas:
        chave=(m["provedor"],m["nome_metrica"],m.get("periodo_inicio",""),m.get("periodo_fim","")); resumo.setdefault(chave, {"schema_versao":"1","snapshot_id":snapshot_id,"provedor":chave[0],"nome_metrica":chave[1],"periodo_inicio":chave[2],"periodo_fim":chave[3],"publicacoes_com_metrica":0})["publicacoes_com_metrica"] += 1
    _csv(os.path.join(diretorio, f"{prefixo}_metricas_resumo.csv"), list(resumo.values()), ["schema_versao","snapshot_id","provedor","nome_metrica","periodo_inicio","periodo_fim","publicacoes_com_metrica"])
    _exportar_ranking(metricas, ocorrencias, snapshot_id, os.path.join(diretorio, f"{prefixo}_metricas_ranking.csv"))


def _exportar_ranking(metricas, ocorrencias, snapshot_id, caminho):
    principais={"google_scholar.citations","openalex.cited_by_count"}
    publicacoes={}
    for ocorrencia in ocorrencias:
        canonica_id=ocorrencia.get("publicacao_canonica_id","")
        atual=publicacoes.get(canonica_id)
        if atual is None or ocorrencia.get("ocorrencia_id") == canonica_id:
            publicacoes[canonica_id]=ocorrencia
    grupos={}
    for metrica in metricas:
        if metrica.get("nome_metrica") not in principais: continue
        grupos.setdefault((metrica["provedor"],metrica["nome_metrica"]),[]).append(metrica)
    linhas=[]
    for (provedor,nome), itens in sorted(grupos.items()):
        itens.sort(key=lambda x: (-(float(x["valor"]) if x.get("valor") is not None else -1),x["publicacao_canonica_id"]))
        for posicao, metrica in enumerate(itens, 1):
            publicacao=publicacoes.get(metrica["publicacao_canonica_id"],{})
            linhas.append({
                "schema_versao":"1","snapshot_id":snapshot_id,"ranking_na_fonte":posicao,
                "publicacao_canonica_id":metrica["publicacao_canonica_id"],"titulo":publicacao.get("titulo",""),
                "ano":publicacao.get("ano",""),"tipo":publicacao.get("tipo",""),
                "veiculo":publicacao.get("venue") or publicacao.get("revista","") ,"provedor":provedor,
                "papel_provedor":metrica.get("papel_provedor",""),"fallback_acionado_por":metrica.get("fallback_acionado_por",""),
                "nome_metrica":nome,"valor":metrica.get("valor"),"unidade":metrica.get("unidade",""),
            })
    colunas=["schema_versao","snapshot_id","ranking_na_fonte","publicacao_canonica_id","titulo","ano","tipo","veiculo","provedor","papel_provedor","fallback_acionado_por","nome_metrica","valor","unidade"]
    _csv(caminho,linhas,colunas)
