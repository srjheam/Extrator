import importlib.util
import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'PPGI'))
sys.path.insert(0, str(ROOT))

from PontuacaoPPGI.NotaInfo import NotaInfo
from PontuacaoPPGI.utils import preflight_pontuacao


def _nota_info(tmp_path):
    caminho = tmp_path / 'pontuacao.json'
    caminho.write_text(json.dumps({
        'prod-min': {'intervalo': [2021, 2024], 'prod-min-qtd': 1, 'valid-tags': [], 'prod-min-tag': 'Mínimo'},
        'nota': {'intervalo': [2023, 2024], 'nota-min': 1, 'nota-multiplo': .25, 'valores': []},
    }), encoding='utf-8')
    return NotaInfo(caminho)


def _linha(**mudancas):
    linha = {
        'Docente': 'Docente', 'tipo': 'Conferência', 'ano': '2023', 'titulo': 'Paper about reliable systems',
        'venue': 'Evento', 'revista': '', 'issn': '', 'doi': '', 'isbn': '', 'autores': '[]',
        'curriculo_id': '1', 'arquivo_xml': '1.xml', 'sequencia': '1', 'estrato': 'A1',
        'qualis_requer_revisao': 'false',
    }
    linha.update(mudancas)
    return linha


def _preflight(tmp_path, linhas, overrides='ocorrencia_a,ocorrencia_b,acao\n'):
    ocorrencias = tmp_path / 'ocorrencias.csv'
    pd.DataFrame(linhas).to_csv(ocorrencias, index=False)
    caminho_overrides = tmp_path / 'overrides.csv'
    caminho_overrides.write_text(overrides, encoding='utf-8')
    return preflight_pontuacao(ocorrencias, caminho_overrides, _nota_info(tmp_path), tmp_path, '2024')


def test_preflight_without_reviews_allows_scoring(tmp_path):
    resultado = _preflight(tmp_path, [_linha()])
    assert resultado.pode_pontuar
    assert resultado.quantidade_deduplicacao == 0
    assert resultado.quantidade_qualis == 0


def test_qualis_review_in_interval_blocks(tmp_path):
    resultado = _preflight(tmp_path, [_linha(qualis_requer_revisao='true')])
    assert not resultado.pode_pontuar
    assert resultado.quantidade_qualis == 1


def test_qualis_review_outside_interval_does_not_block(tmp_path):
    resultado = _preflight(tmp_path, [_linha(ano='2022', qualis_requer_revisao='true')])
    assert resultado.pode_pontuar


def test_deduplication_review_in_interval_blocks(tmp_path):
    resultado = _preflight(tmp_path, [_linha(), _linha(titulo='Paper about reliability systems', sequencia='2')])
    assert not resultado.pode_pontuar
    assert resultado.quantidade_deduplicacao == 1


def test_existing_deduplication_override_clears_blocker(tmp_path):
    primeiro, segundo = _linha(), _linha(titulo='Paper about reliability systems', sequencia='2')
    bloqueado = _preflight(tmp_path, [primeiro, segundo])
    revisao = bloqueado.revisoes_deduplicacao[0]
    overrides = f'ocorrencia_a,ocorrencia_b,acao\n{revisao.ocorrencia_a},{revisao.ocorrencia_b},NAO_AGRUPAR\n'
    resultado = _preflight(tmp_path, [primeiro, segundo], overrides)
    assert resultado.pode_pontuar


def test_multiple_blocker_types_are_reported(tmp_path):
    resultado = _preflight(tmp_path, [
        _linha(qualis_requer_revisao='true'),
        _linha(titulo='Paper about reliability systems', sequencia='2'),
    ])
    assert not resultado.pode_pontuar
    assert resultado.quantidade_deduplicacao == 1
    assert resultado.quantidade_qualis == 1


def _part2_module():
    spec = importlib.util.spec_from_file_location('main_part2', ROOT / 'PPGI' / 'main-part2.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _config(tmp_path, linhas):
    saida = tmp_path / 'saida'
    ocorrencias = tmp_path / 'ocorrencias.csv'
    pd.DataFrame(linhas).to_csv(ocorrencias, index=False)
    overrides = tmp_path / 'overrides.csv'
    overrides.write_text('ocorrencia_a,ocorrencia_b,acao\n', encoding='utf-8')
    nota = tmp_path / 'pontuacao.json'
    nota.write_text(json.dumps({
        'prod-min': {'intervalo': [2021, 2024], 'prod-min-qtd': 1, 'valid-tags': ['Conferência A1'], 'prod-min-tag': 'Mínimo'},
        'nota': {'intervalo': [2023, 2024], 'nota-min': 1, 'nota-multiplo': .25, 'valores': [{'valor': 1, 'tags': ['Conferência A1']}]},
    }), encoding='utf-8')
    config = tmp_path / 'config.json'
    config.write_text(json.dumps({
        'ano_inicio_conferencia': 2023, 'ano_fim_conferencia': 2024,
        'ano_inicio_periodico': 2021, 'ano_fim_periodico': 2024,
        'arquivo_lista_docentes': '', 'diretorio_curriculos': '', 'diretorio_saida': str(saida),
        'arquivo_nota_docente': 'docente.csv', 'arquivo_nota_geral': 'grupo.csv',
        'arquivo_qualis_journal': '', 'arquivo_qualis_conference': '',
        'arquivo_publicacoes_ocorrencias': str(ocorrencias),
        'arquivo_overrides_deduplicacao': str(overrides), 'config_pontuacao': str(nota),
    }), encoding='utf-8')
    return config, saida


def test_blocked_run_keeps_reports_and_writes_manifest(tmp_path):
    config, saida = _config(tmp_path, [_linha(qualis_requer_revisao='true')])
    saida.mkdir()
    (saida / '2024_docente.csv').write_text('old-docente', encoding='utf-8')
    (saida / '2024_grupo.csv').write_text('old-grupo', encoding='utf-8')
    assert _part2_module().main([str(config)]) == 2
    assert (saida / '2024_docente.csv').read_text(encoding='utf-8') == 'old-docente'
    assert (saida / '2024_grupo.csv').read_text(encoding='utf-8') == 'old-grupo'
    assert json.loads((saida / '2024_execucao.json').read_text())['status'] == 'BLOQUEADO_REVISAO'


def test_success_publishes_both_reports_and_manifest(tmp_path):
    config, saida = _config(tmp_path, [_linha()])
    assert _part2_module().main([str(config)]) == 0
    assert (saida / '2024_docente.csv').is_file()
    assert (saida / '2024_grupo.csv').is_file()
    manifest = json.loads((saida / '2024_execucao.json').read_text())
    assert manifest['status'] == 'SUCESSO'
    assert len(manifest['relatorios_publicados']) == 2


def test_failure_removes_temporary_files_and_never_publishes_success(tmp_path, monkeypatch):
    config, saida = _config(tmp_path, [_linha()])
    modulo = _part2_module()
    monkeypatch.setattr(modulo.PontuacaoTotal, 'calcula_nota_geral', lambda *args: (_ for _ in ()).throw(RuntimeError('falha forçada')))
    assert modulo.main([str(config)]) == 1
    manifest = json.loads((saida / '2024_execucao.json').read_text())
    assert manifest['status'] == 'ERRO'
    assert not list(saida.glob('.part2-*.tmp'))
    assert not (saida / '2024_docente.csv').exists()
    assert not (saida / '2024_grupo.csv').exists()
