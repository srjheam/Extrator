"""Adaptadores HTTP das fontes abertas do MVP."""
from __future__ import annotations
import os, time
import requests

class ProvedorMetricas:
    nome = "base"; endpoint_versao = "v1"
    def resolver_por_doi(self, publicacao, doi): raise NotImplementedError

    def _get(self, url, params=None, headers=None):
        for tentativa in range(3):
            try:
                r = requests.get(url, params=params, headers=headers, timeout=(5, 30))
                if r.status_code == 404: return None, "NAO_ENCONTRADO"
                if r.status_code in (401, 403): return None, "CREDENCIAL_AUSENTE"
                if r.status_code == 429 or r.status_code >= 500:
                    time.sleep(int(r.headers.get("Retry-After", 2 ** tentativa)))
                    continue
                r.raise_for_status(); return r.json(), "RESOLVIDO"
            except (requests.Timeout, requests.ConnectionError, ValueError):
                if tentativa == 2: return None, "ERRO_TEMPORARIO"
                time.sleep(2 ** tentativa)
            except requests.RequestException: return None, "ERRO_PERMANENTE"
        return None, "LIMITE_EXCEDIDO"

class CrossrefProvider(ProvedorMetricas):
    nome = "crossref"; endpoint_versao = "works/v1"
    def resolver_por_doi(self, publicacao, doi):
        headers = {"User-Agent": "Extrator-Metricas/1.0"}
        if os.getenv("CROSSREF_MAILTO"): headers["User-Agent"] += " (mailto:" + os.environ["CROSSREF_MAILTO"] + ")"
        dados, status = self._get("https://api.crossref.org/works/" + doi, headers=headers)
        if status != "RESOLVIDO": return {"status": status}
        m = dados["message"]
        identidade = {"id": m.get("DOI", "").lower(), "doi": m.get("DOI", "").lower(), "title": (m.get("title") or [""])[0], "year": str((m.get("published", {}).get("date-parts", [[""]])[0] or [""])[0]), "type": m.get("type", ""), "issn": m.get("ISSN", [])}
        return {"status":"RESOLVIDO", "identidade":identidade, "metricas":[{"nome_metrica":"crossref.is_referenced_by_count", "valor":m.get("is-referenced-by-count"), "unidade":"citacoes", "periodo_inicio":"", "periodo_fim":"", "categoria":""}]}

class OpenAlexProvider(ProvedorMetricas):
    nome = "openalex"; endpoint_versao = "works/v1"
    def resolver_por_doi(self, publicacao, doi):
        params = {"filter": "doi:https://doi.org/" + doi}
        if os.getenv("OPENALEX_API_KEY"): params["api_key"] = os.environ["OPENALEX_API_KEY"]
        dados, status = self._get("https://api.openalex.org/works", params=params)
        if status != "RESOLVIDO": return {"status": status}
        resultados = dados.get("results", [])
        if not resultados: return {"status":"NAO_ENCONTRADO"}
        m = resultados[0]; fonte = m.get("primary_location", {}).get("source") or {}
        identidade = {"id":m.get("id", ""), "doi":(m.get("doi") or "").rsplit("/",1)[-1].lower(), "title":m.get("title", ""), "year":str(m.get("publication_year", "")), "type":m.get("type", ""), "issn":fonte.get("issn", [])}
        metricas = [{"nome_metrica":"openalex.cited_by_count", "valor":m.get("cited_by_count"), "unidade":"citacoes", "periodo_inicio":"", "periodo_fim":"", "categoria":""}]
        for ano, valor in (m.get("counts_by_year") or []): metricas.append({"nome_metrica":"openalex.citations_in_year", "valor":valor.get("cited_by_count"), "unidade":"citacoes", "periodo_inicio":str(ano.get("year")), "periodo_fim":str(ano.get("year")), "categoria":""})
        return {"status":"RESOLVIDO", "identidade":identidade, "metricas":metricas}
