"""Persistência SQLite de cache, snapshots e auditoria."""
from __future__ import annotations
import hashlib, json, sqlite3
from datetime import datetime, timezone

class RepositorioMetricasSQLite:
    def __init__(self, caminho):
        self.con = sqlite3.connect(caminho)
        self.con.row_factory = sqlite3.Row
        self._criar_tabelas()
    def _criar_tabelas(self):
        self.con.executescript('''
        create table if not exists execucao (snapshot_id text primary key, iniciada_em text, finalizada_em text, politica_versao text, modo text);
        create table if not exists consulta (provedor text, tipo_consulta text, chave_hash text, resposta_json text, consultada_em text, primary key(provedor,tipo_consulta,chave_hash));
        create table if not exists identidade (snapshot_id text, publicacao_canonica_id text, provedor text, dados_json text, primary key(snapshot_id,publicacao_canonica_id,provedor));
        create table if not exists metrica_snapshot (snapshot_id text, publicacao_canonica_id text, provedor text, nome_metrica text, categoria text, dados_json text, primary key(snapshot_id,publicacao_canonica_id,provedor,nome_metrica,categoria));
        create table if not exists revisao (snapshot_id text, publicacao_canonica_id text, provedor text, dados_json text, primary key(snapshot_id,publicacao_canonica_id,provedor));
        create table if not exists override_metricas (publicacao_canonica_id text, provedor text, identificador_externo text, justificativa text, primary key(publicacao_canonica_id,provedor));''')
        self.con.commit()
    def criar_snapshot(self, politica, modo):
        valor = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        self.con.execute("insert into execucao values(?,?,?,?,?)", (valor, datetime.now(timezone.utc).isoformat(), None, politica, modo)); self.con.commit(); return valor
    def finalizar_snapshot(self, snapshot): self.con.execute("update execucao set finalizada_em=? where snapshot_id=?", (datetime.now(timezone.utc).isoformat(), snapshot)); self.con.commit()
    def existe_snapshot(self, snapshot): return bool(self.con.execute("select 1 from execucao where snapshot_id=?", (snapshot,)).fetchone())
    @staticmethod
    def _hash(chave): return hashlib.sha256(chave.encode()).hexdigest()
    def obter_consulta(self, provedor, tipo, chave):
        linha = self.con.execute("select resposta_json from consulta where provedor=? and tipo_consulta=? and chave_hash=?", (provedor,tipo,self._hash(chave))).fetchone()
        return json.loads(linha[0]) if linha else None
    def salvar_consulta(self, provedor, tipo, chave, resposta):
        self.con.execute("insert or replace into consulta values(?,?,?,?,?)", (provedor,tipo,self._hash(chave),json.dumps(resposta,ensure_ascii=False),datetime.now(timezone.utc).isoformat())); self.con.commit()
    def salvar_identidade(self, item): self.con.execute("insert or replace into identidade values(?,?,?,?)", (item['snapshot_id'],item['publicacao_canonica_id'],item['provedor'],json.dumps(item,ensure_ascii=False))); self.con.commit()
    def salvar_metricas(self, itens):
        for i in itens: self.con.execute("insert or replace into metrica_snapshot values(?,?,?,?,?,?)", (i['snapshot_id'],i['publicacao_canonica_id'],i['provedor'],i['nome_metrica'],i.get('categoria',''),json.dumps(i,ensure_ascii=False)))
        self.con.commit()
    def salvar_revisao(self, item): self.con.execute("insert or replace into revisao values(?,?,?,?)", (item.get('snapshot_id',''),item['publicacao_canonica_id'],item['provedor'],json.dumps(item,ensure_ascii=False))); self.con.commit()
    def itens(self, tabela, snapshot):
        coluna = 'dados_json'; return [json.loads(x[0]) for x in self.con.execute(f"select {coluna} from {tabela} where snapshot_id=?", (snapshot,))]
    def consultas(self): return [dict(x) for x in self.con.execute("select provedor,tipo_consulta,chave_hash,consultada_em from consulta")]
    def close(self): self.con.close()
