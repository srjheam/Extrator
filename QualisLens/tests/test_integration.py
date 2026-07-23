"""Corpus rotulado manualmente. Não use generate_outputs.py como oráculo."""

import csv
from pathlib import Path

import pandas as pd
import pytest

from QualisLens.qualislens.constants import STATUS_AUTO_FUZZY, STATUS_EXATO, STATUS_REVISAO_MANUAL
from QualisLens.qualislens.matcher import match
from QualisLens.qualislens.main import _processar_linha
from Classificador.QualisConferencia import QualisConferencia


CORPUS = Path(__file__).parent / "data" / "gold_corpus.csv"


def _casos():
    with CORPUS.open(encoding="utf-8") as arquivo:
        return list(csv.DictReader(arquivo))


@pytest.mark.parametrize("caso", _casos(), ids=lambda caso: caso["id"])
def test_corpus_gold(caso, db):
    resultado = match(caso["venue"], int(caso["ano"]), caso["sigla"] or None, db)
    candidatos = resultado["_candidatos_lista"]
    siglas = {str(c["sigla"]).upper() for c in candidatos}
    esperado = caso["esperado"]

    if caso["decisao"] == "exato":
        assert resultado["qualis_status"] == STATUS_EXATO
        assert resultado["qualis_estrato"] == esperado
    elif caso["decisao"] == "topo_ou_revisao":
        # Caso difícil: candidato certo deve estar disponível; só aceite auto
        # quando ele for exatamente o candidato rotulado.
        assert caso["sigla_esperada"] in siglas
        if resultado["qualis_status"] in (STATUS_EXATO, STATUS_AUTO_FUZZY):
            assert resultado["qualis_sigla"] == caso["sigla_esperada"]
            assert resultado["qualis_estrato"] == esperado
        else:
            assert resultado["qualis_status"] == STATUS_REVISAO_MANUAL
    else:
        assert resultado["qualis_status"] == STATUS_REVISAO_MANUAL
        assert resultado["qualis_estrato"] is None


def test_auto_fuzzy_has_no_contradictory_distinctive_term(db):
    resultado = match("Congresso Brasileiro de Engenharia Mecânica", 2022, None, db)
    assert resultado["qualis_status"] == STATUS_REVISAO_MANUAL
    assert "biomed" not in (resultado.get("qualis_sigla") or "").lower()


def test_default_flow_never_calls_ollama(monkeypatch, db):
    def falha(*args, **kwargs):
        raise AssertionError("HTTP/Ollama called without --modelo")

    monkeypatch.setattr("QualisLens.qualislens.llm_reviewer._chamar_ollama", falha)
    resultado = _processar_linha(pd.Series({
        "titulo_artigo": "Teste sem rede",
        "nome_conferencia": "evento desconhecido sem correspondencia",
        "ano_publicacao": "2022",
    }), db, modelos=None)
    assert resultado["qualis_status"] == STATUS_REVISAO_MANUAL


def test_legacy_api_returns_auditable_contract():
    resultado = QualisConferencia().get_match("International Conference on Software Engineering", 2023, "ICSE")
    assert {"estrato", "evento_oficial", "sigla_oficial", "quadrienio", "metodo", "score_primeiro", "margem_segundo", "candidatos", "motivo", "necessita_revisao"} <= set(resultado)
    assert resultado["estrato"] == "A1"
