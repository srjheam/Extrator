"""Regras conservadoras para identidade externa e métricas."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import hashlib
import json
from typing import Iterable

from Deduplicacao.core import doi_valido, normalizar, normalizar_doi

POLITICA_METRICAS_V1 = {"versao": "1", "descricao": "DOI exige metadados compatíveis; buscas sem DOI sempre vão para revisão."}
SCHEMA_VERSAO = "1"

ESTADOS_FINAIS = {"RESOLVIDO", "NAO_ENCONTRADO", "AMBIGUO", "DOI_INCOMPATIVEL", "REVISAO_DEDUPLICACAO", "CREDENCIAL_AUSENTE"}


def agora():
    return datetime.now(timezone.utc).isoformat()


def fingerprint(publicacao):
    campos = (publicacao.get("tipo", ""), publicacao.get("titulo", ""), publicacao.get("ano", ""), publicacao.get("venue", "") or publicacao.get("revista", ""), publicacao.get("autores", ""))
    return hashlib.sha256("|".join(normalizar(x) for x in campos).encode()).hexdigest()


def _compativel(local, externo):
    """Não aceita DOI quando os metadados disponíveis entram em conflito."""
    if normalizar_doi(local.get("doi")) != normalizar_doi(externo.get("doi")):
        return False, "DOI incompatível"
    if normalizar(local.get("titulo")) != normalizar(externo.get("title")):
        return False, "título incompatível"
    ano_local, ano_externo = str(local.get("ano") or ""), str(externo.get("year") or "")
    if ano_local and ano_externo and ano_local != ano_externo:
        return False, "ano incompatível"
    tipo = normalizar(local.get("tipo"))
    externo_tipo = normalizar(externo.get("type"))
    if tipo and externo_tipo and (("period" in tipo and externo_tipo not in {"journal article", "article"}) or ("confer" in tipo and "proceedings" not in externo_tipo)):
        return False, "tipo incompatível"
    issn_local = normalizar(local.get("issn"))
    issns = {normalizar(x) for x in externo.get("issn", [])}
    if issn_local and issns and issn_local not in issns:
        return False, "ISSN incompatível"
    return True, ""


@dataclass
class ResultadoEnriquecimento:
    snapshot_id: str
    identidades: list[dict] = field(default_factory=list)
    metricas: list[dict] = field(default_factory=list)
    revisoes: list[dict] = field(default_factory=list)


def enriquecer_publicacoes(publicacoes_canonicas, provedores, repositorio, politica=POLITICA_METRICAS_V1, snapshot_id=None, modo="online", revisao_deduplicacao=(), refresh=False):
    snapshot_id = snapshot_id or repositorio.criar_snapshot(politica["versao"], modo)
    resultado = ResultadoEnriquecimento(snapshot_id)
    bloqueados = set(revisao_deduplicacao)
    for publicacao in publicacoes_canonicas:
        canonica_id = publicacao["publicacao_canonica_id"]
        fp = fingerprint(publicacao)
        if canonica_id in bloqueados:
            identidade = _identidade(publicacao, snapshot_id, "deduplicacao", "", "REVISAO_DEDUPLICACAO", fp)
            repositorio.salvar_identidade(identidade); resultado.identidades.append(identidade); continue
        for provedor in provedores:
            identidade, metricas, revisao = _enriquecer_um(publicacao, provedor, repositorio, snapshot_id, modo, fp, refresh)
            repositorio.salvar_identidade(identidade)
            repositorio.salvar_metricas(metricas)
            if revisao: repositorio.salvar_revisao(revisao); resultado.revisoes.append(revisao)
            resultado.identidades.append(identidade); resultado.metricas.extend(metricas)
    repositorio.finalizar_snapshot(snapshot_id)
    return resultado


def _identidade(p, snapshot_id, provedor, externo, status, fp, evidencias=None, conflitos=None):
    return {"schema_versao": SCHEMA_VERSAO, "snapshot_id": snapshot_id, "publicacao_canonica_id": p["publicacao_canonica_id"], "impressao_canonica": fp, "provedor": provedor, "identificador_externo": externo, "doi_consultado": normalizar_doi(p.get("doi")), "status": status, "evidencias_json": json.dumps(evidencias or {}, ensure_ascii=False), "conflitos_json": json.dumps(conflitos or {}, ensure_ascii=False), "politica_versao": POLITICA_METRICAS_V1["versao"], "resolvido_em": agora()}


def _enriquecer_um(p, provedor, repo, snapshot_id, modo, fp, refresh):
    doi = normalizar_doi(p.get("doi"))
    if not doi_valido(doi):
        identidade = _identidade(p, snapshot_id, provedor.nome, "", "AMBIGUO", fp)
        revisao = {"schema_versao": SCHEMA_VERSAO, "snapshot_id": snapshot_id, "publicacao_canonica_id": p["publicacao_canonica_id"], "impressao_canonica": fp, "provedor": provedor.nome, "metadados_locais_json": json.dumps(p, ensure_ascii=False), "candidatos_json": "[]", "evidencias_json": "{}", "conflitos_json": "{}", "motivo": "publicação sem DOI exige decisão humana", "decisao_humana": "", "identificador_escolhido": "", "justificativa": "", "decidido_em": "", "politica_versao": POLITICA_METRICAS_V1["versao"]}
        return identidade, [], revisao
    resposta = None if refresh else repo.obter_consulta(provedor.nome, "doi", doi)
    if not resposta:
        if modo == "offline": return _identidade(p, snapshot_id, provedor.nome, "", "CACHE_AUSENTE", fp), [], None
        resposta = provedor.resolver_por_doi(p, doi)
        repo.salvar_consulta(provedor.nome, "doi", doi, resposta)
    if resposta["status"] != "RESOLVIDO":
        return _identidade(p, snapshot_id, provedor.nome, "", resposta["status"], fp, resposta.get("evidencias")), [], None
    externo = resposta["identidade"]
    ok, motivo = _compativel(p, externo)
    if not ok: return _identidade(p, snapshot_id, provedor.nome, externo.get("id", ""), "DOI_INCOMPATIVEL", fp, externo, {"motivo": motivo}), [], None
    identidade = _identidade(p, snapshot_id, provedor.nome, externo.get("id", ""), "RESOLVIDO", fp, externo)
    metricas = []
    for metrica in resposta.get("metricas", []):
        metricas.append({"schema_versao": SCHEMA_VERSAO, "snapshot_id": snapshot_id, "publicacao_canonica_id": p["publicacao_canonica_id"], "provedor": provedor.nome, "identificador_externo": externo.get("id", ""), "obtida_em": agora(), "endpoint_versao": provedor.endpoint_versao, "status": "RESOLVIDO", **metrica})
    return identidade, metricas, None
