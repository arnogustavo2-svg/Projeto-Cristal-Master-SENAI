import base64
import json
import os
import urllib.error
import urllib.request

from flask import Flask, jsonify, render_template, request
from werkzeug.exceptions import HTTPException
from pydantic import ValidationError

import database as db
from schemas import (
    AjusteEstoqueCreate,
    DemandaCreate,
    DemandaInterpretada,
    DeviceEventCreate,
    EntradaEstoque,
    ExcecaoCreate,
    ExcecaoResolucao,
    GerarTarefasInput,
    FechamentoPallet,
    GeminiFileInput,
    LoteCreate,
    MaterialCreate,
    MaterialUpdate,
    MovimentarPallet,
    OperadorCreate,
    OperadorUpdate,
    OrdemProducaoCreate,
    OperatorLookup,
    PalletBloqueio,
    PalletCreate,
    PosicaoCreate,
    TarefaConclusao,
    TarefaInicio,
)


def _carregar_env_local():
    caminho = os.path.join(os.path.dirname(__file__), ".env")
    if not os.path.isfile(caminho):
        return
    with open(caminho, encoding="utf-8-sig") as arquivo:
        for linha in arquivo:
            texto = linha.strip()
            if not texto or texto.startswith("#") or "=" not in texto:
                continue
            nome, valor = texto.split("=", 1)
            nome = nome.strip()
            valor = valor.strip().strip("\"'")
            if nome and nome not in os.environ:
                os.environ[nome] = valor


_carregar_env_local()
app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 30 * 1024 * 1024
db.inicializar_banco()


# ------------------------------------------------------------ HTML

@app.get("/")
def inicio():
    return render_template("index.html")


@app.get("/lider")
def lider_dashboard():
    return render_template("lider/dashboard.html")


@app.get("/lider/materiais")
def lider_materiais():
    return render_template("lider/materiais.html")


@app.get("/lider/estoque")
def lider_estoque():
    return render_template("lider/estoque.html")


@app.get("/lider/operadores")
def lider_operadores():
    return render_template("lider/operadores.html")


@app.get("/lider/ordens")
def lider_ordens():
    return render_template("lider/ordens.html")


@app.get("/lider/ordens/<int:op_id>")
def lider_ordem_detalhes(op_id):
    ordem = db.buscar_ordem(op_id)
    if not ordem:
        return render_template("lider/ordem-detalhes.html", ordem=None), 404
    return render_template("lider/ordem-detalhes.html", ordem=ordem)


@app.get("/lider/tarefas")
def lider_tarefas():
    return render_template("lider/tarefas.html")


@app.get("/lider/movimentacoes")
def lider_movimentacoes():
    return render_template("lider/movimentacoes.html")


@app.get("/lider/auditoria")
def lider_auditoria():
    return render_template("lider/auditoria.html")


@app.get("/lider/dispositivos")
def lider_dispositivos():
    return render_template("lider/dispositivos.html")


@app.get("/lider/excecoes")
def lider_excecoes():
    return render_template("lider/excecoes.html")


@app.get("/operador")
def operador_acesso():
    return render_template("operador/acesso.html")


@app.get("/operador/inicio")
def operador_inicio():
    return render_template("operador/inicio.html")


@app.get("/operador/tarefas")
def operador_tarefas():
    return render_template("operador/tarefas.html")


@app.get("/operador/tarefas/<int:tarefa_id>")
def operador_tarefa_detalhes(tarefa_id):
    tarefa = db.buscar_tarefa(tarefa_id)
    return render_template("operador/tarefa-detalhes.html", tarefa=tarefa)


@app.get("/operador/confirmacao")
def operador_confirmacao():
    return render_template("operador/confirmacao.html")


@app.get("/operador/excecao")
def operador_excecao():
    return render_template("operador/excecao.html")


# ------------------------------------------------------------ Helpers

def _json():
    return request.get_json(silent=True) or {}


def _erro_validacao(erro):
    return jsonify({"erro": "Dados inválidos", "detalhes": erro.errors()}), 422


def _erro_valor(erro, codigo_padrao=409):
    """Traduz ValueError de database.py em código HTTP:
    referência inexistente -> 404; qualquer outro conflito -> codigo_padrao."""
    msg = str(erro)
    if "inexistente" in msg.lower() or "não encontrad" in msg.lower():
        return jsonify({"erro": msg}), 404
    return jsonify({"erro": msg}), codigo_padrao


def _registrar_auditoria_segura(entidade, acao, detalhes):
    conexao = db.conectar()
    try:
        db.registrar_auditoria(conexao, entidade, None, acao, detalhes)
        auditoria_id = conexao.execute("SELECT last_insert_rowid() AS id").fetchone()["id"]
        conexao.commit()
        return auditoria_id
    finally:
        conexao.close()


def _normalizar_comparacao(valor):
    return " ".join(str(valor or "").strip().casefold().split())


def _validar_proposta_cadastros(interpretacao):
    campos_ausentes = []
    alertas = []

    for campo in ("codigo", "produto", "quantidade_cargas"):
        valor = getattr(interpretacao, campo)
        if valor is None or (isinstance(valor, str) and not valor.strip()):
            campos_ausentes.append(campo)

    materiais = db.listar_materiais()
    posicoes = db.listar_posicoes()
    campos_item = (
        ("codigo_material", "codigo_material"),
        ("descricao_material", "descricao_material"),
        ("localizacao", "localizacao"),
        ("quantidade_por_carga", "quantidade_por_carga"),
        ("unidade", "unidade"),
        ("fornecedor", "fornecedor"),
        ("peso_sacaria", "peso_sacaria"),
        ("capacidade_pallet", "capacidade_pallet"),
    )
    for indice, item in enumerate(interpretacao.itens, 1):
        prefixo = f"itens[{indice}]"
        for atributo, nome_campo in campos_item:
            valor = getattr(item, atributo)
            if valor is None or (isinstance(valor, str) and not valor.strip()):
                campos_ausentes.append(f"{prefixo}.{nome_campo}")

        codigo = _normalizar_comparacao(item.codigo_material)
        if codigo:
            material = next((registro for registro in materiais
                             if _normalizar_comparacao(registro.get("codigo")) == codigo), None)
            if not material:
                alertas.append({
                    "tipo": "material_nao_encontrado",
                    "campo": f"{prefixo}.codigo_material",
                    "mensagem": f"Material {item.codigo_material.strip()} não encontrado no cadastro.",
                })
            else:
                if (item.descricao_material and
                        _normalizar_comparacao(item.descricao_material) !=
                        _normalizar_comparacao(material.get("descricao"))):
                    alertas.append({
                        "tipo": "descricao_divergente",
                        "campo": f"{prefixo}.descricao_material",
                        "mensagem": f"Descrição do material {item.codigo_material.strip()} diverge do cadastro.",
                    })
                if (item.unidade and
                        _normalizar_comparacao(item.unidade) !=
                        _normalizar_comparacao(material.get("unidade"))):
                    alertas.append({
                        "tipo": "unidade_divergente",
                        "campo": f"{prefixo}.unidade",
                        "mensagem": f"Unidade do material {item.codigo_material.strip()} diverge do cadastro.",
                    })

        localizacao = _normalizar_comparacao(item.localizacao)
        if localizacao and not any(
            localizacao in {
                _normalizar_comparacao(registro.get("codigo")),
                _normalizar_comparacao(registro.get("descricao")),
            }
            for registro in posicoes
        ):
            alertas.append({
                "tipo": "localizacao_nao_cadastrada",
                "campo": f"{prefixo}.localizacao",
                "mensagem": f"Localização {item.localizacao.strip()} não encontrada no cadastro.",
            })
    return campos_ausentes, alertas


# ------------------------------------------------------------ API - health

@app.get("/api/health")
def health():
    return jsonify({"status": "ok", "service": "aai"})


# ------------------------------------------------------------ API - materiais

@app.get("/api/materiais")
def api_listar_materiais():
    return jsonify(db.listar_materiais())


@app.post("/api/materiais")
def api_criar_material():
    try:
        dados = MaterialCreate.model_validate(_json())
        return jsonify(db.criar_material(dados.model_dump())), 201
    except ValidationError as erro:
        return _erro_validacao(erro)
    except ValueError as erro:
        return jsonify({"erro": str(erro)}), 409


@app.put("/api/materiais/<int:material_id>")
def api_atualizar_material(material_id):
    if not db.buscar_material(material_id):
        return jsonify({"erro": "Material inexistente"}), 404
    try:
        dados = MaterialUpdate.model_validate(_json())
        return jsonify(db.atualizar_material(material_id, dados.model_dump()))
    except ValidationError as erro:
        return _erro_validacao(erro)


@app.post("/api/materiais/<int:material_id>/ativar")
def api_ativar_material(material_id):
    if not db.buscar_material(material_id):
        return jsonify({"erro": "Material inexistente"}), 404
    return jsonify(db.atualizar_material(material_id, {"ativo": True}))


@app.post("/api/materiais/<int:material_id>/desativar")
def api_desativar_material(material_id):
    if not db.buscar_material(material_id):
        return jsonify({"erro": "Material inexistente"}), 404
    return jsonify(db.atualizar_material(material_id, {"ativo": False}))


# ------------------------------------------------------------ API - operadores

@app.get("/api/operadores")
def api_listar_operadores():
    return jsonify(db.listar_operadores())


@app.post("/api/operadores")
def api_criar_operador():
    try:
        dados = OperadorCreate.model_validate(_json())
        return jsonify(db.criar_operador(dados.matricula, dados.nome, dados.funcao)), 201
    except ValidationError as erro:
        return _erro_validacao(erro)
    except ValueError as erro:
        return jsonify({"erro": str(erro)}), 409


@app.put("/api/operadores/<int:operador_id>")
def api_atualizar_operador(operador_id):
    try:
        dados = OperadorUpdate.model_validate(_json())
        resultado = db.atualizar_operador(operador_id, dados.model_dump(exclude_unset=True))
        if not resultado:
            return jsonify({"erro": "Operador inexistente"}), 404
        return jsonify(resultado)
    except ValidationError as erro:
        return _erro_validacao(erro)


@app.post("/api/operador/identificar")
def api_identificar_operador():
    try:
        dados = OperatorLookup.model_validate(_json())
        operador = db.buscar_operador(dados.matricula.strip())
        if operador is None:
            return jsonify({"erro": "Matrícula não encontrada"}), 404
        if not operador["ativo"]:
            return jsonify({"erro": "Operador inativo"}), 403
        return jsonify({"status": "autorizado", "operador": operador})
    except ValidationError as erro:
        return _erro_validacao(erro)


# ------------------------------------------------------------ API - posições, lotes, pallets

@app.get("/api/posicoes")
def api_listar_posicoes():
    return jsonify(db.listar_posicoes())


@app.post("/api/posicoes")
def api_criar_posicao():
    try:
        dados = PosicaoCreate.model_validate(_json())
        return jsonify(db.criar_posicao(dados.codigo, dados.descricao)), 201
    except ValidationError as erro:
        return _erro_validacao(erro)
    except ValueError as erro:
        return jsonify({"erro": str(erro)}), 409


@app.get("/api/lotes")
def api_listar_lotes():
    material_id = request.args.get("material_id", type=int)
    return jsonify(db.listar_lotes(material_id))


@app.post("/api/lotes")
def api_criar_lote():
    try:
        dados = LoteCreate.model_validate(_json())
        validade = dados.validade.isoformat() if dados.validade else None
        return jsonify(db.criar_lote(dados.material_id, dados.codigo, validade)), 201
    except ValidationError as erro:
        return _erro_validacao(erro)
    except ValueError as erro:
        return _erro_valor(erro)


@app.get("/api/pallets")
def api_listar_pallets():
    return jsonify(db.listar_pallets())


@app.post("/api/pallets")
def api_criar_pallet():
    try:
        dados = PalletCreate.model_validate(_json())
        return jsonify(db.criar_pallet(dados.lote_id, dados.codigo, dados.posicao_id)), 201
    except ValidationError as erro:
        return _erro_validacao(erro)
    except ValueError as erro:
        return _erro_valor(erro)


@app.post("/api/pallets/<int:pallet_id>/bloquear")
def api_bloquear_pallet(pallet_id):
    try:
        PalletBloqueio.model_validate(_json() or {"bloqueado": True})
    except ValidationError as erro:
        return _erro_validacao(erro)
    resultado = db.definir_bloqueio_pallet(pallet_id, True)
    if resultado is None:
        return jsonify({"erro": "Pallet não encontrado"}), 404
    return jsonify(resultado)


@app.post("/api/pallets/<int:pallet_id>/desbloquear")
def api_desbloquear_pallet(pallet_id):
    resultado = db.definir_bloqueio_pallet(pallet_id, False)
    if resultado is None:
        return jsonify({"erro": "Pallet não encontrado"}), 404
    return jsonify(resultado)


# ------------------------------------------------------------ API - estoque

@app.get("/api/estoque")
def api_estoque():
    return jsonify({
        "por_material": db.estoque_por_material(),
        "por_lote": db.estoque_por_lote(),
        "pallets": db.listar_pallets(),
        "posicoes": db.listar_posicoes(),
        "itens_bloqueados": db.itens_bloqueados(),
        "movimentacoes": db.listar_movimentacoes(200),
        "ajustes": db.listar_ajustes_estoque(200),
    })


@app.post("/api/movimentacoes/entrada")
def api_movimentacao_entrada():
    try:
        dados = EntradaEstoque.model_validate(_json())
        return jsonify(db.registrar_entrada(dados.model_dump())), 201
    except ValidationError as erro:
        return _erro_validacao(erro)
    except ValueError as erro:
        return _erro_valor(erro)


@app.get("/api/movimentacoes")
def api_movimentacoes():
    return jsonify(db.listar_movimentacoes())


@app.get("/api/ajustes-estoque")
def api_listar_ajustes_estoque():
    return jsonify(db.listar_ajustes_estoque())


@app.post("/api/ajustes-estoque")
def api_criar_ajuste_estoque():
    try:
        dados = AjusteEstoqueCreate.model_validate(_json())
        return jsonify(db.registrar_ajuste_estoque(dados.model_dump())), 201
    except ValidationError as erro:
        return _erro_validacao(erro)
    except ValueError as erro:
        return _erro_valor(erro)


# ------------------------------------------------------------ API - demandas

@app.get("/api/demandas")
def api_listar_demandas():
    return jsonify(db.listar_demandas())


@app.post("/api/demandas")
def api_criar_demanda():
    try:
        entrada = _json()
        dados = DemandaCreate.model_validate(entrada)
        demanda = db.criar_demanda(dados.model_dump())
        interpretacao_id = entrada.get("interpretacao_id")
        if isinstance(interpretacao_id, int):
            conexao = db.conectar()
            try:
                origem_valida = conexao.execute(
                    "SELECT id FROM auditoria WHERE id=? AND entidade='gemini_interpretacao' "
                    "AND acao='concluida'",
                    (interpretacao_id,),
                ).fetchone()
            finally:
                conexao.close()
            if origem_valida:
                _registrar_auditoria_segura("demandas", "revisao_manual", {
                    "demanda_id": demanda["id"],
                    "interpretacao_id": interpretacao_id,
                })
        return jsonify(demanda), 201
    except ValidationError as erro:
        return _erro_validacao(erro)
    except ValueError as erro:
        return _erro_valor(erro)


@app.get("/api/demandas/<int:demanda_id>")
def api_detalhe_demanda(demanda_id):
    demanda = db.buscar_demanda(demanda_id)
    if not demanda:
        return jsonify({"erro": "Demanda não encontrada"}), 404
    return jsonify(demanda)


@app.put("/api/demandas/<int:demanda_id>")
def api_atualizar_demanda(demanda_id):
    try:
        dados = DemandaCreate.model_validate(_json())
        demanda = db.atualizar_demanda(demanda_id, dados.model_dump())
        if not demanda:
            return jsonify({"erro": "Demanda não encontrada"}), 404
        return jsonify(demanda)
    except ValidationError as erro:
        return _erro_validacao(erro)
    except ValueError as erro:
        return _erro_valor(erro)


@app.post("/api/demandas/<int:demanda_id>/confirmar")
def api_confirmar_demanda(demanda_id):
    try:
        ordem = db.confirmar_demanda(demanda_id)
        return jsonify({"demanda_id": demanda_id, "ordem": ordem}), 201
    except ValueError as erro:
        return _erro_valor(erro)


@app.post("/api/gemini/interpretar")
def api_interpretar_documento_demanda():
    try:
        arquivo = GeminiFileInput.model_validate(_json())
        conteudo = base64.b64decode(arquivo.conteudo_base64, validate=True)
    except ValidationError as erro:
        return _erro_validacao(erro)
    except ValueError:
        return jsonify({"erro": "Arquivo em base64 inválido"}), 422
    if len(conteudo) > 20 * 1024 * 1024:
        return jsonify({"erro": "Arquivo excede o limite de 20 MB"}), 413
    modelo = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash").strip()
    metadados = {
        "nome_arquivo": arquivo.nome_arquivo,
        "mime_type": arquivo.mime_type,
        "tamanho_bytes": len(conteudo),
        "modelo": modelo,
    }
    _registrar_auditoria_segura("gemini_interpretacao", "solicitada", metadados)
    chave = os.environ.get("GEMINI_API_KEY", "").strip()
    if not chave:
        _registrar_auditoria_segura("gemini_interpretacao", "rejeitada", {
            **metadados, "motivo": "chave_ausente",
        })
        return jsonify({"erro": "GEMINI_API_KEY não configurada"}), 503

    esquema = {
        "type": "OBJECT",
        "properties": {
            "codigo": {"type": "STRING", "nullable": True},
            "produto": {"type": "STRING", "nullable": True},
            "quantidade_cargas": {"type": "INTEGER", "nullable": True},
            "observacao": {"type": "STRING", "nullable": True},
            "itens": {"type": "ARRAY", "items": {"type": "OBJECT", "properties": {
                "codigo_material": {"type": "STRING", "nullable": True},
                "descricao_material": {"type": "STRING", "nullable": True},
                "localizacao": {"type": "STRING", "nullable": True},
                "quantidade_por_carga": {"type": "NUMBER", "nullable": True},
                "unidade": {"type": "STRING", "nullable": True},
                "fornecedor": {"type": "STRING", "nullable": True},
                "peso_sacaria": {"type": "NUMBER", "nullable": True},
                "capacidade_pallet": {"type": "NUMBER", "nullable": True},
                "observacao": {"type": "STRING", "nullable": True},
            }}},
        },
    }
    payload = {
        "contents": [{"parts": [
            {"text": "Extraia da foto/PDF apenas os dados legíveis de uma ordem de produção. "
                     "Não estime nem invente campos; use null quando ausente. Retorne somente o JSON pedido."},
            {"inlineData": {"mimeType": arquivo.mime_type,
                            "data": arquivo.conteudo_base64}},
        ]}],
        "generationConfig": {"responseMimeType": "application/json", "responseSchema": esquema},
    }
    requisicao = urllib.request.Request(
        f"https://generativelanguage.googleapis.com/v1beta/models/{modelo}:generateContent",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", "x-goog-api-key": chave},
        method="POST",
    )
    try:
        with urllib.request.urlopen(requisicao, timeout=45) as resposta:
            resposta_api = json.loads(resposta.read().decode("utf-8"))
        texto = resposta_api["candidates"][0]["content"]["parts"][0]["text"]
        interpretacao = DemandaInterpretada.model_validate(json.loads(texto))
        campos_ausentes, alertas = _validar_proposta_cadastros(interpretacao)
        interpretacao_id = _registrar_auditoria_segura(
            "gemini_interpretacao", "concluida", {
                **metadados,
                "quantidade_campos_ausentes": len(campos_ausentes),
                "quantidade_alertas": len(alertas),
            },
        )
        return jsonify({
            "interpretacao": interpretacao.model_dump(),
            "revisao_obrigatoria": True,
            "campos_ausentes": campos_ausentes,
            "alertas": alertas,
            "interpretacao_id": interpretacao_id,
        })
    except urllib.error.HTTPError as erro:
        _registrar_auditoria_segura("gemini_interpretacao", "rejeitada", {
            **metadados, "motivo": "erro_http", "codigo_http": erro.code,
        })
        return jsonify({"erro": f"Gemini recusou a interpretação (HTTP {erro.code})"}), 502
    except (urllib.error.URLError, TimeoutError, OSError):
        _registrar_auditoria_segura("gemini_interpretacao", "rejeitada", {
            **metadados, "motivo": "falha_conexao_ou_timeout",
        })
        return jsonify({"erro": "Não foi possível conectar ao serviço de interpretação"}), 502
    except (KeyError, IndexError, TypeError, ValueError, ValidationError):
        _registrar_auditoria_segura("gemini_interpretacao", "rejeitada", {
            **metadados, "motivo": "resposta_invalida",
        })
        return jsonify({"erro": "Resposta estruturada do Gemini inválida"}), 502


# ------------------------------------------------------------ API - ordens

@app.get("/api/ordens")
def api_listar_ordens():
    return jsonify(db.listar_ordens())


@app.post("/api/ordens")
def api_criar_ordem():
    try:
        dados = OrdemProducaoCreate.model_validate(_json())
        payload = dados.model_dump()
        payload["prazo"] = dados.prazo.isoformat() if dados.prazo else None
        return jsonify(db.criar_ordem(payload)), 201
    except ValidationError as erro:
        return _erro_validacao(erro)
    except ValueError as erro:
        return _erro_valor(erro)


@app.get("/api/pallets-op")
def api_listar_pallets_op():
    op_id = request.args.get("op_id", type=int)
    return jsonify(db.listar_pallets_op(op_id))


@app.post("/api/pallets-op/<int:pallet_op_id>/fechar")
def api_fechar_pallet_op(pallet_op_id):
    try:
        dados = FechamentoPallet.model_validate(_json())
        operador = db.buscar_operador(dados.matricula.strip())
        if not operador:
            return jsonify({"erro": "Matrícula não encontrada"}), 404
        if not operador["ativo"]:
            return jsonify({"erro": "Operador inativo"}), 403
        resultado = db.fechar_pallet_op(
            pallet_op_id, operador["id"], dados.sacarias,
            dados.quantidade_pesagem, dados.posicao_id,
        )
        return jsonify(resultado)
    except ValidationError as erro:
        return _erro_validacao(erro)
    except ValueError as erro:
        return _erro_valor(erro)


@app.post("/api/pallets-op/<int:pallet_op_id>/bloquear")
def api_bloquear_pallet_op(pallet_op_id):
    resultado = db.definir_bloqueio_pallet_op(pallet_op_id, True)
    if not resultado:
        return jsonify({"erro": "Pallet da OP não encontrado"}), 404
    return jsonify(resultado)


@app.post("/api/pallets-op/<int:pallet_op_id>/desbloquear")
def api_desbloquear_pallet_op(pallet_op_id):
    resultado = db.definir_bloqueio_pallet_op(pallet_op_id, False)
    if not resultado:
        return jsonify({"erro": "Pallet da OP não encontrado"}), 404
    return jsonify(resultado)


@app.get("/api/ordens/<int:op_id>")
def api_detalhe_ordem(op_id):
    ordem = db.buscar_ordem(op_id)
    if not ordem:
        return jsonify({"erro": "OP não encontrada"}), 404
    return jsonify(ordem)


@app.post("/api/ordens/<int:op_id>/gerar-tarefas")
def api_gerar_tarefas(op_id):
    try:
        dados = GerarTarefasInput.model_validate(_json())
        ids = db.gerar_tarefas_da_ordem(op_id, dados.operador_id)
        return jsonify({"status": "ok", "tarefas_criadas": ids}), 201
    except ValidationError as erro:
        return _erro_validacao(erro)
    except ValueError as erro:
        return _erro_valor(erro)


@app.post("/api/ordens/<int:op_id>/finalizar")
def api_finalizar_ordem(op_id):
    ordem = db.buscar_ordem(op_id)
    if not ordem:
        return jsonify({"erro": "OP não encontrada"}), 404
    if ordem["status"] in ("finalizada", "cancelada"):
        return jsonify({"erro": "OP já encerrada"}), 409
    return jsonify(db.atualizar_status_ordem(op_id, "finalizada"))


@app.post("/api/ordens/<int:op_id>/cancelar")
def api_cancelar_ordem(op_id):
    ordem = db.buscar_ordem(op_id)
    if not ordem:
        return jsonify({"erro": "OP não encontrada"}), 404
    if ordem["status"] == "finalizada":
        return jsonify({"erro": "OP já finalizada"}), 409
    return jsonify(db.atualizar_status_ordem(op_id, "cancelada"))


# ------------------------------------------------------------ API - tarefas

@app.get("/api/tarefas")
def api_listar_tarefas():
    filtro = {
        "op_id": request.args.get("op_id", type=int),
        "operador_id": request.args.get("operador_id", type=int),
        "status": request.args.get("status"),
        "papel": request.args.get("papel"),
    }
    return jsonify(db.listar_tarefas(filtro))


@app.get("/api/tarefas/<int:tarefa_id>")
def api_detalhe_tarefa(tarefa_id):
    t = db.buscar_tarefa(tarefa_id)
    if not t:
        return jsonify({"erro": "Tarefa não encontrada"}), 404
    return jsonify(t)


@app.get("/api/operador/tarefas")
def api_operador_tarefas():
    matricula = request.args.get("matricula", "").strip()
    if not matricula:
        return jsonify({"erro": "Matrícula obrigatória"}), 422
    operador = db.buscar_operador(matricula)
    if not operador:
        return jsonify({"erro": "Matrícula não encontrada"}), 404
    if not operador["ativo"]:
        return jsonify({"erro": "Operador inativo"}), 403
    tarefas = db.listar_tarefas({"operador_id": operador["id"]})
    sem_dono = [t for t in db.listar_tarefas(
        {"status": "pendente", "papel": operador["funcao"]})
                if t["operador_id"] is None]
    return jsonify({"operador": operador, "tarefas": tarefas, "disponiveis": sem_dono})


@app.post("/api/operador/tarefas/<int:tarefa_id>/iniciar")
def api_operador_iniciar(tarefa_id):
    try:
        dados = TarefaInicio.model_validate(_json())
        operador = db.buscar_operador(dados.matricula)
        if not operador:
            return jsonify({"erro": "Matrícula não encontrada"}), 404
        if not operador["ativo"]:
            return jsonify({"erro": "Operador inativo"}), 403
        return jsonify(db.iniciar_tarefa(tarefa_id, operador["id"]))
    except ValidationError as erro:
        return _erro_validacao(erro)
    except ValueError as erro:
        return _erro_valor(erro)


@app.post("/api/operador/tarefas/<int:tarefa_id>/concluir")
def api_operador_concluir(tarefa_id):
    try:
        dados = TarefaConclusao.model_validate(_json())
        operador = db.buscar_operador(dados.matricula)
        if not operador:
            return jsonify({"erro": "Matrícula não encontrada"}), 404
        if not operador["ativo"]:
            return jsonify({"erro": "Operador inativo"}), 403
        return jsonify(db.concluir_tarefa(
            tarefa_id, dados.quantidade_retirada,
            dados.pallet_id, dados.posicao_id, dados.observacao, operador["id"],
        ))
    except ValidationError as erro:
        return _erro_validacao(erro)
    except ValueError as erro:
        return _erro_valor(erro)


@app.post("/api/operador/tarefas/<int:tarefa_id>/movimentar")
def api_operador_movimentar_pallet(tarefa_id):
    try:
        dados = MovimentarPallet.model_validate(_json())
        operador = db.buscar_operador(dados.matricula.strip())
        if not operador:
            return jsonify({"erro": "Matrícula não encontrada"}), 404
        if not operador["ativo"]:
            return jsonify({"erro": "Operador inativo"}), 403
        return jsonify(db.movimentar_pallet_op(
            tarefa_id, operador["id"], dados.posicao_destino_id,
        ))
    except ValidationError as erro:
        return _erro_validacao(erro)
    except ValueError as erro:
        return _erro_valor(erro)


@app.post("/api/tarefas/<int:tarefa_id>/cancelar")
def api_cancelar_tarefa(tarefa_id):
    tarefa = db.buscar_tarefa(tarefa_id)
    if not tarefa:
        return jsonify({"erro": "Tarefa não encontrada"}), 404
    if tarefa["status"] == "concluida":
        return jsonify({"erro": "Tarefa já concluída"}), 409
    conexao = db.conectar()
    try:
        conexao.execute("UPDATE tarefas SET status='cancelada' WHERE id=?", (tarefa_id,))
        db.registrar_auditoria(conexao, "tarefas", tarefa_id, "cancelamento", {})
        conexao.commit()
    finally:
        conexao.close()
    return jsonify(db.buscar_tarefa(tarefa_id))


# ------------------------------------------------------------ API - exceções

@app.get("/api/excecoes")
def api_listar_excecoes():
    return jsonify(db.listar_excecoes())


@app.post("/api/excecoes")
def api_criar_excecao():
    try:
        dados = ExcecaoCreate.model_validate(_json())
        payload = dados.model_dump()
        if payload.get("matricula"):
            operador = db.buscar_operador(payload["matricula"])
            if not operador:
                return jsonify({"erro": "Matrícula não encontrada"}), 404
            payload["operador_id"] = operador["id"]
        payload.pop("matricula", None)
        return jsonify(db.criar_excecao(payload)), 201
    except ValidationError as erro:
        return _erro_validacao(erro)
    except ValueError as erro:
        return _erro_valor(erro)


@app.post("/api/excecoes/<int:excecao_id>/resolver")
def api_resolver_excecao(excecao_id):
    try:
        dados = ExcecaoResolucao.model_validate(_json())
        resultado = db.resolver_excecao(excecao_id, dados.decisao)
        if not resultado:
            return jsonify({"erro": "Exceção não encontrada"}), 404
        return jsonify(resultado)
    except ValidationError as erro:
        return _erro_validacao(erro)


# ------------------------------------------------------------ API - dispositivos

@app.post("/api/dispositivos/eventos")
def api_evento_dispositivo():
    try:
        dados = DeviceEventCreate.model_validate(_json())
        resultado, novo = db.registrar_evento(dados.model_dump())
        return jsonify(resultado), 201 if novo else 200
    except ValidationError as erro:
        return _erro_validacao(erro)
    except ValueError as erro:
        return jsonify({"erro": str(erro)}), 409


@app.get("/api/dispositivos")
def api_listar_dispositivos():
    return jsonify(db.listar_dispositivos())


@app.get("/api/dispositivos/eventos")
def api_listar_eventos():
    return jsonify(db.listar_eventos_dispositivo())


# ------------------------------------------------------------ API - auditoria e dashboard

@app.get("/api/auditoria")
def api_auditoria():
    return jsonify(db.listar_auditoria())


@app.get("/api/dashboard")
def api_dashboard():
    return jsonify(db.resumo_dashboard())


# ------------------------------------------------------------ Erros genéricos

@app.errorhandler(404)
def nao_encontrado(_):
    if request.path.startswith("/api/"):
        return jsonify({"erro": "Recurso não encontrado"}), 404
    return render_template("index.html"), 404


@app.errorhandler(HTTPException)
def erro_http(e):
    if request.path.startswith("/api/"):
        return jsonify({"erro": e.description or "Erro"}), e.code or 500
    return render_template("index.html"), e.code or 500


@app.errorhandler(Exception)
def erro_generico(e):
    # Última barreira: nunca expõe traceback ao cliente.
    if request.path.startswith("/api/"):
        return jsonify({"erro": "Erro interno"}), 500
    return render_template("index.html"), 500


if __name__ == "__main__":
    app.run(debug=True)
