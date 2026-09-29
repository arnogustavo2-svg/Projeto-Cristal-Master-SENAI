import json
import math
import sqlite3
from datetime import datetime
from pathlib import Path

PASTA_DO_PROJETO = Path(__file__).resolve().parent
CAMINHO_DO_BANCO = PASTA_DO_PROJETO / "almoxarifado.db"


def conectar():
    conexao = sqlite3.connect(CAMINHO_DO_BANCO)
    conexao.row_factory = sqlite3.Row
    conexao.execute("PRAGMA foreign_keys = ON")
    return conexao


def agora():
    return datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")


def inicializar_banco():
    conexao = conectar()
    conexao.executescript(
        """
        CREATE TABLE IF NOT EXISTS materiais (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            codigo TEXT NOT NULL UNIQUE,
            descricao TEXT NOT NULL,
            unidade TEXT NOT NULL,
            ativo INTEGER NOT NULL DEFAULT 1,
            criado_em TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS operadores (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            matricula TEXT NOT NULL UNIQUE,
            nome TEXT NOT NULL,
            ativo INTEGER NOT NULL DEFAULT 1,
            criado_em TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS posicoes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            codigo TEXT NOT NULL UNIQUE,
            descricao TEXT,
            criado_em TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS lotes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            material_id INTEGER NOT NULL,
            codigo TEXT NOT NULL,
            validade TEXT,
            criado_em TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(material_id, codigo),
            FOREIGN KEY(material_id) REFERENCES materiais(id)
        );
        CREATE TABLE IF NOT EXISTS pallets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            lote_id INTEGER NOT NULL,
            codigo TEXT NOT NULL UNIQUE,
            posicao_id INTEGER,
            bloqueado INTEGER NOT NULL DEFAULT 0,
            criado_em TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(lote_id) REFERENCES lotes(id),
            FOREIGN KEY(posicao_id) REFERENCES posicoes(id)
        );
        CREATE TABLE IF NOT EXISTS ordens_producao (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            codigo TEXT NOT NULL UNIQUE,
            produto TEXT NOT NULL,
            prioridade INTEGER NOT NULL DEFAULT 3,
            prazo TEXT,
            status TEXT NOT NULL DEFAULT 'aberta',
            criado_em TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            finalizado_em TEXT
        );
        CREATE TABLE IF NOT EXISTS itens_ordem_producao (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            op_id INTEGER NOT NULL,
            material_id INTEGER NOT NULL,
            quantidade REAL NOT NULL,
            criado_em TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(op_id) REFERENCES ordens_producao(id),
            FOREIGN KEY(material_id) REFERENCES materiais(id)
        );
        CREATE TABLE IF NOT EXISTS tarefas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            op_id INTEGER NOT NULL,
            item_id INTEGER NOT NULL,
            material_id INTEGER NOT NULL,
            operador_id INTEGER,
            quantidade REAL NOT NULL,
            prioridade INTEGER NOT NULL DEFAULT 3,
            status TEXT NOT NULL DEFAULT 'pendente',
            lote_recomendado_id INTEGER,
            pallet_id INTEGER,
            posicao_id INTEGER,
            quantidade_retirada REAL,
            observacao TEXT,
            criado_em TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            iniciado_em TEXT,
            concluido_em TEXT,
            FOREIGN KEY(op_id) REFERENCES ordens_producao(id),
            FOREIGN KEY(item_id) REFERENCES itens_ordem_producao(id),
            FOREIGN KEY(material_id) REFERENCES materiais(id),
            FOREIGN KEY(operador_id) REFERENCES operadores(id)
        );
        CREATE TABLE IF NOT EXISTS movimentacoes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tipo TEXT NOT NULL,
            material_id INTEGER NOT NULL,
            lote_id INTEGER,
            pallet_id INTEGER,
            pallet_op_id INTEGER,
            posicao_origem_id INTEGER,
            posicao_destino_id INTEGER,
            quantidade REAL NOT NULL,
            operador_id INTEGER,
            tarefa_id INTEGER,
            op_id INTEGER,
            observacao TEXT,
            criado_em TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(material_id) REFERENCES materiais(id)
        );
        CREATE TABLE IF NOT EXISTS auditoria (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            entidade TEXT NOT NULL,
            entidade_id INTEGER,
            acao TEXT NOT NULL,
            detalhes TEXT,
            criado_em TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS eventos_dispositivo (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            evento_id TEXT NOT NULL UNIQUE,
            dispositivo_id TEXT NOT NULL,
            baia TEXT,
            uid_rfid TEXT,
            tipo_evento TEXT NOT NULL,
            valor TEXT,
            criado_em TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS excecoes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tarefa_id INTEGER,
            operador_id INTEGER,
            motivo TEXT NOT NULL,
            observacao TEXT,
            status TEXT NOT NULL DEFAULT 'aberta',
            decisao TEXT,
            criado_em TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            resolvido_em TEXT,
            FOREIGN KEY(tarefa_id) REFERENCES tarefas(id),
            FOREIGN KEY(operador_id) REFERENCES operadores(id)
        );
        CREATE TABLE IF NOT EXISTS configuracoes_embalagem (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            material_id INTEGER NOT NULL,
            fornecedor TEXT NOT NULL,
            peso_sacaria REAL NOT NULL CHECK(peso_sacaria > 0),
            capacidade_pallet REAL NOT NULL CHECK(capacidade_pallet > 0),
            atualizado_em TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(material_id, fornecedor),
            FOREIGN KEY(material_id) REFERENCES materiais(id)
        );
        CREATE TABLE IF NOT EXISTS demandas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            codigo TEXT NOT NULL UNIQUE,
            produto TEXT NOT NULL,
            quantidade_cargas INTEGER NOT NULL CHECK(quantidade_cargas > 0),
            observacao TEXT,
            status TEXT NOT NULL DEFAULT 'rascunho',
            op_id INTEGER UNIQUE,
            criado_em TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            confirmado_em TEXT,
            FOREIGN KEY(op_id) REFERENCES ordens_producao(id)
        );
        CREATE TABLE IF NOT EXISTS demanda_itens (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            demanda_id INTEGER NOT NULL,
            material_id INTEGER NOT NULL,
            configuracao_id INTEGER,
            codigo_material TEXT NOT NULL,
            descricao_material TEXT NOT NULL,
            localizacao TEXT NOT NULL,
            quantidade_por_carga REAL NOT NULL CHECK(quantidade_por_carga > 0),
            quantidade_total REAL NOT NULL CHECK(quantidade_total > 0),
            unidade TEXT NOT NULL,
            fornecedor TEXT NOT NULL,
            peso_sacaria REAL NOT NULL CHECK(peso_sacaria > 0),
            capacidade_pallet REAL NOT NULL CHECK(capacidade_pallet > 0),
            sacarias_fechadas INTEGER NOT NULL CHECK(sacarias_fechadas >= 0),
            quantidade_em_sacarias REAL NOT NULL CHECK(quantidade_em_sacarias >= 0),
            quantidade_em_pesagem REAL NOT NULL CHECK(quantidade_em_pesagem >= 0),
            observacao TEXT,
            FOREIGN KEY(demanda_id) REFERENCES demandas(id),
            FOREIGN KEY(material_id) REFERENCES materiais(id),
            FOREIGN KEY(configuracao_id) REFERENCES configuracoes_embalagem(id)
        );
        CREATE TABLE IF NOT EXISTS pallets_op (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            op_id INTEGER NOT NULL,
            item_id INTEGER NOT NULL,
            demanda_item_id INTEGER NOT NULL,
            numero INTEGER NOT NULL,
            sacarias INTEGER NOT NULL CHECK(sacarias >= 0),
            quantidade_pesagem REAL NOT NULL CHECK(quantidade_pesagem >= 0),
            quantidade_total REAL NOT NULL CHECK(quantidade_total > 0),
            capacidade REAL NOT NULL CHECK(capacidade > 0),
            status TEXT NOT NULL CHECK(status IN ('previsto','em_montagem','fechado','movimentado','pendente','bloqueado')),
            status_anterior TEXT,
            posicao_id INTEGER,
            criado_em TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            fechado_em TEXT,
            movimentado_em TEXT,
            UNIQUE(item_id, numero),
            FOREIGN KEY(op_id) REFERENCES ordens_producao(id),
            FOREIGN KEY(item_id) REFERENCES itens_ordem_producao(id),
            FOREIGN KEY(demanda_item_id) REFERENCES demanda_itens(id),
            FOREIGN KEY(posicao_id) REFERENCES posicoes(id)
        );
        CREATE TABLE IF NOT EXISTS ajustes_estoque (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            material_id INTEGER NOT NULL,
            lote_id INTEGER,
            lote_anterior_id INTEGER,
            pallet_id INTEGER,
            posicao_anterior_id INTEGER,
            posicao_id INTEGER,
            tipo TEXT NOT NULL,
            motivo TEXT NOT NULL,
            observacao TEXT,
            quantidade_antes REAL NOT NULL,
            quantidade_ajuste REAL NOT NULL,
            quantidade_depois REAL NOT NULL,
            responsavel TEXT NOT NULL,
            criado_em TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(material_id) REFERENCES materiais(id),
            FOREIGN KEY(lote_id) REFERENCES lotes(id),
            FOREIGN KEY(pallet_id) REFERENCES pallets(id),
            FOREIGN KEY(posicao_anterior_id) REFERENCES posicoes(id),
            FOREIGN KEY(posicao_id) REFERENCES posicoes(id)
        );
        """
    )
    colunas = {
        "operadores": {"funcao": "TEXT NOT NULL DEFAULT 'separador'"},
        "tarefas": {
            "papel": "TEXT NOT NULL DEFAULT 'separador'",
            "pallet_op_id": "INTEGER REFERENCES pallets_op(id)",
        },
        "ajustes_estoque": {"lote_anterior_id": "INTEGER REFERENCES lotes(id)"},
        "movimentacoes": {"pallet_op_id": "INTEGER REFERENCES pallets_op(id)"},
    }
    for tabela, definicoes in colunas.items():
        existentes = {linha["name"] for linha in conexao.execute(f"PRAGMA table_info({tabela})")}
        for nome, definicao in definicoes.items():
            if nome not in existentes:
                conexao.execute(f"ALTER TABLE {tabela} ADD COLUMN {nome} {definicao}")
    conexao.commit()
    conexao.close()


# ---------- Auditoria ----------

def registrar_auditoria(conexao, entidade, entidade_id, acao, detalhes=None):
    conexao.execute(
        "INSERT INTO auditoria (entidade, entidade_id, acao, detalhes) VALUES (?, ?, ?, ?)",
        (entidade, entidade_id, acao, json.dumps(detalhes or {}, ensure_ascii=False)),
    )


def listar_auditoria(limite=200):
    conexao = conectar()
    try:
        linhas = conexao.execute(
            "SELECT * FROM auditoria ORDER BY id DESC LIMIT ?", (limite,)
        ).fetchall()
        return [dict(l) for l in linhas]
    finally:
        conexao.close()


# ---------- Materiais ----------

def listar_materiais():
    conexao = conectar()
    try:
        linhas = conexao.execute(
            "SELECT * FROM materiais ORDER BY codigo"
        ).fetchall()
        return [dict(l) for l in linhas]
    finally:
        conexao.close()


def buscar_material(material_id):
    conexao = conectar()
    try:
        linha = conexao.execute(
            "SELECT * FROM materiais WHERE id = ?", (material_id,)
        ).fetchone()
        return dict(linha) if linha else None
    finally:
        conexao.close()


def criar_material(dados):
    conexao = conectar()
    try:
        cursor = conexao.execute(
            "INSERT INTO materiais (codigo, descricao, unidade) VALUES (?, ?, ?)",
            (dados["codigo"].strip(), dados["descricao"].strip(), dados["unidade"].strip()),
        )
        registrar_auditoria(conexao, "materiais", cursor.lastrowid, "criacao", dados)
        conexao.commit()
        return buscar_material(cursor.lastrowid)
    except sqlite3.IntegrityError as erro:
        raise ValueError("Código de material já cadastrado") from erro
    finally:
        conexao.close()


def atualizar_material(material_id, dados):
    conexao = conectar()
    try:
        campos = []
        valores = []
        for campo in ("descricao", "unidade"):
            if dados.get(campo) is not None:
                campos.append(f"{campo} = ?")
                valores.append(dados[campo].strip())
        if "ativo" in dados and dados["ativo"] is not None:
            campos.append("ativo = ?")
            valores.append(1 if dados["ativo"] else 0)
        if not campos:
            return buscar_material(material_id)
        valores.append(material_id)
        conexao.execute(
            f"UPDATE materiais SET {', '.join(campos)} WHERE id = ?", valores
        )
        registrar_auditoria(conexao, "materiais", material_id, "alteracao", dados)
        conexao.commit()
        return buscar_material(material_id)
    finally:
        conexao.close()


# ---------- Operadores ----------

def listar_operadores():
    conexao = conectar()
    try:
        linhas = conexao.execute(
            "SELECT * FROM operadores ORDER BY matricula"
        ).fetchall()
        return [dict(l) for l in linhas]
    finally:
        conexao.close()


def buscar_operador(matricula):
    conexao = conectar()
    try:
        linha = conexao.execute(
            "SELECT * FROM operadores WHERE matricula = ?", (matricula,)
        ).fetchone()
        return dict(linha) if linha else None
    finally:
        conexao.close()


def criar_operador(matricula, nome, funcao="separador"):
    conexao = conectar()
    try:
        cursor = conexao.execute(
            "INSERT INTO operadores (matricula, nome, funcao) VALUES (?, ?, ?)",
            (matricula.strip(), nome.strip(), funcao),
        )
        registrar_auditoria(
            conexao, "operadores", cursor.lastrowid, "criacao",
            {"matricula": matricula, "nome": nome, "funcao": funcao},
        )
        conexao.commit()
        linha = conexao.execute(
            "SELECT * FROM operadores WHERE id = ?", (cursor.lastrowid,)
        ).fetchone()
        return dict(linha)
    except sqlite3.IntegrityError as erro:
        raise ValueError("Matrícula já cadastrada") from erro
    finally:
        conexao.close()


def atualizar_operador(operador_id, dados):
    conexao = conectar()
    try:
        campos, valores = [], []
        if dados.get("nome") is not None:
            campos.append("nome = ?")
            valores.append(dados["nome"].strip())
        if dados.get("funcao") is not None:
            campos.append("funcao = ?")
            valores.append(dados["funcao"])
        if "ativo" in dados and dados["ativo"] is not None:
            campos.append("ativo = ?")
            valores.append(1 if dados["ativo"] else 0)
        if campos:
            valores.append(operador_id)
            conexao.execute(
                f"UPDATE operadores SET {', '.join(campos)} WHERE id = ?", valores
            )
            registrar_auditoria(conexao, "operadores", operador_id, "alteracao", dados)
            conexao.commit()
        linha = conexao.execute(
            "SELECT * FROM operadores WHERE id = ?", (operador_id,)
        ).fetchone()
        return dict(linha) if linha else None
    finally:
        conexao.close()


# ---------- Posições / Lotes / Pallets ----------

def listar_posicoes():
    conexao = conectar()
    try:
        return [dict(l) for l in conexao.execute("SELECT * FROM posicoes ORDER BY codigo").fetchall()]
    finally:
        conexao.close()


def criar_posicao(codigo, descricao=None):
    conexao = conectar()
    try:
        cursor = conexao.execute(
            "INSERT INTO posicoes (codigo, descricao) VALUES (?, ?)",
            (codigo.strip(), (descricao or "").strip() or None),
        )
        registrar_auditoria(conexao, "posicoes", cursor.lastrowid, "criacao", {"codigo": codigo})
        conexao.commit()
        return dict(conexao.execute("SELECT * FROM posicoes WHERE id = ?", (cursor.lastrowid,)).fetchone())
    except sqlite3.IntegrityError as erro:
        raise ValueError("Posição já cadastrada") from erro
    finally:
        conexao.close()


def listar_lotes(material_id=None):
    conexao = conectar()
    try:
        if material_id:
            linhas = conexao.execute(
                "SELECT * FROM lotes WHERE material_id = ? ORDER BY criado_em, id",
                (material_id,),
            ).fetchall()
        else:
            linhas = conexao.execute("SELECT * FROM lotes ORDER BY id").fetchall()
        return [dict(l) for l in linhas]
    finally:
        conexao.close()


def criar_lote(material_id, codigo, validade=None):
    conexao = conectar()
    try:
        if not conexao.execute(
                "SELECT id FROM materiais WHERE id = ?", (material_id,)).fetchone():
            raise ValueError("Material inexistente")
        cursor = conexao.execute(
            "INSERT INTO lotes (material_id, codigo, validade) VALUES (?, ?, ?)",
            (material_id, codigo.strip(), validade),
        )
        registrar_auditoria(conexao, "lotes", cursor.lastrowid, "criacao",
                            {"material_id": material_id, "codigo": codigo})
        conexao.commit()
        return dict(conexao.execute("SELECT * FROM lotes WHERE id = ?", (cursor.lastrowid,)).fetchone())
    except sqlite3.IntegrityError as erro:
        raise ValueError("Lote já cadastrado para este material") from erro
    finally:
        conexao.close()


def listar_pallets():
    conexao = conectar()
    try:
        linhas = conexao.execute("""
            SELECT p.*, l.codigo AS lote_codigo, l.material_id AS material_id,
                   pos.codigo AS posicao_codigo
            FROM pallets p
            JOIN lotes l ON l.id = p.lote_id
            LEFT JOIN posicoes pos ON pos.id = p.posicao_id
            ORDER BY p.id
        """).fetchall()
        return [dict(l) for l in linhas]
    finally:
        conexao.close()


def criar_pallet(lote_id, codigo, posicao_id=None):
    conexao = conectar()
    try:
        if not conexao.execute(
                "SELECT id FROM lotes WHERE id = ?", (lote_id,)).fetchone():
            raise ValueError("Lote inexistente")
        if posicao_id is not None and not conexao.execute(
                "SELECT id FROM posicoes WHERE id = ?", (posicao_id,)).fetchone():
            raise ValueError("Posição inexistente")
        cursor = conexao.execute(
            "INSERT INTO pallets (lote_id, codigo, posicao_id) VALUES (?, ?, ?)",
            (lote_id, codigo.strip(), posicao_id),
        )
        registrar_auditoria(conexao, "pallets", cursor.lastrowid, "criacao",
                            {"lote_id": lote_id, "codigo": codigo})
        conexao.commit()
        return dict(conexao.execute("SELECT * FROM pallets WHERE id = ?", (cursor.lastrowid,)).fetchone())
    except sqlite3.IntegrityError as erro:
        raise ValueError("Pallet já cadastrado (código duplicado)") from erro
    finally:
        conexao.close()


def definir_bloqueio_pallet(pallet_id, bloqueado):
    """Retorna o pallet atualizado, ou None se o ID não existir."""
    conexao = conectar()
    try:
        if not conexao.execute(
                "SELECT id FROM pallets WHERE id = ?", (pallet_id,)).fetchone():
            return None
        conexao.execute(
            "UPDATE pallets SET bloqueado = ? WHERE id = ?",
            (1 if bloqueado else 0, pallet_id),
        )
        registrar_auditoria(conexao, "pallets", pallet_id,
                            "bloqueio" if bloqueado else "desbloqueio", {})
        conexao.commit()
        return dict(conexao.execute("SELECT * FROM pallets WHERE id = ?", (pallet_id,)).fetchone())
    finally:
        conexao.close()


# ---------- Estoque ----------

def calcular_saldo(material_id=None, lote_id=None, pallet_id=None):
    """Calcula saldo (entradas - saídas) filtrando por UMA referência por vez.
    Chamador deve escolher explicitamente qual granularidade quer consultar."""
    conexao = conectar()
    try:
        sql = (
            "SELECT COALESCE(SUM(CASE WHEN tipo='entrada' THEN quantidade ELSE 0 END)"
            " - SUM(CASE WHEN tipo='saida' THEN quantidade ELSE 0 END), 0) AS saldo"
            " FROM movimentacoes WHERE 1=1"
        )
        params = []
        if material_id is not None:
            sql += " AND material_id = ?"
            params.append(material_id)
        if lote_id is not None:
            sql += " AND lote_id = ?"
            params.append(lote_id)
        if pallet_id is not None:
            sql += " AND pallet_id = ?"
            params.append(pallet_id)
        linha = conexao.execute(sql, params).fetchone()
        ajuste_sql = "SELECT COALESCE(SUM(quantidade_ajuste), 0) AS saldo FROM ajustes_estoque WHERE 1=1"
        ajuste_params = []
        if pallet_id is not None:
            ajuste_sql += " AND pallet_id = ?"
            ajuste_params.append(pallet_id)
        elif lote_id is not None:
            ajuste_sql += " AND (lote_id = ? OR pallet_id IN (SELECT id FROM pallets WHERE lote_id = ?))"
            ajuste_params.extend((lote_id, lote_id))
        elif material_id is not None:
            ajuste_sql += " AND material_id = ?"
            ajuste_params.append(material_id)
        ajuste = conexao.execute(ajuste_sql, ajuste_params).fetchone()["saldo"]
        return float(linha["saldo"] + ajuste)
    finally:
        conexao.close()


def estoque_por_material():
    conexao = conectar()
    try:
        linhas = conexao.execute("""
            SELECT m.id, m.codigo, m.descricao, m.unidade,
            COALESCE(SUM(CASE WHEN mv.tipo='entrada' THEN mv.quantidade ELSE 0 END)
                - SUM(CASE WHEN mv.tipo='saida' THEN mv.quantidade ELSE 0 END), 0)
            + COALESCE((SELECT SUM(a.quantidade_ajuste) FROM ajustes_estoque a
                     WHERE a.material_id=m.id), 0) AS saldo
            FROM materiais m
            LEFT JOIN movimentacoes mv ON mv.material_id = m.id
            GROUP BY m.id
            ORDER BY m.codigo
        """).fetchall()
        return [dict(l) for l in linhas]
    finally:
        conexao.close()


def estoque_por_lote():
    conexao = conectar()
    try:
        linhas = conexao.execute("""
            SELECT l.id, l.codigo, l.material_id, m.codigo AS material_codigo, l.validade,
            COALESCE(SUM(CASE WHEN mv.tipo='entrada' THEN mv.quantidade ELSE 0 END)
                - SUM(CASE WHEN mv.tipo='saida' THEN mv.quantidade ELSE 0 END), 0)
            + COALESCE((SELECT SUM(a.quantidade_ajuste) FROM ajustes_estoque a
                     WHERE a.material_id=l.material_id
                    AND (a.lote_id=l.id OR a.pallet_id IN
                         (SELECT p.id FROM pallets p WHERE p.lote_id=l.id))), 0) AS saldo
            FROM lotes l
            JOIN materiais m ON m.id = l.material_id
            LEFT JOIN movimentacoes mv ON mv.lote_id = l.id
            GROUP BY l.id
            ORDER BY l.id
        """).fetchall()
        return [dict(l) for l in linhas]
    finally:
        conexao.close()


def itens_bloqueados():
    conexao = conectar()
    try:
        linhas = conexao.execute("""
            SELECT p.id, p.codigo, p.bloqueado, l.codigo AS lote_codigo,
                   m.codigo AS material_codigo
            FROM pallets p
            JOIN lotes l ON l.id = p.lote_id
            JOIN materiais m ON m.id = l.material_id
            WHERE p.bloqueado = 1
        """).fetchall()
        return [dict(l) for l in linhas]
    finally:
        conexao.close()


# ---------- Ordens de Produção ----------

def listar_ordens():
    conexao = conectar()
    try:
        return [dict(l) for l in conexao.execute(
            "SELECT * FROM ordens_producao ORDER BY id DESC"
        ).fetchall()]
    finally:
        conexao.close()


def buscar_ordem(op_id):
    conexao = conectar()
    try:
        linha = conexao.execute("SELECT * FROM ordens_producao WHERE id = ?", (op_id,)).fetchone()
        if not linha:
            return None
        ordem = dict(linha)
        ordem["itens"] = [dict(l) for l in conexao.execute(
            "SELECT * FROM itens_ordem_producao WHERE op_id = ?", (op_id,)
        ).fetchall()]
        return ordem
    finally:
        conexao.close()


def criar_ordem(dados):
    conexao = conectar()
    try:
        for item in dados.get("itens", []):
            if not conexao.execute(
                    "SELECT id FROM materiais WHERE id = ?", (item["material_id"],)).fetchone():
                raise ValueError(f"Material {item['material_id']} inexistente")
        cursor = conexao.execute(
            "INSERT INTO ordens_producao (codigo, produto, prioridade, prazo) VALUES (?, ?, ?, ?)",
            (dados["codigo"].strip(), dados["produto"].strip(),
             int(dados.get("prioridade", 3)), dados.get("prazo")),
        )
        op_id = cursor.lastrowid
        for item in dados.get("itens", []):
            conexao.execute(
                "INSERT INTO itens_ordem_producao (op_id, material_id, quantidade) VALUES (?, ?, ?)",
                (op_id, item["material_id"], float(item["quantidade"])),
            )
        registrar_auditoria(conexao, "ordens_producao", op_id, "criacao", dados)
        conexao.commit()
        return buscar_ordem(op_id)
    except sqlite3.IntegrityError as erro:
        raise ValueError("Código de OP já cadastrado") from erro
    finally:
        conexao.close()


# ---------- Demandas simuladas e embalagem ----------

def _resumo_demanda(conexao, demanda_id):
    demanda = conexao.execute(
        "SELECT * FROM demandas WHERE id = ?", (demanda_id,)
    ).fetchone()
    if not demanda:
        return None
    resultado = dict(demanda)
    resultado["itens"] = [dict(linha) for linha in conexao.execute(
        "SELECT di.*, m.codigo AS codigo_catalogo FROM demanda_itens di "
        "JOIN materiais m ON m.id = di.material_id "
        "WHERE di.demanda_id = ? ORDER BY di.id", (demanda_id,)
    ).fetchall()]
    for item in resultado["itens"]:
        saldo = calcular_saldo(material_id=item["material_id"])
        item["saldo_disponivel"] = saldo
        item["saldo_faltante"] = round(max(0, item["quantidade_total"] - saldo), 6)
    return resultado


def listar_demandas():
    conexao = conectar()
    try:
        linhas = conexao.execute(
            "SELECT d.*, op.codigo AS codigo_op FROM demandas d "
            "LEFT JOIN ordens_producao op ON op.id = d.op_id ORDER BY d.id DESC"
        ).fetchall()
        return [dict(linha) for linha in linhas]
    finally:
        conexao.close()


def buscar_demanda(demanda_id):
    conexao = conectar()
    try:
        return _resumo_demanda(conexao, demanda_id)
    finally:
        conexao.close()


def _inserir_itens_demanda(conexao, demanda_id, quantidade_cargas, itens):
    for item in itens:
        codigo = item["codigo_material"].strip()
        descricao = item["descricao_material"].strip()
        unidade = item["unidade"].strip()
        fornecedor = item["fornecedor"].strip()
        peso_sacaria = float(item["peso_sacaria"])
        capacidade = float(item["capacidade_pallet"])
        if peso_sacaria > capacidade:
            raise ValueError(f"A sacaria do material {codigo} excede a capacidade do pallet")

        material = conexao.execute(
            "SELECT * FROM materiais WHERE codigo = ?", (codigo,)
        ).fetchone()
        if material:
            if material["descricao"].strip() != descricao or material["unidade"].strip() != unidade:
                raise ValueError(f"Código {codigo} já existe com descrição ou unidade diferente")
            if not material["ativo"]:
                raise ValueError(f"Material {codigo} está inativo")
            material_id = material["id"]
        else:
            cursor = conexao.execute(
                "INSERT INTO materiais (codigo, descricao, unidade) VALUES (?, ?, ?)",
                (codigo, descricao, unidade),
            )
            material_id = cursor.lastrowid
            registrar_auditoria(conexao, "materiais", material_id, "criacao_por_demanda", {
                "codigo": codigo, "descricao": descricao, "unidade": unidade,
            })

        conexao.execute(
            """INSERT INTO configuracoes_embalagem
               (material_id, fornecedor, peso_sacaria, capacidade_pallet)
               VALUES (?, ?, ?, ?)
               ON CONFLICT(material_id, fornecedor) DO UPDATE SET
                   peso_sacaria=excluded.peso_sacaria,
                   capacidade_pallet=excluded.capacidade_pallet,
                   atualizado_em=CURRENT_TIMESTAMP""",
            (material_id, fornecedor, peso_sacaria, capacidade),
        )
        configuracao = conexao.execute(
            "SELECT id FROM configuracoes_embalagem WHERE material_id=? AND fornecedor=?",
            (material_id, fornecedor),
        ).fetchone()
        quantidade_total = round(float(item["quantidade_por_carga"]) * quantidade_cargas, 6)
        sacarias = math.floor((quantidade_total + 1e-9) / peso_sacaria)
        quantidade_sacarias = round(sacarias * peso_sacaria, 6)
        quantidade_pesagem = round(max(0, quantidade_total - quantidade_sacarias), 6)
        conexao.execute(
            """INSERT INTO demanda_itens
               (demanda_id, material_id, configuracao_id, codigo_material,
                descricao_material, localizacao, quantidade_por_carga,
                quantidade_total, unidade, fornecedor, peso_sacaria,
                capacidade_pallet, sacarias_fechadas, quantidade_em_sacarias,
                quantidade_em_pesagem, observacao)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (demanda_id, material_id, configuracao["id"], codigo, descricao,
             item["localizacao"].strip(), float(item["quantidade_por_carga"]),
             quantidade_total, unidade, fornecedor, peso_sacaria, capacidade,
             sacarias, quantidade_sacarias, quantidade_pesagem,
             item.get("observacao")),
        )


def criar_demanda(dados):
    conexao = conectar()
    try:
        cursor = conexao.execute(
            "INSERT INTO demandas (codigo, produto, quantidade_cargas, observacao) VALUES (?, ?, ?, ?)",
            (dados["codigo"].strip(), dados["produto"].strip(),
             int(dados["quantidade_cargas"]), dados.get("observacao")),
        )
        demanda_id = cursor.lastrowid
        _inserir_itens_demanda(conexao, demanda_id, int(dados["quantidade_cargas"]), dados["itens"])
        registrar_auditoria(conexao, "demandas", demanda_id, "criacao", dados)
        conexao.commit()
        return _resumo_demanda(conexao, demanda_id)
    except sqlite3.IntegrityError as erro:
        raise ValueError("Código de demanda já cadastrado") from erro
    finally:
        conexao.close()


def atualizar_demanda(demanda_id, dados):
    conexao = conectar()
    try:
        demanda = conexao.execute("SELECT * FROM demandas WHERE id=?", (demanda_id,)).fetchone()
        if not demanda:
            return None
        if demanda["status"] != "rascunho":
            raise ValueError("Demanda confirmada não pode ser alterada")
        conexao.execute("DELETE FROM demanda_itens WHERE demanda_id=?", (demanda_id,))
        conexao.execute(
            "UPDATE demandas SET codigo=?, produto=?, quantidade_cargas=?, observacao=? WHERE id=?",
            (dados["codigo"].strip(), dados["produto"].strip(),
             int(dados["quantidade_cargas"]), dados.get("observacao"), demanda_id),
        )
        _inserir_itens_demanda(conexao, demanda_id, int(dados["quantidade_cargas"]), dados["itens"])
        registrar_auditoria(conexao, "demandas", demanda_id, "alteracao_rascunho", dados)
        conexao.commit()
        return _resumo_demanda(conexao, demanda_id)
    except sqlite3.IntegrityError as erro:
        raise ValueError("Código de demanda já cadastrado") from erro
    finally:
        conexao.close()


def _planejar_pallets(quantidade_total, peso_sacaria, capacidade):
    sacarias = math.floor((quantidade_total + 1e-9) / peso_sacaria)
    pesagem = round(max(0, quantidade_total - sacarias * peso_sacaria), 6)
    sacarias_por_pallet = math.floor((capacidade + 1e-9) / peso_sacaria)
    if sacarias_por_pallet < 1:
        raise ValueError("A capacidade do pallet deve comportar ao menos uma sacaria")

    pallets = []
    restante = sacarias
    while restante:
        quantidade_sacarias = min(restante, sacarias_por_pallet)
        peso = round(quantidade_sacarias * peso_sacaria, 6)
        pallets.append({"sacarias": quantidade_sacarias, "pesagem": 0.0, "quantidade": peso})
        restante -= quantidade_sacarias

    if pesagem > 1e-6:
        if pallets and pallets[-1]["quantidade"] + pesagem <= capacidade + 1e-6:
            pallets[-1]["pesagem"] = pesagem
            pallets[-1]["quantidade"] = round(pallets[-1]["quantidade"] + pesagem, 6)
        else:
            pallets.append({"sacarias": 0, "pesagem": pesagem, "quantidade": pesagem})
    if not pallets:
        pallets.append({"sacarias": 0, "pesagem": quantidade_total, "quantidade": quantidade_total})
    return pallets


def confirmar_demanda(demanda_id):
    conexao = conectar()
    try:
        demanda = conexao.execute("SELECT * FROM demandas WHERE id=?", (demanda_id,)).fetchone()
        if not demanda:
            raise ValueError("Demanda não encontrada")
        if demanda["status"] != "rascunho":
            raise ValueError("Demanda já confirmada")
        codigo_op = demanda["codigo"].strip()
        cursor = conexao.execute(
            "INSERT INTO ordens_producao (codigo, produto, prioridade) VALUES (?, ?, 3)",
            (codigo_op, demanda["produto"]),
        )
        op_id = cursor.lastrowid
        registrar_auditoria(conexao, "ordens_producao", op_id, "criacao_por_demanda", {
            "demanda_id": demanda_id, "codigo": codigo_op,
        })
        itens = conexao.execute(
            "SELECT * FROM demanda_itens WHERE demanda_id=? ORDER BY id", (demanda_id,)
        ).fetchall()
        for item in itens:
            item_cursor = conexao.execute(
                "INSERT INTO itens_ordem_producao (op_id, material_id, quantidade) VALUES (?, ?, ?)",
                (op_id, item["material_id"], item["quantidade_total"]),
            )
            item_op_id = item_cursor.lastrowid
            lote_id = _recomendar_lote_fifo(conexao, item["material_id"], item["quantidade_total"])
            tarefa_cursor = conexao.execute(
                """INSERT INTO tarefas
                   (op_id, item_id, material_id, quantidade, prioridade,
                    lote_recomendado_id, papel)
                   VALUES (?, ?, ?, ?, 3, ?, 'separador')""",
                (op_id, item_op_id, item["material_id"], item["quantidade_total"], lote_id),
            )
            registrar_auditoria(conexao, "tarefas", tarefa_cursor.lastrowid,
                                "criacao_separacao", {"op_id": op_id, "item_id": item_op_id})
            planos = _planejar_pallets(
                item["quantidade_total"], item["peso_sacaria"], item["capacidade_pallet"]
            )
            for numero, plano in enumerate(planos, 1):
                status = "previsto" if abs(plano["quantidade"] - item["capacidade_pallet"]) <= 1e-6 else "em_montagem"
                conexao.execute(
                    """INSERT INTO pallets_op
                       (op_id, item_id, demanda_item_id, numero, sacarias,
                        quantidade_pesagem, quantidade_total, capacidade, status)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (op_id, item_op_id, item["id"], numero, plano["sacarias"],
                     plano["pesagem"], plano["quantidade"], item["capacidade_pallet"], status),
                )
        conexao.execute(
            "UPDATE demandas SET status='confirmada', op_id=?, confirmado_em=? WHERE id=?",
            (op_id, agora(), demanda_id),
        )
        registrar_auditoria(conexao, "demandas", demanda_id, "confirmacao", {"op_id": op_id})
        conexao.commit()
        return buscar_ordem(op_id)
    except sqlite3.IntegrityError as erro:
        raise ValueError("Não foi possível confirmar: código de OP ou vínculo duplicado") from erro
    finally:
        conexao.close()


def listar_pallets_op(op_id=None):
    conexao = conectar()
    try:
        sql = """SELECT p.*, m.codigo AS material_codigo, m.descricao AS material_descricao,
                        op.codigo AS op_codigo, t.id AS tarefa_separador_id
                 FROM pallets_op p
                 JOIN itens_ordem_producao io ON io.id=p.item_id
                 JOIN materiais m ON m.id=io.material_id
                 JOIN ordens_producao op ON op.id=p.op_id
                 LEFT JOIN tarefas t ON t.item_id=p.item_id AND t.papel='separador'
                 WHERE 1=1"""
        parametros = []
        if op_id is not None:
            sql += " AND p.op_id=?"
            parametros.append(op_id)
        sql += " ORDER BY p.op_id, p.item_id, p.numero"
        return [dict(linha) for linha in conexao.execute(sql, parametros).fetchall()]
    finally:
        conexao.close()


def definir_bloqueio_pallet_op(pallet_op_id, bloqueado):
    conexao = conectar()
    try:
        pallet = conexao.execute(
            "SELECT * FROM pallets_op WHERE id=?", (pallet_op_id,)
        ).fetchone()
        if not pallet:
            return None
        if bloqueado:
            if pallet["status"] in ("movimentado", "bloqueado"):
                return dict(pallet)
            conexao.execute(
                "UPDATE pallets_op SET status_anterior=status, status='bloqueado' WHERE id=?",
                (pallet_op_id,),
            )
            acao = "bloqueio"
        else:
            if pallet["status"] != "bloqueado":
                return dict(pallet)
            restaurado = pallet["status_anterior"] or "em_montagem"
            conexao.execute(
                "UPDATE pallets_op SET status=?, status_anterior=NULL WHERE id=?",
                (restaurado, pallet_op_id),
            )
            acao = "desbloqueio"
        registrar_auditoria(conexao, "pallets_op", pallet_op_id, acao, {})
        conexao.commit()
        return dict(conexao.execute(
            "SELECT * FROM pallets_op WHERE id=?", (pallet_op_id,)
        ).fetchone())
    finally:
        conexao.close()


def atualizar_status_ordem(op_id, status):
    conexao = conectar()
    try:
        conexao.execute(
            "UPDATE ordens_producao SET status = ?, finalizado_em = ? WHERE id = ?",
            (status, agora() if status in ("finalizada", "cancelada") else None, op_id),
        )
        registrar_auditoria(conexao, "ordens_producao", op_id, status, {})
        conexao.commit()
        return buscar_ordem(op_id)
    finally:
        conexao.close()


def gerar_tarefas_da_ordem(op_id, operador_id=None):
    conexao = conectar()
    try:
        ordem = conexao.execute("SELECT * FROM ordens_producao WHERE id = ?", (op_id,)).fetchone()
        if not ordem:
            raise ValueError("OP não encontrada")
        if ordem["status"] in ("finalizada", "cancelada"):
            raise ValueError("OP não permite gerar tarefas neste estado")

        if operador_id is not None and not conexao.execute(
                "SELECT id FROM operadores WHERE id = ?", (operador_id,)).fetchone():
            raise ValueError("Operador inexistente")

        existentes = conexao.execute(
            "SELECT item_id FROM tarefas WHERE op_id = ?", (op_id,)
        ).fetchall()
        ja_gerados = {l["item_id"] for l in existentes}

        itens = conexao.execute(
            "SELECT * FROM itens_ordem_producao WHERE op_id = ?", (op_id,)
        ).fetchall()
        criadas = []
        for item in itens:
            if item["id"] in ja_gerados:
                continue
            lote_id = _recomendar_lote_fifo(conexao, item["material_id"], item["quantidade"])
            cursor = conexao.execute(
                """INSERT INTO tarefas
                   (op_id, item_id, material_id, operador_id, quantidade, prioridade, lote_recomendado_id)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (op_id, item["id"], item["material_id"], operador_id,
                 item["quantidade"], ordem["prioridade"], lote_id),
            )
            criadas.append(cursor.lastrowid)
            registrar_auditoria(conexao, "tarefas", cursor.lastrowid, "criacao",
                                {"op_id": op_id, "item_id": item["id"]})
        conexao.commit()
        return criadas
    finally:
        conexao.close()


def _recomendar_lote_fifo(conexao, material_id, quantidade):
    """Recomendação FIFO: lote mais antigo com saldo positivo."""
    linhas = conexao.execute("""
        SELECT l.id,
          COALESCE(SUM(CASE WHEN mv.tipo='entrada' THEN mv.quantidade ELSE 0 END)
                 - SUM(CASE WHEN mv.tipo='saida' THEN mv.quantidade ELSE 0 END), 0) AS saldo
        FROM lotes l
        LEFT JOIN movimentacoes mv ON mv.lote_id = l.id
        WHERE l.material_id = ?
        GROUP BY l.id
        ORDER BY l.criado_em ASC, l.id ASC
    """, (material_id,)).fetchall()
    for linha in linhas:
        if linha["saldo"] >= quantidade:
            return linha["id"]
    for linha in linhas:
        if linha["saldo"] > 0:
            return linha["id"]
    return None


# ---------- Tarefas ----------

def listar_tarefas(filtro=None):
    conexao = conectar()
    try:
        sql = """
        SELECT t.*, m.codigo AS material_codigo, m.descricao AS material_descricao,
               o.nome AS operador_nome, o.matricula AS operador_matricula,
               op.codigo AS op_codigo, l.codigo AS lote_codigo,
               p.codigo AS pallet_codigo, pos.codigo AS posicao_codigo
        FROM tarefas t
        JOIN materiais m ON m.id = t.material_id
        JOIN ordens_producao op ON op.id = t.op_id
        LEFT JOIN operadores o ON o.id = t.operador_id
        LEFT JOIN lotes l ON l.id = t.lote_recomendado_id
        LEFT JOIN pallets p ON p.id = t.pallet_id
        LEFT JOIN posicoes pos ON pos.id = t.posicao_id
        WHERE 1=1
        """
        params = []
        filtro = filtro or {}
        if filtro.get("op_id"):
            sql += " AND t.op_id = ?"
            params.append(filtro["op_id"])
        if filtro.get("operador_id"):
            sql += " AND t.operador_id = ?"
            params.append(filtro["operador_id"])
        if filtro.get("status"):
            sql += " AND t.status = ?"
            params.append(filtro["status"])
        if filtro.get("papel"):
            sql += " AND t.papel = ?"
            params.append(filtro["papel"])
        sql += " ORDER BY t.id DESC"
        return [dict(l) for l in conexao.execute(sql, params).fetchall()]
    finally:
        conexao.close()


def buscar_tarefa(tarefa_id):
    conexao = conectar()
    try:
        linha = conexao.execute("""
         SELECT t.*, m.codigo AS material_codigo, m.descricao AS material_descricao, m.unidade AS material_unidade,
             o.nome AS operador_nome, o.matricula AS operador_matricula,
             op.codigo AS op_codigo, l.codigo AS lote_codigo,
             p.codigo AS pallet_codigo, pos.codigo AS posicao_codigo,
             pp.numero AS pallet_op_numero, pp.status AS pallet_op_status,
             pp.quantidade_total AS pallet_op_quantidade, pp.capacidade AS pallet_op_capacidade
        FROM tarefas t
        JOIN materiais m ON m.id = t.material_id
        JOIN ordens_producao op ON op.id = t.op_id
        LEFT JOIN operadores o ON o.id = t.operador_id
        LEFT JOIN lotes l ON l.id = t.lote_recomendado_id
        LEFT JOIN pallets p ON p.id = t.pallet_id
        LEFT JOIN posicoes pos ON pos.id = t.posicao_id
        LEFT JOIN pallets_op pp ON pp.id = t.pallet_op_id
        WHERE t.id = ?
        """, (tarefa_id,)).fetchone()
        return dict(linha) if linha else None
    finally:
        conexao.close()


def iniciar_tarefa(tarefa_id, operador_id):
    conexao = conectar()
    try:
        t = conexao.execute("SELECT * FROM tarefas WHERE id = ?", (tarefa_id,)).fetchone()
        if not t:
            raise ValueError("Tarefa não encontrada")
        if t["status"] != "pendente":
            raise ValueError("Tarefa não está pendente")
        if t["operador_id"] is not None and t["operador_id"] != operador_id:
            raise ValueError("Tarefa atribuída a outro operador")
        operador = conexao.execute(
            "SELECT funcao, ativo FROM operadores WHERE id=?", (operador_id,)
        ).fetchone()
        if not operador or not operador["ativo"]:
            raise ValueError("Operador inexistente ou inativo")
        if operador["funcao"] != t["papel"]:
            raise ValueError(f"Tarefa reservada à função {t['papel']}")
        if t["papel"] == "empilhadeira" and t["pallet_op_id"]:
            pallet = conexao.execute(
                "SELECT status FROM pallets_op WHERE id=?", (t["pallet_op_id"],)
            ).fetchone()
            if not pallet or pallet["status"] != "fechado":
                raise ValueError("Empilhadeira só pode iniciar pallet fechado")
        conexao.execute(
            "UPDATE tarefas SET status = 'em_andamento', iniciado_em = ?, operador_id = ? WHERE id = ?",
            (agora(), operador_id, tarefa_id),
        )
        registrar_auditoria(conexao, "tarefas", tarefa_id, "inicio",
                            {"operador_id": operador_id})
        conexao.commit()
        return buscar_tarefa(tarefa_id)
    finally:
        conexao.close()


def concluir_tarefa(tarefa_id, quantidade_retirada, pallet_id=None,
                    posicao_id=None, observacao=None, operador_id=None):
    conexao = conectar()
    try:
        t = conexao.execute("SELECT * FROM tarefas WHERE id = ?", (tarefa_id,)).fetchone()
        if not t:
            raise ValueError("Tarefa não encontrada")
        if t["status"] != "em_andamento":
            raise ValueError("Tarefa não está em andamento")
        if operador_id is not None and t["operador_id"] != operador_id:
            raise ValueError("Tarefa iniciada por outro operador")
        if t["papel"] != "separador":
            raise ValueError("Tarefa de empilhadeira deve movimentar o pallet")

        pallets_planejados = conexao.execute(
            "SELECT COUNT(*) AS n FROM pallets_op WHERE item_id=?", (t["item_id"],)
        ).fetchone()["n"]
        if pallets_planejados:
            if abs(float(quantidade_retirada) - float(t["quantidade"])) > 1e-6:
                raise ValueError("A separação deve registrar a quantidade total da tarefa")
            abertos = conexao.execute(
                "SELECT COUNT(*) AS n FROM pallets_op WHERE item_id=? AND status NOT IN ('fechado','movimentado')",
                (t["item_id"],),
            ).fetchone()["n"]
            if abertos:
                raise ValueError("A tarefa permanece ativa até fechar ou resolver todos os pallets")

        material_id = t["material_id"]
        lote_id = None
        if pallet_id:
            linha_pallet = conexao.execute(
                "SELECT * FROM pallets WHERE id = ?", (pallet_id,)
            ).fetchone()
            if not linha_pallet:
                raise ValueError("Pallet informado não existe")
            if linha_pallet["bloqueado"]:
                raise ValueError("Pallet bloqueado não pode ser movimentado")
            lote_id = linha_pallet["lote_id"]
            lote_do_pallet = conexao.execute(
                "SELECT material_id FROM lotes WHERE id = ?", (lote_id,)).fetchone()
            if lote_do_pallet and lote_do_pallet["material_id"] != material_id:
                raise ValueError("Pallet pertence a material diferente da tarefa")
        elif t["lote_recomendado_id"]:
            lote_id = t["lote_recomendado_id"]

        # CORREÇÃO: seleciona explicitamente UMA granularidade de saldo,
        # nunca lote_id e pallet_id simultaneamente com fallback implícito.
        if pallet_id is not None:
            saldo = calcular_saldo(pallet_id=pallet_id)
        elif lote_id is not None:
            saldo = calcular_saldo(lote_id=lote_id)
        else:
            saldo = calcular_saldo(material_id=material_id)

        if saldo < float(quantidade_retirada):
            raise ValueError("Saldo insuficiente para conclusão")

        conexao.execute(
            """UPDATE tarefas SET status='concluida', concluido_em=?,
               quantidade_retirada=?, pallet_id=?, posicao_id=?, observacao=?
               WHERE id=?""",
            (agora(), float(quantidade_retirada), pallet_id, posicao_id,
             observacao, tarefa_id),
        )
        conexao.execute(
            """INSERT INTO movimentacoes
               (tipo, material_id, lote_id, pallet_id, posicao_destino_id, quantidade,
                operador_id, tarefa_id, op_id, observacao)
               VALUES ('saida', ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (material_id, lote_id, pallet_id, posicao_id, float(quantidade_retirada),
             t["operador_id"], tarefa_id, t["op_id"], observacao),
        )
        registrar_auditoria(conexao, "tarefas", tarefa_id, "conclusao",
                            {"quantidade_retirada": quantidade_retirada})
        conexao.commit()

        # Finalizar OP se todas as tarefas concluídas
        pendentes = conexao.execute(
            "SELECT COUNT(*) AS n FROM tarefas WHERE op_id = ? AND status NOT IN ('concluida','cancelada')",
            (t["op_id"],),
        ).fetchone()["n"]
        if pendentes == 0:
            conexao.execute(
                "UPDATE ordens_producao SET status='finalizada', finalizado_em=? WHERE id=?",
                (agora(), t["op_id"]),
            )
            conexao.commit()
        return buscar_tarefa(tarefa_id)
    finally:
        conexao.close()


def fechar_pallet_op(pallet_op_id, operador_id, sacarias, quantidade_pesagem, posicao_id=None):
    conexao = conectar()
    try:
        pallet = conexao.execute(
            "SELECT * FROM pallets_op WHERE id=?", (pallet_op_id,)
        ).fetchone()
        if not pallet:
            raise ValueError("Pallet da OP não encontrado")
        if pallet["status"] not in ("previsto", "em_montagem", "pendente"):
            raise ValueError("Pallet não pode ser fechado neste estado")
        tarefa = conexao.execute(
            "SELECT * FROM tarefas WHERE item_id=? AND papel='separador'",
            (pallet["item_id"],),
        ).fetchone()
        if not tarefa or tarefa["status"] != "em_andamento" or tarefa["operador_id"] != operador_id:
            raise ValueError("Inicie a tarefa de separação correspondente antes de fechar pallets")
        operador = conexao.execute(
            "SELECT funcao, ativo FROM operadores WHERE id=?", (operador_id,)
        ).fetchone()
        if not operador or not operador["ativo"] or operador["funcao"] != "separador":
            raise ValueError("Somente separador ativo pode fechar pallet")
        if posicao_id is not None and not conexao.execute(
            "SELECT id FROM posicoes WHERE id=?", (posicao_id,)
        ).fetchone():
            raise ValueError("Posição inexistente")

        demanda_item = conexao.execute(
            "SELECT peso_sacaria FROM demanda_itens WHERE id=?",
            (pallet["demanda_item_id"],),
        ).fetchone()
        quantidade_real = round(int(sacarias) * demanda_item["peso_sacaria"] + float(quantidade_pesagem), 6)
        if abs(quantidade_real - float(pallet["quantidade_total"])) > 1e-6:
            raise ValueError("Pesagem e número de sacarias divergem do pallet planejado")
        if abs(quantidade_real - float(pallet["capacidade"])) > 1e-6:
            raise ValueError("Pallet abaixo da capacidade permanece em montagem")

        conexao.execute(
            "UPDATE pallets_op SET sacarias=?, quantidade_pesagem=?, status='fechado', posicao_id=?, fechado_em=? WHERE id=?",
            (int(sacarias), float(quantidade_pesagem), posicao_id, agora(), pallet_op_id),
        )
        existente = conexao.execute(
            "SELECT id FROM tarefas WHERE pallet_op_id=? AND papel='empilhadeira'",
            (pallet_op_id,),
        ).fetchone()
        if not existente:
            item = conexao.execute(
                "SELECT io.material_id, io.op_id, op.prioridade FROM itens_ordem_producao io "
                "JOIN ordens_producao op ON op.id=io.op_id WHERE io.id=?",
                (pallet["item_id"],),
            ).fetchone()
            cursor = conexao.execute(
                """INSERT INTO tarefas
                   (op_id, item_id, material_id, quantidade, prioridade, papel, pallet_op_id)
                   VALUES (?, ?, ?, ?, ?, 'empilhadeira', ?)""",
                (item["op_id"], pallet["item_id"], item["material_id"],
                 pallet["quantidade_total"], item["prioridade"], pallet_op_id),
            )
            registrar_auditoria(conexao, "tarefas", cursor.lastrowid,
                                "criacao_empilhadeira", {"pallet_op_id": pallet_op_id})
        registrar_auditoria(conexao, "pallets_op", pallet_op_id, "fechamento", {
            "sacarias": int(sacarias), "quantidade_pesagem": float(quantidade_pesagem),
            "operador_id": operador_id,
        })
        conexao.commit()
        return dict(conexao.execute("SELECT * FROM pallets_op WHERE id=?", (pallet_op_id,)).fetchone())
    finally:
        conexao.close()


def movimentar_pallet_op(tarefa_id, operador_id, posicao_destino_id):
    conexao = conectar()
    try:
        tarefa = conexao.execute("SELECT * FROM tarefas WHERE id=?", (tarefa_id,)).fetchone()
        if not tarefa:
            raise ValueError("Tarefa não encontrada")
        if tarefa["papel"] != "empilhadeira" or not tarefa["pallet_op_id"]:
            raise ValueError("Tarefa não é de movimentação de pallet")
        if tarefa["status"] != "em_andamento" or tarefa["operador_id"] != operador_id:
            raise ValueError("Tarefa não está iniciada por este operador")
        operador = conexao.execute(
            "SELECT funcao, ativo FROM operadores WHERE id=?", (operador_id,)
        ).fetchone()
        if not operador or not operador["ativo"] or operador["funcao"] != "empilhadeira":
            raise ValueError("Somente operador de empilhadeira ativo pode movimentar pallets")
        if not conexao.execute("SELECT id FROM posicoes WHERE id=?", (posicao_destino_id,)).fetchone():
            raise ValueError("Posição de destino inexistente")
        pallet = conexao.execute(
            "SELECT * FROM pallets_op WHERE id=?", (tarefa["pallet_op_id"],)
        ).fetchone()
        if not pallet or pallet["status"] != "fechado":
            raise ValueError("Somente pallet fechado e não movimentado pode ser transportado")
        conexao.execute(
            "UPDATE pallets_op SET status='movimentado', posicao_id=?, movimentado_em=? WHERE id=?",
            (posicao_destino_id, agora(), pallet["id"]),
        )
        conexao.execute(
            "UPDATE tarefas SET status='concluida', concluido_em=? WHERE id=?",
            (agora(), tarefa_id),
        )
        conexao.execute(
            """INSERT INTO movimentacoes
                    (tipo, material_id, lote_id, pallet_id, pallet_op_id,
                     posicao_origem_id, posicao_destino_id, quantidade,
                operador_id, tarefa_id, op_id, observacao)
                    VALUES ('transferencia', ?, ?, NULL, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (tarefa["material_id"], tarefa["lote_recomendado_id"], pallet["id"],
                 pallet["posicao_id"], posicao_destino_id, pallet["quantidade_total"],
                 operador_id, tarefa_id, tarefa["op_id"], f"Pallet de OP #{pallet['id']}"),
        )
        registrar_auditoria(conexao, "pallets_op", pallet["id"], "movimentacao", {
            "tarefa_id": tarefa_id, "operador_id": operador_id,
            "posicao_destino_id": posicao_destino_id,
        })
        pendentes = conexao.execute(
            "SELECT COUNT(*) AS n FROM tarefas WHERE op_id=? AND status NOT IN ('concluida','cancelada')",
            (tarefa["op_id"],),
        ).fetchone()["n"]
        if pendentes == 0:
            conexao.execute(
                "UPDATE ordens_producao SET status='finalizada', finalizado_em=? WHERE id=?",
                (agora(), tarefa["op_id"]),
            )
        conexao.commit()
        return buscar_tarefa(tarefa_id)
    finally:
        conexao.close()


# ---------- Movimentações ----------

def listar_movimentacoes(limite=500):
    conexao = conectar()
    try:
        linhas = conexao.execute("""
        SELECT mv.*, m.codigo AS material_codigo, o.nome AS operador_nome,
               op.codigo AS op_codigo
        FROM movimentacoes mv
        JOIN materiais m ON m.id = mv.material_id
        LEFT JOIN operadores o ON o.id = mv.operador_id
        LEFT JOIN ordens_producao op ON op.id = mv.op_id
        ORDER BY mv.id DESC LIMIT ?
        """, (limite,)).fetchall()
        return [dict(l) for l in linhas]
    finally:
        conexao.close()


def registrar_entrada(dados):
    conexao = conectar()
    try:
        material = conexao.execute("SELECT * FROM materiais WHERE id = ?",
                                   (dados["material_id"],)).fetchone()
        if not material:
            raise ValueError("Material inexistente")
        if not material["ativo"]:
            raise ValueError("Material inativo não pode receber entrada")

        lote_id = dados.get("lote_id")
        pallet_id = dados.get("pallet_id")
        posicao_id = dados.get("posicao_id")

        if lote_id:
            lote = conexao.execute(
                "SELECT * FROM lotes WHERE id = ?", (lote_id,)).fetchone()
            if not lote:
                raise ValueError("Lote inexistente")
            if lote["material_id"] != dados["material_id"]:
                raise ValueError("Lote não pertence ao material informado")

        if pallet_id:
            pallet = conexao.execute(
                "SELECT * FROM pallets WHERE id = ?", (pallet_id,)).fetchone()
            if not pallet:
                raise ValueError("Pallet inexistente")
            if lote_id and pallet["lote_id"] != lote_id:
                raise ValueError("Pallet não pertence ao lote informado")
            if not lote_id:
                lote_do_pallet = conexao.execute(
                    "SELECT material_id FROM lotes WHERE id = ?",
                    (pallet["lote_id"],)).fetchone()
                if lote_do_pallet and lote_do_pallet["material_id"] != dados["material_id"]:
                    raise ValueError("Pallet pertence a material diferente do informado")

        if posicao_id and not conexao.execute(
                "SELECT id FROM posicoes WHERE id = ?", (posicao_id,)).fetchone():
            raise ValueError("Posição inexistente")

        cursor = conexao.execute(
            """INSERT INTO movimentacoes
               (tipo, material_id, lote_id, pallet_id, posicao_destino_id,
                quantidade, operador_id, observacao)
               VALUES ('entrada', ?, ?, ?, ?, ?, ?, ?)""",
            (dados["material_id"], dados.get("lote_id"), dados.get("pallet_id"),
             dados.get("posicao_id"), float(dados["quantidade"]),
             dados.get("operador_id"), dados.get("observacao")),
        )
        registrar_auditoria(conexao, "movimentacoes", cursor.lastrowid,
                            "entrada", dados)
        conexao.commit()
        return dict(conexao.execute(
            "SELECT * FROM movimentacoes WHERE id = ?", (cursor.lastrowid,)
        ).fetchone())
    finally:
        conexao.close()


def registrar_ajuste_estoque(dados):
    conexao = conectar()
    try:
        material = conexao.execute(
            "SELECT id FROM materiais WHERE id=?", (dados["material_id"],)
        ).fetchone()
        if not material:
            raise ValueError("Material inexistente")
        if dados.get("lote_id"):
            lote = conexao.execute(
                "SELECT material_id FROM lotes WHERE id=?", (dados["lote_id"],)
            ).fetchone()
            if not lote:
                raise ValueError("Lote inexistente")
            if lote["material_id"] != dados["material_id"]:
                raise ValueError("Lote não pertence ao material informado")
        if dados.get("pallet_id"):
            pallet = conexao.execute(
                "SELECT lote_id FROM pallets WHERE id=?", (dados["pallet_id"],)
            ).fetchone()
            if not pallet:
                raise ValueError("Pallet inexistente")
            pallet_lote = conexao.execute(
                "SELECT material_id FROM lotes WHERE id=?", (pallet["lote_id"],)
            ).fetchone()
            if pallet_lote["material_id"] != dados["material_id"]:
                raise ValueError("Pallet pertence a material diferente do informado")
            if (dados.get("lote_id") and pallet["lote_id"] != dados["lote_id"]
                    and dados["tipo"] != "lote_incorreto"):
                raise ValueError("Pallet não pertence ao lote informado")
        for campo in ("posicao_anterior_id", "posicao_id"):
            if dados.get(campo) and not conexao.execute(
                "SELECT id FROM posicoes WHERE id=?", (dados[campo],)
            ).fetchone():
                raise ValueError("Posição inexistente")

        delta = float(dados["quantidade_ajuste"])
        tipo = dados["tipo"]
        tipos_sem_saldo = {"lote_incorreto", "posicao_incorreta"}
        if tipo in tipos_sem_saldo and delta != 0:
            raise ValueError("Correção de lote/posição deve manter o saldo")
        if tipo not in tipos_sem_saldo and delta == 0:
            raise ValueError("Informe uma quantidade de ajuste diferente de zero")
        if tipo == "falta_fisica" and delta >= 0:
            raise ValueError("Falta física exige ajuste negativo")
        if tipo in {"sobra_fisica", "pallet_encontrado", "pallet_sem_identificacao"} and delta <= 0:
            raise ValueError("Sobra ou pallet encontrado exige ajuste positivo")
        if tipo == "posicao_incorreta" and not dados.get("posicao_id"):
            raise ValueError("Informe a posição correta para o pallet")
        if tipo in {"lote_incorreto", "posicao_incorreta"} and not dados.get("pallet_id"):
            raise ValueError("Correção de lote/posição exige um pallet identificado")
        if tipo == "lote_incorreto" and not dados.get("lote_id"):
            raise ValueError("Informe o lote correto para o pallet")

        pallet_id = dados.get("pallet_id")
        lote_id = dados.get("lote_id")
        lote_anterior_id = None
        posicao_anterior_id = dados.get("posicao_anterior_id")
        if pallet_id:
            dados_pallet = conexao.execute(
                "SELECT lote_id, posicao_id FROM pallets WHERE id=?", (pallet_id,)
            ).fetchone()
            if tipo == "lote_incorreto":
                lote_anterior_id = dados_pallet["lote_id"]
            if tipo == "posicao_incorreta" and posicao_anterior_id is None:
                posicao_anterior_id = dados_pallet["posicao_id"]
            saldo_antes = calcular_saldo(pallet_id=pallet_id)
        elif lote_id:
            saldo_antes = calcular_saldo(lote_id=lote_id)
        else:
            saldo_antes = calcular_saldo(material_id=dados["material_id"])
        saldo_depois = round(saldo_antes + delta, 6)
        if saldo_depois < -1e-6:
            raise ValueError("Ajuste não pode deixar saldo negativo")

        cursor = conexao.execute(
            """INSERT INTO ajustes_estoque
               (material_id, lote_id, lote_anterior_id, pallet_id, posicao_anterior_id, posicao_id,
                tipo, motivo, observacao, quantidade_antes, quantidade_ajuste,
                quantidade_depois, responsavel)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (dados["material_id"], lote_id, lote_anterior_id, pallet_id,
             posicao_anterior_id, dados.get("posicao_id"), tipo,
             dados["motivo"].strip(), dados.get("observacao"), saldo_antes,
             delta, saldo_depois, dados["responsavel"].strip()),
        )
        if tipo == "lote_incorreto":
            conexao.execute("UPDATE pallets SET lote_id=? WHERE id=?", (lote_id, pallet_id))
        if tipo == "posicao_incorreta" and dados.get("posicao_id"):
            conexao.execute("UPDATE pallets SET posicao_id=? WHERE id=?", (dados["posicao_id"], pallet_id))
        registrar_auditoria(conexao, "ajustes_estoque", cursor.lastrowid, "ajuste_manual", dados)
        conexao.commit()
        return dict(conexao.execute(
            "SELECT * FROM ajustes_estoque WHERE id=?", (cursor.lastrowid,)
        ).fetchone())
    finally:
        conexao.close()


def listar_ajustes_estoque(limite=500):
    conexao = conectar()
    try:
        linhas = conexao.execute(
                        """SELECT a.*, m.codigo AS material_codigo, l.codigo AS lote_codigo,
                                     la.codigo AS lote_anterior_codigo,
                                     p.codigo AS pallet_codigo, po.codigo AS posicao_codigo
               FROM ajustes_estoque a
               JOIN materiais m ON m.id=a.material_id
               LEFT JOIN lotes l ON l.id=a.lote_id
                            LEFT JOIN lotes la ON la.id=a.lote_anterior_id
               LEFT JOIN pallets p ON p.id=a.pallet_id
               LEFT JOIN posicoes po ON po.id=a.posicao_id
               ORDER BY a.id DESC LIMIT ?""", (limite,)
        ).fetchall()
        return [dict(linha) for linha in linhas]
    finally:
        conexao.close()


# ---------- Eventos de dispositivo ----------

def registrar_evento(dados):
    conexao = conectar()
    try:
        existe = conexao.execute(
            "SELECT id FROM eventos_dispositivo WHERE evento_id = ?",
            (dados["evento_id"],),
        ).fetchone()
        if existe:
            return ({"status": "duplicado", "evento_id": dados["evento_id"]}, False)

        cursor = conexao.execute(
            """INSERT INTO eventos_dispositivo
            (evento_id, dispositivo_id, baia, uid_rfid, tipo_evento, valor)
            VALUES (?, ?, ?, ?, ?, ?)""",
            (dados["evento_id"], dados["dispositivo_id"], dados.get("baia"),
             dados.get("uid_rfid"), dados["tipo_evento"],
             json.dumps(dados.get("valor"), ensure_ascii=False)),
        )
        registrar_auditoria(conexao, "eventos_dispositivo", cursor.lastrowid,
                            "recebido", dados)
        conexao.commit()
        return ({"status": "recebido", "id": cursor.lastrowid, **dados}, True)
    finally:
        conexao.close()


def listar_dispositivos():
    conexao = conectar()
    try:
        linhas = conexao.execute("""
        SELECT dispositivo_id,
               COUNT(*) AS total_eventos,
               MAX(criado_em) AS ultimo_contato
        FROM eventos_dispositivo
        GROUP BY dispositivo_id
        ORDER BY dispositivo_id
        """).fetchall()
        return [dict(l) for l in linhas]
    finally:
        conexao.close()


def listar_eventos_dispositivo(limite=200):
    conexao = conectar()
    try:
        linhas = conexao.execute(
            "SELECT * FROM eventos_dispositivo ORDER BY id DESC LIMIT ?", (limite,)
        ).fetchall()
        return [dict(l) for l in linhas]
    finally:
        conexao.close()


# ---------- Exceções ----------

def listar_excecoes():
    conexao = conectar()
    try:
        linhas = conexao.execute("""
        SELECT e.*, t.op_id AS tarefa_op_id, t.material_id AS tarefa_material_id,
               o.nome AS operador_nome, o.matricula AS operador_matricula,
               op.codigo AS op_codigo
        FROM excecoes e
        LEFT JOIN tarefas t ON t.id = e.tarefa_id
        LEFT JOIN operadores o ON o.id = e.operador_id
        LEFT JOIN ordens_producao op ON op.id = t.op_id
        ORDER BY e.id DESC
        """).fetchall()
        return [dict(l) for l in linhas]
    finally:
        conexao.close()


def criar_excecao(dados):
    conexao = conectar()
    try:
        if dados.get("tarefa_id") and not conexao.execute(
                "SELECT id FROM tarefas WHERE id = ?", (dados["tarefa_id"],)).fetchone():
            raise ValueError("Tarefa inexistente")
        cursor = conexao.execute(
            """INSERT INTO excecoes (tarefa_id, operador_id, motivo, observacao)
               VALUES (?, ?, ?, ?)""",
            (dados.get("tarefa_id"), dados.get("operador_id"),
             dados["motivo"], dados.get("observacao")),
        )
        if dados.get("tarefa_id"):
            conexao.execute(
                "UPDATE tarefas SET status = 'bloqueada' WHERE id = ?",
                (dados["tarefa_id"],),
            )
        registrar_auditoria(conexao, "excecoes", cursor.lastrowid, "abertura", dados)
        conexao.commit()
        return dict(conexao.execute(
            "SELECT * FROM excecoes WHERE id = ?", (cursor.lastrowid,)
        ).fetchone())
    finally:
        conexao.close()


def resolver_excecao(excecao_id, decisao):
    conexao = conectar()
    try:
        conexao.execute(
            "UPDATE excecoes SET status='resolvida', decisao=?, resolvido_em=? WHERE id=?",
            (decisao, agora(), excecao_id),
        )
        registro = conexao.execute(
            "SELECT * FROM excecoes WHERE id = ?", (excecao_id,)
        ).fetchone()
        if registro and registro["tarefa_id"]:
            conexao.execute(
                "UPDATE tarefas SET status='cancelada' WHERE id=? AND status='bloqueada'",
                (registro["tarefa_id"],),
            )
        registrar_auditoria(conexao, "excecoes", excecao_id, "resolucao",
                            {"decisao": decisao})
        conexao.commit()
        return dict(registro) if registro else None
    finally:
        conexao.close()


# ---------- Dashboard ----------

def resumo_dashboard():
    conexao = conectar()
    try:
        total_materiais = conexao.execute("SELECT COUNT(*) AS n FROM materiais").fetchone()["n"]
        operadores_ativos = conexao.execute(
            "SELECT COUNT(*) AS n FROM operadores WHERE ativo=1"
        ).fetchone()["n"]
        def contar_tarefas(status):
            return conexao.execute(
                "SELECT COUNT(*) AS n FROM tarefas WHERE status = ?", (status,)
            ).fetchone()["n"]
        pendentes = contar_tarefas("pendente")
        em_andamento = contar_tarefas("em_andamento")
        concluidas = contar_tarefas("concluida")
        bloqueadas = contar_tarefas("bloqueada")
        movimentacoes_recentes = [dict(l) for l in conexao.execute(
            "SELECT * FROM movimentacoes ORDER BY id DESC LIMIT 10"
        ).fetchall()]
        excecoes_abertas = conexao.execute(
            "SELECT COUNT(*) AS n FROM excecoes WHERE status='aberta'"
        ).fetchone()["n"]
        alertas_estoque = [dict(l) for l in conexao.execute("""
            SELECT m.codigo, COALESCE(SUM(CASE WHEN mv.tipo='entrada' THEN mv.quantidade ELSE 0 END)
                - SUM(CASE WHEN mv.tipo='saida' THEN mv.quantidade ELSE 0 END),0) AS saldo
            FROM materiais m LEFT JOIN movimentacoes mv ON mv.material_id = m.id
            GROUP BY m.id HAVING saldo <= 0
        """).fetchall()]
        eventos = [dict(l) for l in conexao.execute(
            "SELECT * FROM eventos_dispositivo ORDER BY id DESC LIMIT 10"
        ).fetchall()]
        return {
            "materiais_cadastrados": total_materiais,
            "operadores_ativos": operadores_ativos,
            "tarefas_pendentes": pendentes,
            "tarefas_em_andamento": em_andamento,
            "tarefas_concluidas": concluidas,
            "tarefas_bloqueadas": bloqueadas,
            "movimentacoes_recentes": movimentacoes_recentes,
            "excecoes_abertas": excecoes_abertas,
            "alertas_estoque": alertas_estoque,
            "eventos_dispositivos": eventos,
        }
    finally:
        conexao.close()
