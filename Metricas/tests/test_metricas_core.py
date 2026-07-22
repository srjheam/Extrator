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


def test_offline_sem_cache_nao_chama_rede(tmp_path):
    repo = RepositorioMetricasSQLite(tmp_path / "m.sqlite")
    provider = Provider()
    resultado = enriquecer_publicacoes([pub()], [provider], repo, modo="offline")
    assert provider.chamadas == 0
    assert resultado.identidades[0]["status"] == "CACHE_AUSENTE"


def test_sem_doi_vai_para_revisao(tmp_path):
    repo = RepositorioMetricasSQLite(tmp_path / "m.sqlite")
    provider = Provider()
    resultado = enriquecer_publicacoes([pub("")], [provider], repo)
    assert resultado.identidades[0]["status"] == "AMBIGUO"
    assert resultado.revisoes[0]["motivo"].startswith("publicação sem DOI")
