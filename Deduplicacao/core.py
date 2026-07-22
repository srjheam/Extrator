"""Regras conservadoras e determinísticas para deduplicar publicações."""
from __future__ import annotations

from dataclasses import dataclass, field
from difflib import SequenceMatcher
from hashlib import sha256
import csv
import re
import unicodedata
from typing import Any, Iterable


POLITICA_V1 = {
    "versao": "1",
    "titulo_fuzzy_minimo": 0.96,
    "ano_tolerancia": 0,
    "descricao": "DOI, tipo e conflitos estruturais bloqueiam agrupamento automático.",
}


def normalizar(valor: Any) -> str:
    texto = unicodedata.normalize("NFKD", str(valor or "")).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", " ", texto).strip()


def normalizar_doi(valor: Any) -> str:
    valor = str(valor or "").strip().lower()
    valor = re.sub(r"^(https?://(dx\.)?doi\.org/|doi:)\s*", "", valor)
    return valor.rstrip(" .;,)")


def doi_valido(valor: Any) -> bool:
    return bool(re.fullmatch(r"10\.\d{4,9}/[-._;()/:a-z0-9]+", normalizar_doi(valor)))


def _tipo(item: Any) -> str:
    if isinstance(item, dict):
        return item.get("tipo", "")
    return "Periódico" if hasattr(item, "get_revista") else "Conferência"


def _valor(item: Any, chave: str, padrao=""):
    if isinstance(item, dict):
        return item.get(chave, padrao)
    metadados = getattr(item, "get_metadados", lambda: None)()
    if chave in {"doi", "isbn", "volume", "fasciculo", "pagina_inicial", "pagina_final"}:
        return getattr(metadados, chave, padrao) if metadados else padrao
    mapa = {"ano": "get_ano", "titulo": "get_titulo", "issn": "get_issn", "venue": "get_venue", "revista": "get_revista", "autores": "get_autores"}
    metodo = mapa.get(chave)
    return getattr(item, metodo)() if metodo and hasattr(item, metodo) else padrao


def _proveniencia(item: Any):
    if isinstance(item, dict):
        return item.get("curriculo_id", ""), int(item.get("sequencia", 0) or 0)
    metadados = getattr(item, "get_metadados", lambda: None)()
    p = getattr(metadados, "proveniencia", None)
    return (getattr(p, "curriculo_id", ""), getattr(p, "sequencia", 0))


def id_ocorrencia(item: Any) -> str:
    curriculo, sequencia = _proveniencia(item)
    base = "|".join(map(str, (curriculo, _tipo(item), sequencia, normalizar(_valor(item, "titulo")), _valor(item, "ano"), normalizar_doi(_valor(item, "doi")))))
    return sha256(base.encode("utf-8")).hexdigest()[:20]


@dataclass
class Decisao:
    ocorrencia_a: str
    ocorrencia_b: str
    decisao: str
    motivo: str
    score_titulo: float = 0.0


@dataclass
class ResultadoDeduplicacao:
    ocorrencias: list[Any]
    ids_ocorrencia: dict[int, str]
    canonica_por_ocorrencia: dict[str, str]
    publicacoes_unicas: list[Any]
    decisoes: list[Decisao]
    revisoes: list[Decisao]
    metricas: dict[str, int] = field(default_factory=dict)


def _candidata(a, b):
    # Blocos reduzem pares e não decidem identidade.
    doi_a, doi_b = normalizar_doi(_valor(a, "doi")), normalizar_doi(_valor(b, "doi"))
    if doi_valido(doi_a) and doi_valido(doi_b) and doi_a == doi_b:
        return True
    titulo_a, titulo_b = normalizar(_valor(a, "titulo")), normalizar(_valor(b, "titulo"))
    if not titulo_a or not titulo_b:
        return False
    return titulo_a[:18] == titulo_b[:18] or (int(_valor(a, "ano", 0) or 0) == int(_valor(b, "ano", 0) or 0) and SequenceMatcher(None, titulo_a, titulo_b).ratio() >= .80)


def decidir_par(a, b, id_a, id_b, politica=POLITICA_V1) -> Decisao:
    if _tipo(a) != _tipo(b):
        return Decisao(id_a, id_b, "NAO_AGRUPAR", "tipos diferentes")
    doi_a, doi_b = normalizar_doi(_valor(a, "doi")), normalizar_doi(_valor(b, "doi"))
    if doi_valido(doi_a) and doi_valido(doi_b):
        if doi_a != doi_b:
            return Decisao(id_a, id_b, "NAO_AGRUPAR", "DOIs válidos diferentes")
        return Decisao(id_a, id_b, "AGRUPAR", "DOI válido idêntico", 1.0)
    ano_a, ano_b = int(_valor(a, "ano", 0) or 0), int(_valor(b, "ano", 0) or 0)
    if ano_a != ano_b:
        return Decisao(id_a, id_b, "NAO_AGRUPAR", "anos diferentes")
    local_a = normalizar(_valor(a, "revista") or _valor(a, "venue"))
    local_b = normalizar(_valor(b, "revista") or _valor(b, "venue"))
    issn_a, issn_b = normalizar(_valor(a, "issn")), normalizar(_valor(b, "issn"))
    if (issn_a and issn_b and issn_a != issn_b) or (local_a and local_b and local_a != local_b):
        return Decisao(id_a, id_b, "NAO_AGRUPAR", "conflito estrutural de veículo")
    titulo_a, titulo_b = normalizar(_valor(a, "titulo")), normalizar(_valor(b, "titulo"))
    score = SequenceMatcher(None, titulo_a, titulo_b).ratio()
    if titulo_a == titulo_b and (issn_a == issn_b or local_a == local_b or not (issn_a or issn_b or local_a or local_b)):
        return Decisao(id_a, id_b, "AGRUPAR", "título e estrutura idênticos", score)
    if score >= politica["titulo_fuzzy_minimo"] and (issn_a == issn_b or local_a == local_b) and (issn_a or local_a):
        return Decisao(id_a, id_b, "AGRUPAR", "título similar e veículo idêntico", score)
    if score >= .80:
        return Decisao(id_a, id_b, "REVISAO_MANUAL", "evidência insuficiente", score)
    return Decisao(id_a, id_b, "NAO_AGRUPAR", "títulos diferentes", score)


def _normalizar_overrides(overrides: Iterable[Any]):
    resposta = {}
    for item in overrides:
        if isinstance(item, dict):
            a, b, acao = item.get("ocorrencia_a", ""), item.get("ocorrencia_b", ""), item.get("acao", "")
        else:
            a, b, acao = item.ocorrencia_a, item.ocorrencia_b, item.acao
        if a and b and acao in {"AGRUPAR", "NAO_AGRUPAR"}:
            resposta[frozenset((a, b))] = acao
    return resposta


def ler_overrides(caminho):
    try:
        with open(caminho, newline="", encoding="utf-8-sig") as arquivo:
            return list(csv.DictReader(arquivo))
    except FileNotFoundError:
        return []


def deduplicar_publicacoes(ocorrencias, resolucoes_evento=None, overrides=(), politica=POLITICA_V1) -> ResultadoDeduplicacao:
    ocorrencias = list(ocorrencias)
    ids = {id(item): id_ocorrencia(item) for item in ocorrencias}
    parent = list(range(len(ocorrencias)))
    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]; x = parent[x]
        return x
    def union(a, b):
        a, b = find(a), find(b)
        if a != b: parent[max(a, b)] = min(a, b)
    def grupo(indice):
        raiz = find(indice)
        return [n for n in range(len(ocorrencias)) if find(n) == raiz]
    overrides = _normalizar_overrides(overrides)
    decisoes, revisoes, candidatos = [], [], 0
    for i, a in enumerate(ocorrencias):
        for j in range(i + 1, len(ocorrencias)):
            b = ocorrencias[j]
            if not _candidata(a, b): continue
            candidatos += 1
            chave = frozenset((ids[id(a)], ids[id(b)]))
            decisao = decidir_par(a, b, ids[id(a)], ids[id(b)], politica)
            if chave in overrides:
                decisao = Decisao(decisao.ocorrencia_a, decisao.ocorrencia_b, overrides[chave], "override versionado", decisao.score_titulo)
            decisoes.append(decisao)
            if decisao.decisao == "AGRUPAR":
                # Não permita que uma cadeia una registros que entram em
                # conflito entre si. Isto evita o efeito A~B~C.
                compativel = True
                for esquerdo in grupo(i):
                    for direito in grupo(j):
                        if esquerdo == direito:
                            continue
                        chave_grupo = frozenset((ids[id(ocorrencias[esquerdo])], ids[id(ocorrencias[direito])]))
                        teste = decidir_par(ocorrencias[esquerdo], ocorrencias[direito], ids[id(ocorrencias[esquerdo])], ids[id(ocorrencias[direito])], politica)
                        if chave_grupo in overrides:
                            teste.decisao = overrides[chave_grupo]
                        if teste.decisao != "AGRUPAR":
                            compativel = False
                if compativel:
                    union(i, j)
                else:
                    decisoes[-1] = Decisao(decisao.ocorrencia_a, decisao.ocorrencia_b, "REVISAO_MANUAL", "cadeia com conflito estrutural", decisao.score_titulo)
                    revisoes.append(decisoes[-1])
            elif decisao.decisao == "REVISAO_MANUAL": revisoes.append(decisao)
    grupos = {}
    for i, item in enumerate(ocorrencias): grupos.setdefault(find(i), []).append(item)
    unicas, canonicas = [], {}
    for grupo in grupos.values():
        # Mais DOI/ISSN/autores é mais estruturado. O ID resolve empates.
        canonica = max(grupo, key=lambda x: (sum(bool(_valor(x, k)) for k in ("doi", "issn", "isbn")), len(_valor(x, "autores", []) or []), -int(ids[id(x)], 16)))
        unicas.append(canonica)
        for item in grupo: canonicas[ids[id(item)]] = ids[id(canonica)]
    unicas.sort(key=lambda x: ids[id(x)])
    return ResultadoDeduplicacao(ocorrencias, ids, canonicas, unicas, decisoes, revisoes, {"ocorrencias": len(ocorrencias), "pares_candidatos": candidatos, "decisoes": len(decisoes), "revisoes": len(revisoes), "publicacoes_unicas": len(unicas)})
