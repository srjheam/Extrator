"""Provedores de identidade e métricas bibliográficas."""
from __future__ import annotations

import hashlib
import json
import os
import random
import re
import time
from urllib.parse import parse_qs, urljoin, urlparse

from bs4 import BeautifulSoup
import requests

from Deduplicacao.core import doi_valido, normalizar, normalizar_doi


def _ano(texto):
    anos = re.findall(r"\b(?:18|19|20)\d{2}\b", texto or "")
    return anos[-1] if anos else ""


def _autores_locais(publicacao):
    autores = publicacao.get("autores") or []
    if isinstance(autores, str):
        try:
            autores = json.loads(autores)
        except (TypeError, ValueError):
            autores = [x.strip() for x in autores.split(",")]
    return [str(x).strip() for x in autores if str(x).strip()]


def _sobrenomes(autores):
    resposta = set()
    for autor in autores:
        partes = normalizar(autor).split()
        if partes:
            resposta.add(partes[-1])
    return resposta


def _autores_compativeis(locais, externos):
    if not locais or not externos:
        return True
    return bool(_sobrenomes(locais) & _sobrenomes(externos))


def _veiculo_local(publicacao):
    return publicacao.get("venue") or publicacao.get("revista") or ""


class ProvedorMetricas:
    nome = "base"
    endpoint_versao = "v1"
    aceita_sem_doi = False

    def __init__(self, session=None, sleep=time.sleep):
        self.session = session or requests.Session()
        self.sleep = sleep

    def chave_consulta(self, publicacao, doi):
        if doi_valido(doi):
            return "doi", doi
        chave = "|".join((normalizar(publicacao.get("titulo")), str(publicacao.get("ano") or "")))
        return "bibliografica", chave

    def consultar(self, publicacao, doi):
        if doi_valido(doi):
            return self.resolver_por_doi(publicacao, doi)
        if self.aceita_sem_doi:
            return self.buscar_candidatos(publicacao)
        return {"status": "AMBIGUO", "evidencias": {"motivo": "provedor requer DOI"}}

    def resolver_por_doi(self, publicacao, doi):
        raise NotImplementedError

    def buscar_candidatos(self, publicacao):
        return {"status": "AMBIGUO", "evidencias": {"motivo": "busca bibliográfica não implementada"}}

    def _get_json(self, url, params=None, headers=None):
        for tentativa in range(3):
            try:
                resposta = self.session.get(url, params=params, headers=headers, timeout=(5, 30))
                if resposta.status_code == 404:
                    return None, "NAO_ENCONTRADO"
                if resposta.status_code in (401, 403):
                    return None, "CREDENCIAL_AUSENTE"
                if resposta.status_code == 429 or resposta.status_code >= 500:
                    if tentativa < 2:
                        self.sleep(_retry_after(resposta, 2**tentativa))
                    continue
                resposta.raise_for_status()
                return resposta.json(), "RESOLVIDO"
            except (requests.Timeout, requests.ConnectionError, ValueError):
                if tentativa == 2:
                    return None, "ERRO_TEMPORARIO"
                self.sleep(2**tentativa)
            except requests.RequestException:
                return None, "ERRO_PERMANENTE"
        return None, "LIMITE_EXCEDIDO"


def _retry_after(resposta, padrao):
    try:
        return max(0, int(resposta.headers.get("Retry-After", padrao)))
    except (TypeError, ValueError):
        return padrao


class CrossrefProvider(ProvedorMetricas):
    nome = "crossref"
    endpoint_versao = "works/v1"

    def resolver_por_doi(self, publicacao, doi):
        headers = {"User-Agent": "Extrator-Metricas/1.0"}
        if os.getenv("CROSSREF_MAILTO"):
            headers["User-Agent"] += " (mailto:" + os.environ["CROSSREF_MAILTO"] + ")"
        dados, status = self._get_json("https://api.crossref.org/works/" + doi, headers=headers)
        if status != "RESOLVIDO":
            return {"status": status}
        mensagem = dados["message"]
        identidade = {
            "id": mensagem.get("DOI", "").lower(),
            "doi": mensagem.get("DOI", "").lower(),
            "title": (mensagem.get("title") or [""])[0],
            "year": str((mensagem.get("published", {}).get("date-parts", [[""]])[0] or [""])[0]),
            "type": mensagem.get("type", ""),
            "issn": mensagem.get("ISSN", []),
        }
        return {
            "status": "RESOLVIDO",
            "identidade": identidade,
            "metricas": [{
                "nome_metrica": "crossref.is_referenced_by_count",
                "valor": mensagem.get("is-referenced-by-count"),
                "unidade": "citacoes",
                "periodo_inicio": "",
                "periodo_fim": "",
                "categoria": "",
            }],
        }


class GoogleScholarProvider(ProvedorMetricas):
    """Consulta resultados por título e extrai a contagem exibida pelo Scholar."""

    nome = "google_scholar"
    endpoint_versao = "html-search/v1"
    aceita_sem_doi = True
    base_url = "https://scholar.google.com/scholar"

    def __init__(
        self,
        session=None,
        sleep=time.sleep,
        clock=time.monotonic,
        random_uniform=random.uniform,
        intervalo_minimo=2.5,
        jitter=1.0,
        user_agent=None,
    ):
        super().__init__(session=session, sleep=sleep)
        self.clock = clock
        self.random_uniform = random_uniform
        self.intervalo_minimo = intervalo_minimo
        self.jitter = jitter
        self.user_agent = user_agent or os.getenv(
            "GOOGLE_SCHOLAR_USER_AGENT",
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/132.0.0.0 Safari/537.36",
        )
        self.ultima_consulta = None

    def chave_consulta(self, publicacao, doi):
        chave = "|".join((
            normalizar(publicacao.get("titulo")),
            str(publicacao.get("ano") or ""),
            normalizar_doi(doi),
            normalizar("|".join(_autores_locais(publicacao))),
            normalizar(_veiculo_local(publicacao)),
        ))
        return "titulo", chave

    def resolver_por_doi(self, publicacao, doi):
        return self._buscar(publicacao)

    def buscar_candidatos(self, publicacao):
        return self._buscar(publicacao)

    def validar_identidade(self, publicacao, identidade):
        if normalizar(publicacao.get("titulo")) != normalizar(identidade.get("title")):
            return False, "título incompatível"
        ano_local = str(publicacao.get("ano") or "")
        ano_externo = str(identidade.get("year") or "")
        if ano_local and ano_externo and ano_local != ano_externo:
            return False, "ano incompatível"
        autores_locais = _autores_locais(publicacao)
        autores_externos = identidade.get("authors") or []
        if not _autores_compativeis(autores_locais, autores_externos):
            return False, "autores incompatíveis"
        tem_autor_compativel = bool(autores_locais and autores_externos and _autores_compativeis(autores_locais, autores_externos))
        tem_veiculo_compativel = bool(
            normalizar(_veiculo_local(publicacao))
            and normalizar(_veiculo_local(publicacao)) == normalizar(identidade.get("venue"))
        )
        if not (tem_autor_compativel or tem_veiculo_compativel):
            return False, "evidência adicional de autor ou veículo ausente"
        return True, ""

    def _buscar(self, publicacao):
        titulo = str(publicacao.get("titulo") or "").strip()
        if not titulo:
            return {"status": "NAO_ENCONTRADO", "evidencias": {"motivo": "título ausente"}}
        titulo_consulta = titulo.replace('"', " ")
        self._aguardar_intervalo()
        self.ultima_consulta = self.clock()
        try:
            if hasattr(self.session, "cookies"):
                self.session.cookies.clear()
            resposta = self.session.get(
                self.base_url,
                params={"q": f'intitle:"{titulo_consulta}"', "hl": "en", "num": 10},
                headers={"User-Agent": self.user_agent},
                timeout=(5, 30),
            )
        except (requests.Timeout, requests.ConnectionError):
            return {"status": "ERRO_TEMPORARIO"}
        except requests.RequestException:
            return {"status": "ERRO_PERMANENTE"}
        if resposta.status_code == 429:
            return {"status": "LIMITE_EXCEDIDO"}
        if resposta.status_code in (401, 403):
            return {"status": "ERRO_PERMANENTE"}
        if resposta.status_code >= 500:
            return {"status": "ERRO_TEMPORARIO"}
        if not resposta.ok:
            return {"status": "ERRO_PERMANENTE"}
        url_final = getattr(resposta, "url", self.base_url)
        candidatos, bloqueado = parse_google_scholar_html(resposta.text, url_final)
        if bloqueado:
            return {"status": "LIMITE_EXCEDIDO", "evidencias": {"motivo": "página de verificação recebida"}}
        url_consulta = url_final
        for candidato in candidatos:
            if not candidato.get("url_evidencia"):
                candidato["url_evidencia"] = url_consulta
        compativeis = [
            x for x in candidatos
            if x.get("citations") is not None and self.validar_identidade(publicacao, x)[0]
        ]
        evidencias = {"candidatos": candidatos[:10], "consulta": f'intitle:"{titulo_consulta}"', "url_consulta": url_consulta}
        if not compativeis:
            return {"status": "NAO_ENCONTRADO", "evidencias": evidencias}
        ids = {x["id"] for x in compativeis}
        if len(ids) != 1:
            return {"status": "AMBIGUO", "evidencias": evidencias}
        escolhido = compativeis[0]
        return {
            "status": "RESOLVIDO",
            "identidade": escolhido,
            "evidencias": evidencias,
            "metricas": [{
                "nome_metrica": "google_scholar.citations",
                "valor": escolhido["citations"],
                "unidade": "citacoes",
                "periodo_inicio": "",
                "periodo_fim": "",
                "categoria": "",
            }],
        }

    def _aguardar_intervalo(self):
        if self.ultima_consulta is None:
            return
        alvo = self.intervalo_minimo + self.random_uniform(0, self.jitter)
        restante = alvo - (self.clock() - self.ultima_consulta)
        if restante > 0:
            self.sleep(restante)


def parse_google_scholar_html(html, url_final=""):
    """Retorna somente evidências bibliográficas mínimas dos resultados."""
    texto_baixo = (html or "").lower()
    soup = BeautifulSoup(html or "", "html.parser")
    bloqueado = "/sorry/" in (url_final or "") or any(sinal in texto_baixo for sinal in (
        "unusual traffic",
        "not a robot",
        "our systems have detected",
        "/sorry/",
    )) or bool(soup.select_one("#gs_captcha_f, form[action*='/sorry/']"))
    if bloqueado:
        return [], True
    estrutura_conhecida = soup.select_one(".gs_r, #gs_res_ccl, #gs_res_ccl_mid")
    sem_resultados = "did not match any articles" in texto_baixo
    if html and not estrutura_conhecida and not sem_resultados:
        return [], True
    resultados = []
    for registro in soup.select(".gs_r"):
        conteudo = registro.select_one(".gs_ri") or registro
        cabecalho = conteudo.select_one(".gs_rt")
        if not cabecalho:
            continue
        link_titulo = cabecalho.select_one("a")
        titulo = (link_titulo or cabecalho).get_text(" ", strip=True)
        titulo = re.sub(r"^\[[^]]+\]\s*", "", titulo).strip()
        metadados = conteudo.select_one(".gs_a")
        texto_metadados = metadados.get_text(" ", strip=True) if metadados else ""
        partes = [x.strip() for x in texto_metadados.split(" - ")]
        autores = [x.strip() for x in (partes[0] if partes else "").split(",") if x.strip()]
        rodape = conteudo.select_one(".gs_fl")
        citacoes = 0 if rodape else None
        identificador = registro.get("data-cid", "")
        url_evidencia = ""
        for link in rodape.select("a") if rodape else []:
            texto_link = link.get_text(" ", strip=True)
            encontrado = re.search(r"Cited by\s+([\d.,\s]+)", texto_link, re.IGNORECASE)
            if encontrado:
                citacoes = int(re.sub(r"\D", "", encontrado.group(1)) or 0)
                parametros = parse_qs(urlparse(link.get("href", "")).query)
                identificador = (parametros.get("cites") or [identificador])[0]
                url_evidencia = urljoin("https://scholar.google.com", link.get("href", ""))
                break
        url_resultado = urljoin("https://scholar.google.com", link_titulo.get("href", "")) if link_titulo else ""
        if not identificador:
            base = "|".join((normalizar(titulo), texto_metadados, url_resultado))
            identificador = hashlib.sha256(base.encode("utf-8")).hexdigest()[:20]
        resultados.append({
            "id": identificador,
            "doi": "",
            "title": titulo,
            "year": _ano(texto_metadados),
            "type": "",
            "issn": [],
            "authors": autores,
            "venue": re.sub(r"\b(?:18|19|20)\d{2}\b", "", partes[1]).strip(" ,") if len(partes) > 1 else "",
            "citations": citacoes,
            "url_publicacao": url_resultado,
            "url_evidencia": url_evidencia,
        })
    return resultados, False


class OpenAlexProvider(ProvedorMetricas):
    nome = "openalex"
    endpoint_versao = "works/v1"
    aceita_sem_doi = True

    def chave_consulta(self, publicacao, doi):
        if doi_valido(doi):
            return "doi", doi
        chave = "|".join((
            normalizar(publicacao.get("titulo")),
            str(publicacao.get("ano") or ""),
            normalizar("|".join(_autores_locais(publicacao))),
            normalizar(_veiculo_local(publicacao)),
        ))
        return "bibliografica", chave

    def resolver_por_doi(self, publicacao, doi):
        dados, status = self._obter({"filter": "doi:https://doi.org/" + doi})
        if status != "RESOLVIDO":
            return {"status": status}
        obras = [
            x for x in dados.get("results", [])
            if normalizar_doi(x.get("doi")) == doi
        ]
        candidatos = [self._identidade(x) for x in obras]
        if not obras:
            return {"status": "NAO_ENCONTRADO", "evidencias": {"candidatos": []}}
        if len({x["id"] for x in candidatos}) != 1:
            return {"status": "AMBIGUO", "evidencias": {"candidatos": candidatos[:10]}}
        return self._resultado(obras[0])

    def buscar_candidatos(self, publicacao):
        params = {"search": publicacao.get("titulo", ""), "per-page": 10}
        if publicacao.get("ano"):
            params["filter"] = "publication_year:" + str(publicacao["ano"])
        dados, status = self._obter(params)
        if status != "RESOLVIDO":
            return {"status": status}
        candidatos = [self._identidade(x) for x in dados.get("results", [])]
        compativeis = [x for x in candidatos if _identidade_bibliografica_compativel(publicacao, x)]
        if not compativeis:
            return {"status": "NAO_ENCONTRADO", "evidencias": {"candidatos": candidatos[:10]}}
        if len({x["id"] for x in compativeis}) != 1:
            return {"status": "AMBIGUO", "evidencias": {"candidatos": compativeis[:10]}}
        obra = next(x for x in dados["results"] if x.get("id", "") == compativeis[0]["id"])
        return self._resultado(obra)

    def _obter(self, params):
        params = dict(params)
        if os.getenv("OPENALEX_API_KEY"):
            params["api_key"] = os.environ["OPENALEX_API_KEY"]
        return self._get_json("https://api.openalex.org/works", params=params)

    def _resultado(self, obra):
        identidade = self._identidade(obra)
        metricas = [{
            "nome_metrica": "openalex.cited_by_count",
            "valor": obra.get("cited_by_count"),
            "unidade": "citacoes",
            "periodo_inicio": "",
            "periodo_fim": "",
            "categoria": "",
        }]
        for contagem in obra.get("counts_by_year") or []:
            ano = str(contagem.get("year", ""))
            metricas.append({
                "nome_metrica": "openalex.citations_in_year",
                "valor": contagem.get("cited_by_count"),
                "unidade": "citacoes",
                "periodo_inicio": ano,
                "periodo_fim": ano,
                "categoria": "",
            })
        return {"status": "RESOLVIDO", "identidade": identidade, "metricas": metricas}

    @staticmethod
    def _identidade(obra):
        fonte = (obra.get("primary_location") or {}).get("source") or {}
        autores = [
            x.get("author", {}).get("display_name", "")
            for x in obra.get("authorships") or []
            if x.get("author", {}).get("display_name")
        ]
        return {
            "id": obra.get("id", ""),
            "doi": normalizar_doi(obra.get("doi")),
            "title": obra.get("title", ""),
            "year": str(obra.get("publication_year", "")),
            "type": obra.get("type", ""),
            "issn": fonte.get("issn", []),
            "authors": autores,
            "venue": fonte.get("display_name", ""),
        }


def _identidade_bibliografica_compativel(publicacao, identidade):
    doi_local = normalizar_doi(publicacao.get("doi"))
    if doi_valido(doi_local) and doi_local != normalizar_doi(identidade.get("doi")):
        return False
    if normalizar(publicacao.get("titulo")) != normalizar(identidade.get("title")):
        return False
    ano_local = str(publicacao.get("ano") or "")
    ano_externo = str(identidade.get("year") or "")
    if ano_local and ano_externo and ano_local != ano_externo:
        return False
    autores_locais = _autores_locais(publicacao)
    autores_externos = identidade.get("authors") or []
    if not _autores_compativeis(autores_locais, autores_externos):
        return False
    if not doi_valido(doi_local):
        tem_autor_compativel = bool(autores_locais and autores_externos and _autores_compativeis(autores_locais, autores_externos))
        tem_veiculo_compativel = bool(
            normalizar(_veiculo_local(publicacao))
            and normalizar(_veiculo_local(publicacao)) == normalizar(identidade.get("venue"))
        )
        return tem_autor_compativel or tem_veiculo_compativel
    return True
