"""Exportações CSV. Métricas de fontes diferentes não são somadas."""
from __future__ import annotations
import csv, json, os

def _csv(path, rows, columns):
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        w=csv.DictWriter(f, fieldnames=columns, extrasaction="ignore"); w.writeheader(); w.writerows(rows)

def exportar(repo, snapshot_id, diretorio, prefixo, ocorrencias=()):
    os.makedirs(diretorio, exist_ok=True)
    identidades=repo.itens("identidade", snapshot_id); metricas=repo.itens("metrica_snapshot", snapshot_id); revisoes=repo.itens("revisao", snapshot_id)
    consultas=[{"schema_versao":"1", "snapshot_id":snapshot_id, **x} for x in repo.consultas()]
    bases={"identidades":identidades,"publicacoes":metricas,"veiculos":[],"revisao":revisoes,"consultas":consultas}
    for nome, linhas in bases.items():
        cols=sorted({k for x in linhas for k in x} | {"schema_versao","snapshot_id"})
        _csv(os.path.join(diretorio, f"{prefixo}_metricas_{nome}.csv"), linhas, cols)
    por_docente=[]
    for o in ocorrencias:
        for m in metricas:
            if m["publicacao_canonica_id"] == o.get("publicacao_canonica_id"):
                por_docente.append({"schema_versao":"1","snapshot_id":snapshot_id,"Docente":o.get("Docente",""), **m})
    _csv(os.path.join(diretorio, f"{prefixo}_metricas_docentes.csv"), por_docente, sorted({k for x in por_docente for k in x} | {"schema_versao","snapshot_id","Docente"}))
    resumo={}
    for m in metricas:
        chave=(m["provedor"],m["nome_metrica"],m.get("periodo_inicio",""),m.get("periodo_fim","")); resumo.setdefault(chave, {"schema_versao":"1","snapshot_id":snapshot_id,"provedor":chave[0],"nome_metrica":chave[1],"periodo_inicio":chave[2],"periodo_fim":chave[3],"publicacoes_com_metrica":0})["publicacoes_com_metrica"] += 1
    _csv(os.path.join(diretorio, f"{prefixo}_metricas_resumo.csv"), list(resumo.values()), ["schema_versao","snapshot_id","provedor","nome_metrica","periodo_inicio","periodo_fim","publicacoes_com_metrica"])
