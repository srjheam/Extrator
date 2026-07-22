from Metricas.providers import OpenAlexProvider
from Metricas.core import enriquecer_publicacoes
from Metricas.repository import RepositorioMetricasSQLite


class Response:
    status_code = 200
    headers = {}

    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self.payload


class Session:
    def __init__(self, payload):
        self.payload = payload
        self.calls = []

    def get(self, url, **kwargs):
        self.calls.append((url, kwargs))
        return Response(self.payload)


def test_openalex_extrai_contagem_total_e_serie_anual():
    obra = {
        "id": "https://openalex.org/W1",
        "doi": "https://doi.org/10.1000/teste",
        "title": "Um teste",
        "publication_year": 2024,
        "type": "article",
        "cited_by_count": 9,
        "counts_by_year": [
            {"year": 2024, "cited_by_count": 3},
            {"year": 2025, "cited_by_count": 6},
        ],
        "primary_location": {"source": {"display_name": "Journal of Tests", "issn": ["1234-5678"]}},
        "authorships": [{"author": {"display_name": "Alice Silva"}}],
    }
    provider = OpenAlexProvider(session=Session({"results": [obra]}), sleep=lambda _: None)
    publicacao = {"titulo": "Um teste", "ano": "2024", "doi": "10.1000/teste", "autores": '["Alice Silva"]'}
    resposta = provider.resolver_por_doi(publicacao, "10.1000/teste")
    assert resposta["status"] == "RESOLVIDO"
    assert [x["valor"] for x in resposta["metricas"]] == [9, 3, 6]
    assert resposta["metricas"][2]["periodo_inicio"] == "2025"


def test_resposta_de_doi_e_reutilizada_com_validacao_independente(tmp_path):
    obra = {
        "id": "https://openalex.org/W1", "doi": "https://doi.org/10.1000/teste",
        "title": "Um teste", "publication_year": 2024, "type": "article",
        "cited_by_count": 9, "counts_by_year": [], "primary_location": None,
        "authorships": [{"author": {"display_name": "Alice Silva"}}],
    }
    session = Session({"results": [obra]})
    provider = OpenAlexProvider(session=session, sleep=lambda _: None)
    publicacoes = [
        {"publicacao_canonica_id": "c1", "titulo": "Um teste", "ano": "2024", "tipo": "Periódico", "doi": "10.1000/teste", "issn": "", "autores": '["Alice Silva"]'},
        {"publicacao_canonica_id": "c2", "titulo": "Um teste", "ano": "2024", "tipo": "Periódico", "doi": "10.1000/teste", "issn": "", "autores": '["Pessoa Diferente"]'},
    ]
    resultado = enriquecer_publicacoes(publicacoes, [provider], RepositorioMetricasSQLite(tmp_path / "m.sqlite"))
    assert len(session.calls) == 1
    assert [x["status"] for x in resultado.identidades] == ["RESOLVIDO", "DOI_INCOMPATIVEL"]
