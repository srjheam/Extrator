import pytest

from Metricas.core import enriquecer_publicacoes
from Metricas.repository import RepositorioMetricasSQLite


class Provider:
    nome = "teste"
    endpoint_versao = "v1"

    def __init__(self):
        self.chamadas = 0

    def resolver_por_doi(self, publicacao, doi):
        self.chamadas += 1
        return {"status": "RESOLVIDO", "identidade": {"id": "x", "doi": doi, "title": publicacao["titulo"], "year": str(publicacao["ano"]), "type": "journal-article", "issn": []}, "metricas": [{"nome_metrica": "teste.citacoes", "valor": 2, "unidade": "citacoes", "periodo_inicio": "", "periodo_fim": "", "categoria": ""}]}


class ProviderComStatus(Provider):
    def __init__(self, nome, status, valor=None):
        super().__init__()
        self.nome = nome
        self.status = status
        self.valor = valor

    def resolver_por_doi(self, publicacao, doi):
        self.chamadas += 1
        if self.status != "RESOLVIDO":
            return {"status": self.status}
        return {"status": "RESOLVIDO", "identidade": {"id": self.nome, "doi": doi, "title": publicacao["titulo"], "year": str(publicacao["ano"]), "type": "journal-article", "issn": []}, "metricas": [{"nome_metrica": self.nome + ".citacoes", "valor": self.valor, "unidade": "citacoes", "periodo_inicio": "", "periodo_fim": "", "categoria": ""}]}


def pub(doi="10.1000/teste"):
    return {"publicacao_canonica_id": "c1", "titulo": "Um teste", "ano": "2024", "tipo": "Periódico", "doi": doi, "issn": ""}


def test_doi_usa_cache_e_metricas_separadas(tmp_path):
    repo = RepositorioMetricasSQLite(tmp_path / "m.sqlite")
    provider = Provider()
    primeiro = enriquecer_publicacoes([pub()], [provider], repo)
    segundo = enriquecer_publicacoes([pub()], [provider], repo)
    assert provider.chamadas == 1
    assert primeiro.identidades[0]["status"] == "RESOLVIDO"
    assert segundo.metricas[0]["nome_metrica"] == "teste.citacoes"
    assert repo.consultas(primeiro.snapshot_id)[0]["cache_hit"] == 0
    assert repo.consultas(segundo.snapshot_id)[0]["cache_hit"] == 1


def test_offline_sem_cache_nao_chama_rede(tmp_path):
    repo = RepositorioMetricasSQLite(tmp_path / "m.sqlite")
    provider = Provider()
    resultado = enriquecer_publicacoes([pub()], [provider], repo, modo="offline")
    assert provider.chamadas == 0
    assert resultado.identidades[0]["status"] == "CACHE_AUSENTE"


def test_sem_doi_em_provedor_sem_busca_vai_para_revisao(tmp_path):
    repo = RepositorioMetricasSQLite(tmp_path / "m.sqlite")
    provider = Provider()
    resultado = enriquecer_publicacoes([pub("")], [provider], repo)
    assert resultado.identidades[0]["status"] == "AMBIGUO"
    assert resultado.revisoes[0]["motivo"] == "provedor requer DOI"


def test_scholar_resolvido_com_zero_nao_chama_fallback(tmp_path):
    repo = RepositorioMetricasSQLite(tmp_path / "m.sqlite")
    scholar = ProviderComStatus("google_scholar", "RESOLVIDO", 0)
    openalex = ProviderComStatus("openalex", "RESOLVIDO", 7)
    resultado = enriquecer_publicacoes([pub()], [scholar, openalex], repo, estrategia_provedores="fallback")
    assert scholar.chamadas == 1
    assert openalex.chamadas == 0
    assert resultado.metricas[0]["valor"] == 0
    assert resultado.metricas[0]["papel_provedor"] == "PRIMARIO"


def test_openalex_e_chamado_quando_scholar_nao_resolve(tmp_path):
    repo = RepositorioMetricasSQLite(tmp_path / "m.sqlite")
    scholar = ProviderComStatus("google_scholar", "NAO_ENCONTRADO")
    openalex = ProviderComStatus("openalex", "RESOLVIDO", 7)
    resultado = enriquecer_publicacoes([pub()], [scholar, openalex], repo, estrategia_provedores="fallback")
    assert openalex.chamadas == 1
    assert resultado.metricas[0]["provedor"] == "openalex"
    assert resultado.metricas[0]["papel_provedor"] == "FALLBACK"
    assert resultado.metricas[0]["fallback_acionado_por"] == "google_scholar:NAO_ENCONTRADO"


def test_openalex_e_chamado_quando_scholar_nao_fornece_contagem(tmp_path):
    repo = RepositorioMetricasSQLite(tmp_path / "m.sqlite")
    scholar = ProviderComStatus("google_scholar", "RESOLVIDO", None)
    openalex = ProviderComStatus("openalex", "RESOLVIDO", 7)
    resultado = enriquecer_publicacoes([pub()], [scholar, openalex], repo, estrategia_provedores="fallback")
    assert openalex.chamadas == 1
    assert len(resultado.metricas) == 1
    assert resultado.metricas[0]["fallback_acionado_por"] == "google_scholar:SEM_METRICA"


def test_metricas_anuais_nao_se_sobrescrevem(tmp_path):
    repo = RepositorioMetricasSQLite(tmp_path / "m.sqlite")
    snapshot = repo.criar_snapshot("1", "teste")
    base = {"snapshot_id": snapshot, "publicacao_canonica_id": "c1", "provedor": "openalex", "nome_metrica": "openalex.citations_in_year", "categoria": ""}
    repo.salvar_metricas([{**base, "periodo_inicio": "2023", "periodo_fim": "2023"}, {**base, "periodo_inicio": "2024", "periodo_fim": "2024"}])
    assert len(repo.itens("metrica_snapshot", snapshot)) == 2


def test_erro_temporario_nao_fica_no_cache(tmp_path):
    repo = RepositorioMetricasSQLite(tmp_path / "m.sqlite")
    provider = ProviderComStatus("google_scholar", "ERRO_TEMPORARIO")
    enriquecer_publicacoes([pub()], [provider], repo, estrategia_provedores="fallback")
    provider.status = "RESOLVIDO"
    provider.valor = 4
    resultado = enriquecer_publicacoes([pub()], [provider], repo, estrategia_provedores="fallback")
    assert provider.chamadas == 2
    assert resultado.metricas[0]["valor"] == 4


def test_credencial_ausente_nao_fica_no_cache(tmp_path):
    repo = RepositorioMetricasSQLite(tmp_path / "m.sqlite")
    provider = ProviderComStatus("openalex", "CREDENCIAL_AUSENTE")
    enriquecer_publicacoes([pub()], [provider], repo, estrategia_provedores="fallback")
    provider.status = "RESOLVIDO"
    provider.valor = 4
    resultado = enriquecer_publicacoes([pub()], [provider], repo, estrategia_provedores="fallback")
    assert provider.chamadas == 2
    assert resultado.metricas[0]["valor"] == 4


def test_provedor_auxiliar_nao_interrompe_cadeia_de_citacoes(tmp_path):
    repo = RepositorioMetricasSQLite(tmp_path / "m.sqlite")
    crossref = ProviderComStatus("crossref", "RESOLVIDO", 2)
    scholar = ProviderComStatus("google_scholar", "RESOLVIDO", 0)
    openalex = ProviderComStatus("openalex", "RESOLVIDO", 7)
    resultado = enriquecer_publicacoes(
        [pub()],
        [scholar, openalex],
        repo,
        estrategia_provedores="fallback",
        provedores_independentes=[crossref],
    )
    assert crossref.chamadas == 1
    assert scholar.chamadas == 1
    assert openalex.chamadas == 0
    assert [x["provedor"] for x in resultado.metricas] == ["crossref", "google_scholar"]


def test_snapshot_existente_nao_pode_ser_sobrescrito(tmp_path):
    repo = RepositorioMetricasSQLite(tmp_path / "m.sqlite")
    snapshot = repo.criar_snapshot("1", "teste")
    with pytest.raises(ValueError, match="imutáveis"):
        enriquecer_publicacoes([pub()], [Provider()], repo, snapshot_id=snapshot)
