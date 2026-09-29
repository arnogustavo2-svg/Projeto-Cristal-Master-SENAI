import base64
import io
import json
import os
import sys
import sqlite3
import tempfile
from pathlib import Path
from unittest.mock import patch
from urllib.error import URLError

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import database as db


def main():
    with tempfile.TemporaryDirectory() as pasta:
        caminho_teste = Path(pasta) / "teste.db"
        caminho_legado = Path(pasta) / "legado.db"
        db.CAMINHO_DO_BANCO = caminho_legado
        conexao_legada = sqlite3.connect(caminho_legado)
        conexao_legada.executescript("""
            CREATE TABLE operadores (
                id INTEGER PRIMARY KEY AUTOINCREMENT, matricula TEXT NOT NULL UNIQUE,
                nome TEXT NOT NULL, ativo INTEGER NOT NULL DEFAULT 1,
                criado_em TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE tarefas (
                id INTEGER PRIMARY KEY AUTOINCREMENT, op_id INTEGER NOT NULL,
                item_id INTEGER NOT NULL, material_id INTEGER NOT NULL,
                operador_id INTEGER, quantidade REAL NOT NULL,
                prioridade INTEGER NOT NULL DEFAULT 3,
                status TEXT NOT NULL DEFAULT 'pendente', lote_recomendado_id INTEGER,
                pallet_id INTEGER, posicao_id INTEGER, quantidade_retirada REAL,
                observacao TEXT, criado_em TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                iniciado_em TEXT, concluido_em TEXT
            );
            CREATE TABLE movimentacoes (
                id INTEGER PRIMARY KEY AUTOINCREMENT, tipo TEXT NOT NULL,
                material_id INTEGER NOT NULL, lote_id INTEGER, pallet_id INTEGER,
                posicao_origem_id INTEGER, posicao_destino_id INTEGER,
                quantidade REAL NOT NULL, operador_id INTEGER, tarefa_id INTEGER,
                op_id INTEGER, observacao TEXT,
                criado_em TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
        """)
        conexao_legada.close()
        db.inicializar_banco()
        conexao_legada = sqlite3.connect(caminho_legado)
        assert "funcao" in {linha[1] for linha in conexao_legada.execute("PRAGMA table_info(operadores)")}
        assert {"papel", "pallet_op_id"}.issubset(
            {linha[1] for linha in conexao_legada.execute("PRAGMA table_info(tarefas)")}
        )
        assert "pallet_op_id" in {linha[1] for linha in conexao_legada.execute("PRAGMA table_info(movimentacoes)")}
        conexao_legada.close()

        db.CAMINHO_DO_BANCO = caminho_teste
        import app as modulo

        db.inicializar_banco()
        cliente = modulo.app.test_client()

        # Telas
        assert cliente.get("/").status_code == 200
        assert cliente.get("/lider").status_code == 200
        assert cliente.get("/lider/materiais").status_code == 200
        assert cliente.get("/lider/estoque").status_code == 200
        assert cliente.get("/lider/operadores").status_code == 200
        pagina_ordens = cliente.get("/lider/ordens")
        assert pagina_ordens.status_code == 200
        assert b"previsualizacao-documento" in pagina_ordens.data
        assert b"previa-imagem-documento" in pagina_ordens.data
        assert b"previa-pdf-documento" in pagina_ordens.data
        assert cliente.get("/lider/tarefas").status_code == 200
        assert cliente.get("/lider/movimentacoes").status_code == 200
        assert cliente.get("/lider/auditoria").status_code == 200
        assert cliente.get("/lider/dispositivos").status_code == 200
        assert cliente.get("/lider/excecoes").status_code == 200
        assert cliente.get("/operador").status_code == 200
        assert cliente.get("/operador/inicio").status_code == 200
        assert cliente.get("/operador/tarefas").status_code == 200
        assert cliente.get("/operador/confirmacao").status_code == 200
        assert cliente.get("/operador/excecao").status_code == 200
        assert cliente.get("/api/health").get_json()["status"] == "ok"
        assert cliente.get("/lider/ordens").status_code == 200

        r = cliente.post("/api/materiais", json={
            "codigo": "MAT-001", "descricao": "Resina", "unidade": "kg",
        })
        assert r.status_code == 201, r.get_json()
        material_referencia_id = r.get_json()["id"]
        r = cliente.post("/api/posicoes", json={"codigo": "POS-A1", "descricao": "Corredor A1"})
        assert r.status_code == 201, r.get_json()
        posicao_referencia_id = r.get_json()["id"]

        # Guardas da interpretação não dependem de Gemini nem acessam rede real.
        assert cliente.post("/api/gemini/interpretar", json={
            "nome_arquivo": "op.pdf", "mime_type": "application/pdf",
            "conteudo_base64": "%%%",
        }).status_code == 422
        with patch.dict(os.environ, {"GEMINI_API_KEY": ""}):
            resposta = cliente.post("/api/gemini/interpretar", json={
                "nome_arquivo": "op.pdf", "mime_type": "application/pdf",
                "conteudo_base64": "Zg==",
            })
            assert resposta.status_code == 503

        arquivo_grande = base64.b64encode(b"x" * (20 * 1024 * 1024 + 1)).decode("ascii")
        resposta = cliente.post("/api/gemini/interpretar", json={
            "nome_arquivo": "grande.pdf", "mime_type": "application/pdf",
            "conteudo_base64": arquivo_grande,
        })
        assert resposta.status_code == 413, resposta.get_json()
        del arquivo_grande

        proposta_gemini = {
            "codigo": None,
            "produto": "Produto interpretado",
            "quantidade_cargas": 2,
            "itens": [
                {
                    "codigo_material": "MAT-INEXISTENTE", "descricao_material": "Peça X",
                    "localizacao": "Z-99", "quantidade_por_carga": 10,
                    "unidade": "kg", "fornecedor": "Fornecedor X",
                    "peso_sacaria": 25, "capacidade_pallet": 500,
                },
                {
                    "codigo_material": " mat-001 ", "descricao_material": "Resina divergente",
                    "localizacao": " pos-a1 ", "quantidade_por_carga": 5,
                    "unidade": "un", "fornecedor": "Fornecedor Y",
                    "peso_sacaria": None, "capacidade_pallet": 500,
                },
            ],
        }
        resposta_gemini = {"candidates": [{"content": {"parts": [{
            "text": json.dumps(proposta_gemini),
        }]}}]}
        conteudo_documento = b"documento de teste privado"
        saldo_antes_interpretacao = db.calcular_saldo(material_id=material_referencia_id)
        ordens_antes_interpretacao = len(db.listar_ordens())
        demandas_antes_interpretacao = len(db.listar_demandas())
        with patch.dict(os.environ, {"GEMINI_API_KEY": "mock-only", "GEMINI_MODEL": "modelo-teste"}), \
                patch("app.urllib.request.urlopen", return_value=io.BytesIO(
                    json.dumps(resposta_gemini).encode("utf-8")
                )) as urlopen_mock:
            resposta = cliente.post("/api/gemini/interpretar", json={
                "nome_arquivo": "op-teste.pdf", "mime_type": "application/pdf",
                "conteudo_base64": base64.b64encode(conteudo_documento).decode("ascii"),
            })
        assert resposta.status_code == 200, resposta.get_json()
        proposta = resposta.get_json()
        assert proposta["revisao_obrigatoria"] is True
        assert proposta["interpretacao"]["produto"] == "Produto interpretado"
        assert "codigo" in proposta["campos_ausentes"]
        assert "itens[2].peso_sacaria" in proposta["campos_ausentes"]
        tipos_alerta = {alerta["tipo"] for alerta in proposta["alertas"]}
        assert {"material_nao_encontrado", "descricao_divergente", "unidade_divergente",
                "localizacao_nao_cadastrada"}.issubset(tipos_alerta)
        assert all(set(alerta) == {"tipo", "campo", "mensagem"} for alerta in proposta["alertas"])
        assert urlopen_mock.call_count == 1
        registros_gemini = [registro for registro in db.listar_auditoria()
                    if registro["entidade"] == "gemini_interpretacao"]
        detalhes_gemini = json.dumps(registros_gemini, ensure_ascii=False)
        assert "op-teste.pdf" in detalhes_gemini
        assert base64.b64encode(conteudo_documento).decode("ascii") not in detalhes_gemini
        assert len(db.listar_ordens()) == ordens_antes_interpretacao
        assert len(db.listar_demandas()) == demandas_antes_interpretacao
        assert db.calcular_saldo(material_id=material_referencia_id) == saldo_antes_interpretacao

        proposta_corrigida = {
            "codigo": "OP-INTERPRETADA", "produto": proposta_gemini["produto"],
            "quantidade_cargas": 2,
            "itens": [{
                "codigo_material": "MAT-001", "descricao_material": "Resina",
                "localizacao": "POS-A1", "quantidade_por_carga": 5,
                "unidade": "kg", "fornecedor": "Fornecedor Y",
                "peso_sacaria": 25, "capacidade_pallet": 500,
            }],
            "interpretacao_id": proposta["interpretacao_id"],
        }
        r = cliente.post("/api/demandas", json=proposta_corrigida)
        assert r.status_code == 201, r.get_json()
        registros_revisao = [registro for registro in db.listar_auditoria()
                             if registro["entidade"] == "demandas" and
                             registro["acao"] == "revisao_manual"]
        assert registros_revisao
        ordem_count_antes_confirmacao = len(db.listar_ordens())
        r = cliente.post(f"/api/demandas/{r.get_json()['id']}/confirmar", json={})
        assert r.status_code == 201, r.get_json()
        assert len(db.listar_ordens()) == ordem_count_antes_confirmacao + 1
        resposta_duplicada = cliente.post(
            f"/api/demandas/{r.get_json()['demanda_id']}/confirmar", json={}
        )
        assert resposta_duplicada.status_code == 409
        assert len(db.listar_ordens()) == ordem_count_antes_confirmacao + 1

        with patch.dict(os.environ, {"GEMINI_API_KEY": "mock-only"}), \
                patch("app.urllib.request.urlopen", return_value=io.BytesIO(
                    json.dumps({"candidates": [{"content": {"parts": [{"text": "not-json"}]}}]}).encode("utf-8")
                )):
            assert cliente.post("/api/gemini/interpretar", json={
                "nome_arquivo": "op.pdf", "mime_type": "application/pdf", "conteudo_base64": "Zg==",
            }).status_code == 502
        with patch.dict(os.environ, {"GEMINI_API_KEY": "mock-only"}), \
                patch("app.urllib.request.urlopen", side_effect=TimeoutError):
            assert cliente.post("/api/gemini/interpretar", json={
                "nome_arquivo": "op.pdf", "mime_type": "application/pdf", "conteudo_base64": "Zg==",
            }).status_code == 502
        with patch.dict(os.environ, {"GEMINI_API_KEY": "mock-only"}), \
                patch("app.urllib.request.urlopen", side_effect=URLError("connection failed")):
            assert cliente.post("/api/gemini/interpretar", json={
                "nome_arquivo": "op.pdf", "mime_type": "application/pdf", "conteudo_base64": "Zg==",
            }).status_code == 502

        # Materiais
        r = cliente.post("/api/materiais", json={"codigo": "MAT-001", "descricao": "Resina", "unidade": "kg"})
        assert r.status_code == 409, r.get_json()
        r = cliente.post("/api/materiais", json={"codigo": "MAT-001", "descricao": "Duplicado", "unidade": "kg"})
        assert r.status_code == 409, r.get_json()
        r = cliente.post("/api/materiais", json={"codigo": "", "descricao": "", "unidade": ""})
        assert r.status_code == 422
        assert cliente.get("/api/materiais").get_json()[0]["codigo"] == "MAT-001"
        material_id = material_referencia_id

        # Ativar/desativar material inexistente -> 404 (bug corrigido)
        assert cliente.post("/api/materiais/9999/desativar").status_code == 404
        assert cliente.post(f"/api/materiais/{material_id}/desativar").status_code == 200
        assert cliente.post(f"/api/materiais/{material_id}/ativar").status_code == 200

        # Operadores
        r = cliente.post("/api/operadores", json={"matricula": "OP-001", "nome": "Operador de teste"})
        assert r.status_code == 201, r.get_json()
        assert cliente.post("/api/operador/identificar", json={"matricula": "OP-001"}).status_code == 200
        assert cliente.post("/api/operador/identificar", json={"matricula": "XX-999"}).status_code == 404

        # Evento de dispositivo e duplicidade (idempotência)
        evento = {"evento_id": "EVT-001", "dispositivo_id": "ESP32-A1", "uid_rfid": "RFID-001",
                  "tipo_evento": "tag_detectada", "valor": True}
        assert cliente.post("/api/dispositivos/eventos", json=evento).status_code == 201
        assert cliente.post("/api/dispositivos/eventos", json=evento).status_code == 200

        # Posições / lotes / pallets
        r = cliente.post("/api/posicoes", json={"codigo": "POS-A1"})
        assert r.status_code == 409, r.get_json()
        posicao_id = posicao_referencia_id
        r = cliente.post("/api/lotes", json={"material_id": material_id, "codigo": "LOTE-001"})
        assert r.status_code == 201, r.get_json()
        lote_id = r.get_json()["id"]
        r = cliente.post("/api/lotes", json={"material_id": 9999, "codigo": "LOTE-X"})
        assert r.status_code == 404, r.get_json()
        r = cliente.post("/api/pallets", json={"lote_id": lote_id, "codigo": "PLT-001", "posicao_id": posicao_id})
        assert r.status_code == 201, r.get_json()
        pallet_id = r.get_json()["id"]

        # Estoque: entrada vinculada ao lote/pallet
        r = cliente.post("/api/movimentacoes/entrada",
                         json={"material_id": material_id, "lote_id": lote_id, "pallet_id": pallet_id,
                               "posicao_id": posicao_id, "quantidade": 100})
        assert r.status_code == 201, r.get_json()
        assert db.calcular_saldo(material_id=material_id) == 100
        assert db.calcular_saldo(pallet_id=pallet_id) == 100

        # Bloqueio de pallet
        assert cliente.post(f"/api/pallets/{pallet_id}/bloquear", json={"bloqueado": True}).status_code == 200
        assert cliente.get("/api/estoque").get_json()["itens_bloqueados"][0]["codigo"] == "PLT-001"

        # OP + tarefas
        r = cliente.post("/api/ordens", json={
            "codigo": "OP-100", "produto": "Produto A", "prioridade": 2,
            "itens": [{"material_id": material_id, "quantidade": 10}],
        })
        assert r.status_code == 201, r.get_json()
        op_id = r.get_json()["id"]
        assert cliente.get(f"/lider/ordens/{op_id}").status_code == 200
        assert cliente.get("/lider/ordens/999999").status_code == 404
        r = cliente.post(f"/api/ordens/{op_id}/gerar-tarefas", json={})
        assert r.status_code == 201, r.get_json()
        tarefas = cliente.get(f"/api/tarefas?op_id={op_id}").get_json()
        assert len(tarefas) == 1
        tarefa_id = tarefas[0]["id"]
        assert cliente.get(f"/operador/tarefas/{tarefa_id}").status_code == 200

        # Execução: tentar concluir com pallet bloqueado deve falhar
        assert cliente.post(f"/api/operador/tarefas/{tarefa_id}/iniciar",
                            json={"matricula": "OP-001"}).status_code == 200
        r = cliente.post(f"/api/operador/tarefas/{tarefa_id}/concluir",
                         json={"matricula": "OP-001", "quantidade_retirada": 5, "pallet_id": pallet_id})
        assert r.status_code == 409, r.get_json()  # pallet bloqueado -> corretamente rejeitado

        # Desbloqueia e conclui de fato
        assert cliente.post(f"/api/pallets/{pallet_id}/desbloquear").status_code == 200
        r = cliente.post(f"/api/operador/tarefas/{tarefa_id}/concluir",
                         json={"matricula": "OP-001", "quantidade_retirada": 10, "pallet_id": pallet_id})
        assert r.status_code == 200, r.get_json()
        assert db.calcular_saldo(material_id=material_id) == 90
        assert db.calcular_saldo(pallet_id=pallet_id) == 90

        # OP deve estar finalizada automaticamente (única tarefa concluída)
        assert cliente.get(f"/api/ordens/{op_id}").get_json()["status"] == "finalizada"

        # Saldo insuficiente deve ser rejeitado (bug do cálculo de saldo corrigido)
        r2 = cliente.post("/api/ordens", json={
            "codigo": "OP-101", "produto": "Produto B", "prioridade": 1,
            "itens": [{"material_id": material_id, "quantidade": 500}],
        })
        op2_id = r2.get_json()["id"]
        cliente.post(f"/api/ordens/{op2_id}/gerar-tarefas", json={})
        tarefa2_id = [t for t in cliente.get("/api/tarefas").get_json() if t["op_id"] == op2_id][0]["id"]
        cliente.post(f"/api/operador/tarefas/{tarefa2_id}/iniciar", json={"matricula": "OP-001"})
        r = cliente.post(f"/api/operador/tarefas/{tarefa2_id}/concluir",
                         json={"matricula": "OP-001", "quantidade_retirada": 500, "pallet_id": pallet_id})
        assert r.status_code == 409, r.get_json()  # saldo insuficiente

        # Demanda: rascunho revisável, fórmula de embalagem e confirmação gera OP/tarefas
        payload_demanda = {
            "codigo": "DEM-100", "produto": "Produto com demanda", "quantidade_cargas": 3,
            "itens": [{
                "codigo_material": "MAT-001", "descricao_material": "Resina",
                "localizacao": "A-01", "quantidade_por_carga": 375, "unidade": "kg",
                "fornecedor": "Fornecedor A", "peso_sacaria": 25,
                "capacidade_pallet": 500,
            }],
        }
        r = cliente.post("/api/demandas", json=payload_demanda)
        assert r.status_code == 201, r.get_json()
        demanda_id = r.get_json()["id"]
        item_demanda = r.get_json()["itens"][0]
        assert item_demanda["quantidade_total"] == 1125
        assert item_demanda["sacarias_fechadas"] == 45
        assert item_demanda["quantidade_em_pesagem"] == 0
        assert r.get_json()["status"] == "rascunho"

        # A revisão pode ajustar a quantidade antes da confirmação da OP.
        payload_demanda["quantidade_cargas"] = 2
        payload_demanda["itens"][0]["quantidade_por_carga"] = 500
        r = cliente.put(f"/api/demandas/{demanda_id}", json=payload_demanda)
        assert r.status_code == 200, r.get_json()
        assert r.get_json()["itens"][0]["quantidade_total"] == 1000
        assert r.get_json()["itens"][0]["sacarias_fechadas"] == 40

        r = cliente.post("/api/lotes", json={"material_id": material_id, "codigo": "LOTE-002"})
        assert r.status_code == 201, r.get_json()
        lote_demanda_id = r.get_json()["id"]
        assert cliente.post("/api/movimentacoes/entrada", json={
            "material_id": material_id, "lote_id": lote_demanda_id, "quantidade": 1000,
        }).status_code == 201

        r = cliente.post(f"/api/demandas/{demanda_id}/confirmar", json={})
        assert r.status_code == 201, r.get_json()
        demanda_op_id = r.get_json()["ordem"]["id"]
        tarefas_demanda = cliente.get(f"/api/tarefas?op_id={demanda_op_id}").get_json()
        assert len(tarefas_demanda) == 1
        assert tarefas_demanda[0]["papel"] == "separador"
        pallets_op = cliente.get(f"/api/pallets-op?op_id={demanda_op_id}").get_json()
        assert len(pallets_op) == 2
        assert all(p["status"] == "previsto" and p["quantidade_total"] == 500 for p in pallets_op)

        tarefa_separador_id = tarefas_demanda[0]["id"]
        assert cliente.post(f"/api/operador/tarefas/{tarefa_separador_id}/iniciar",
                            json={"matricula": "OP-001"}).status_code == 200
        for pallet_op in pallets_op:
            r = cliente.post(f"/api/pallets-op/{pallet_op['id']}/fechar", json={
                "matricula": "OP-001", "sacarias": 20, "quantidade_pesagem": 0,
            })
            assert r.status_code == 200, r.get_json()
            assert r.get_json()["status"] == "fechado"

        tarefas_demanda = cliente.get(f"/api/tarefas?op_id={demanda_op_id}").get_json()
        tarefas_empilhadeira = [t for t in tarefas_demanda if t["papel"] == "empilhadeira"]
        assert len(tarefas_empilhadeira) == 2
        assert cliente.post(f"/api/operador/tarefas/{tarefas_empilhadeira[0]['id']}/iniciar",
                            json={"matricula": "OP-001"}).status_code == 409
        r = cliente.post("/api/operadores", json={
            "matricula": "FORK-001", "nome": "Operador de empilhadeira", "funcao": "empilhadeira",
        })
        assert r.status_code == 201, r.get_json()
        for tarefa in tarefas_empilhadeira:
            assert cliente.post(f"/api/operador/tarefas/{tarefa['id']}/iniciar",
                                json={"matricula": "FORK-001"}).status_code == 200

        r = cliente.post(f"/api/operador/tarefas/{tarefa_separador_id}/concluir", json={
            "matricula": "OP-001", "quantidade_retirada": 1000,
        })
        assert r.status_code == 200, r.get_json()
        for tarefa in tarefas_empilhadeira:
            r = cliente.post(f"/api/operador/tarefas/{tarefa['id']}/movimentar", json={
                "matricula": "FORK-001", "posicao_destino_id": posicao_id,
            })
            assert r.status_code == 200, r.get_json()
        transferencias = [m for m in cliente.get("/api/movimentacoes").get_json()
                          if m["tipo"] == "transferencia"]
        assert len(transferencias) == 2
        assert {m["pallet_op_id"] for m in transferencias} == {p["id"] for p in pallets_op}
        assert all(m["posicao_destino_id"] == posicao_id for m in transferencias)
        assert cliente.get(f"/api/ordens/{demanda_op_id}").get_json()["status"] == "finalizada"
        assert len([p for p in cliente.get(f"/api/pallets-op?op_id={demanda_op_id}").get_json()
                    if p["status"] == "movimentado"]) == 2

        r = cliente.post("/api/demandas", json={
            "codigo": "DEM-102", "produto": "Produto parcial", "quantidade_cargas": 3,
            "itens": [{
                "codigo_material": "MAT-001", "descricao_material": "Resina",
                "localizacao": "A-01", "quantidade_por_carga": 375, "unidade": "kg",
                "fornecedor": "Fornecedor A", "peso_sacaria": 25,
                "capacidade_pallet": 500,
            }],
        })
        assert r.status_code == 201, r.get_json()
        demanda_parcial_id = r.get_json()["id"]
        assert cliente.post(f"/api/demandas/{demanda_parcial_id}/confirmar", json={}).status_code == 201
        op_parcial_id = cliente.get(f"/api/demandas/{demanda_parcial_id}").get_json()["op_id"]
        pallets_parciais = cliente.get(f"/api/pallets-op?op_id={op_parcial_id}").get_json()
        assert [p["quantidade_total"] for p in pallets_parciais] == [500, 500, 125]
        assert [p["status"] for p in pallets_parciais] == ["previsto", "previsto", "em_montagem"]
        tarefas_parciais = cliente.get(f"/api/tarefas?op_id={op_parcial_id}").get_json()
        assert len(tarefas_parciais) == 1
        assert tarefas_parciais[0]["papel"] == "separador"
        tarefa_parcial_id = tarefas_parciais[0]["id"]
        assert cliente.post(f"/api/operador/tarefas/{tarefa_parcial_id}/iniciar",
                            json={"matricula": "OP-001"}).status_code == 200
        r = cliente.post(f"/api/operador/tarefas/{tarefa_parcial_id}/concluir", json={
            "matricula": "OP-001", "quantidade_retirada": 1125,
        })
        assert r.status_code == 409, r.get_json()

        # Ajustes físicos são append-only e atualizam o saldo sem apagar movimentos.
        saldo_antes_ajuste = db.calcular_saldo(material_id=material_id)
        saldo_pallet_antes_ajuste = db.calcular_saldo(pallet_id=pallet_id)
        r = cliente.post("/api/ajustes-estoque", json={
            "material_id": material_id, "quantidade_ajuste": -5,
            "tipo": "falta_fisica", "motivo": "Contagem física",
            "responsavel": "Líder de teste",
        })
        assert r.status_code == 201, r.get_json()
        assert r.get_json()["quantidade_antes"] == saldo_antes_ajuste
        assert r.get_json()["quantidade_depois"] == saldo_antes_ajuste - 5
        assert db.calcular_saldo(material_id=material_id) == saldo_antes_ajuste - 5
        assert cliente.get("/api/ajustes-estoque").get_json()[0]["tipo"] == "falta_fisica"

        r = cliente.post("/api/posicoes", json={"codigo": "POS-B1"})
        assert r.status_code == 201, r.get_json()
        posicao_correta_id = r.get_json()["id"]
        r = cliente.post("/api/ajustes-estoque", json={
            "material_id": material_id, "lote_id": lote_demanda_id,
            "pallet_id": pallet_id, "tipo": "lote_incorreto",
            "quantidade_ajuste": 0, "motivo": "Conferência do lote",
            "responsavel": "Líder de teste",
        })
        assert r.status_code == 201, r.get_json()
        assert r.get_json()["lote_anterior_id"] == lote_id
        assert r.get_json()["lote_id"] == lote_demanda_id
        assert db.calcular_saldo(pallet_id=pallet_id) == saldo_pallet_antes_ajuste
        r = cliente.post("/api/ajustes-estoque", json={
            "material_id": material_id, "lote_id": lote_demanda_id,
            "pallet_id": pallet_id, "posicao_anterior_id": posicao_id,
            "posicao_id": posicao_correta_id, "tipo": "posicao_incorreta",
            "quantidade_ajuste": 0, "motivo": "Correção de endereço",
            "responsavel": "Líder de teste",
        })
        assert r.status_code == 201, r.get_json()
        pallet_fisico = next(p for p in db.listar_pallets() if p["id"] == pallet_id)
        assert pallet_fisico["posicao_id"] == posicao_correta_id
        assert db.calcular_saldo(pallet_id=pallet_id) == saldo_pallet_antes_ajuste

        # Exceção
        r = cliente.post("/api/excecoes", json={
            "matricula": "OP-001", "motivo": "pallet_nao_encontrado",
            "observacao": "Teste",
        })
        assert r.status_code == 201, r.get_json()
        excecao_id = r.get_json()["id"]
        assert cliente.post(f"/api/excecoes/{excecao_id}/resolver", json={"decisao": "Resolvido em teste"}).status_code == 200

        # Auditoria e dashboard usam dados reais
        assert len(cliente.get("/api/auditoria").get_json()) > 0
        d = cliente.get("/api/dashboard").get_json()
        assert d["materiais_cadastrados"] == 1
        assert d["tarefas_concluidas"] >= 2
        assert d["excecoes_abertas"] == 0

        # Persistência após reabrir conexão (simula reinício)
        assert db.buscar_material(material_id)["codigo"] == "MAT-001"

    print("SMOKE TEST PASS")


if __name__ == "__main__":
    main()
