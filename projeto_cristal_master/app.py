import os
from datetime import datetime, date, timedelta
from flask import Flask, render_template, request, redirect, url_for, send_from_directory, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_socketio import SocketIO, emit
from sqlalchemy import func
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///cristal_master.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = 'uploads'

db = SQLAlchemy(app)
socketio = SocketIO(app)

# --------------------------------- MODELOS ---------------------------------
class Operador(db.Model):
    __tablename__ = 'operador'
    id = db.Column(db.Integer, primary_key=True)
    matricula = db.Column(db.String(4), unique=True, nullable=False)
    nome = db.Column(db.String(100))

class OrdemProducao(db.Model):
    __tablename__ = 'ordem_producao'
    id = db.Column(db.Integer, primary_key=True)
    numero_op = db.Column(db.String(20), unique=True, nullable=False)
    extrusora = db.Column(db.String(50))
    codigo_material = db.Column(db.String(50))
    descricao_material = db.Column(db.String(100))
    qtd_total_kg = db.Column(db.Float, nullable=False)
    qtd_entregue_kg = db.Column(db.Float, default=0.0)
    saldo_devedor_kg = db.Column(db.Float, nullable=False)
    status = db.Column(db.String(20), default='Ativa')

class LinhaEstoque(db.Model):
    __tablename__ = 'linha_estoque'
    id = db.Column(db.Integer, primary_key=True)
    nome_linha = db.Column(db.String(50), nullable=False)
    modo = db.Column(db.String(20), nullable=False)  # 'Consumo' ou 'Abastecimento'
    status = db.Column(db.String(20), default='Ativo')
    lote_atual = db.Column(db.String(50))
    pallets_restantes = db.Column(db.Integer, default=0)

class HistoricoBaixa(db.Model):
    __tablename__ = 'historico_baixa'
    id = db.Column(db.Integer, primary_key=True)
    op_id = db.Column(db.Integer, db.ForeignKey('ordem_producao.id'), nullable=False)
    codigo_pallet_bipado = db.Column(db.String(50))
    qtd_baixada_kg = db.Column(db.Float, nullable=False)
    operador_matricula = db.Column(db.String(4), nullable=False)
    data_hora = db.Column(db.DateTime, default=datetime.utcnow)
    status_sync = db.Column(db.String(20), default='Registrado')  # Renomeado

    ordem = db.relationship('OrdemProducao', backref='baixas')

class BloqueioFifo(db.Model):
    __tablename__ = 'bloqueio_fifo'
    id = db.Column(db.Integer, primary_key=True)
    op_id = db.Column(db.Integer, db.ForeignKey('ordem_producao.id'), nullable=False)
    motivo = db.Column(db.Text, nullable=False)
    foto_path = db.Column(db.String(200))
    operador_matricula = db.Column(db.String(4), nullable=False)
    data_hora = db.Column(db.DateTime, default=datetime.utcnow)
    status_analise = db.Column(db.String(20), default='Pendente')

    ordem = db.relationship('OrdemProducao', backref='bloqueios')

class MaterialEstoque(db.Model):
    __tablename__ = 'material_estoque'
    id = db.Column(db.Integer, primary_key=True)
    codigo_material = db.Column(db.String(50), unique=True, nullable=False)
    descricao = db.Column(db.String(100))
    saldo_real_kg = db.Column(db.Float, nullable=False, default=0.0)
    estoque_seguranca_kg = db.Column(db.Float, nullable=False, default=0.0)

# --------------------------------- SEED ---------------------------------
def seed_data():
    if OrdemProducao.query.count() == 0:
        # Operadores
        op1 = Operador(matricula='1234', nome='Operador Padrão')
        op2 = Operador(matricula='9999', nome='Líder Teste')
        db.session.add_all([op1, op2])

        # OPs
        op_prod1 = OrdemProducao(
            numero_op='OP-1001',
            extrusora='Extrusora A',
            codigo_material='MAT-PE-001',
            descricao_material='PEAD Natural',
            qtd_total_kg=10000.0,
            qtd_entregue_kg=2000.0,
            saldo_devedor_kg=8000.0,
            status='Ativa'
        )
        op_prod2 = OrdemProducao(
            numero_op='OP-1002',
            extrusora='Extrusora B',
            codigo_material='MAT-PP-002',
            descricao_material='Polipropileno Branco',
            qtd_total_kg=5000.0,
            qtd_entregue_kg=500.0,
            saldo_devedor_kg=4500.0,
            status='Ativa'
        )
        db.session.add_all([op_prod1, op_prod2])

        # Linhas duplas
        linha_consumo = LinhaEstoque(
            nome_linha='Linha Consumo 1',
            modo='Consumo',
            status='Ativo',
            lote_atual='LOTE-001',
            pallets_restantes=15
        )
        linha_abast = LinhaEstoque(
            nome_linha='Linha Abastecimento 1',
            modo='Abastecimento',
            status='Ativo',
            lote_atual='LOTE-002',
            pallets_restantes=20
        )
        db.session.add_all([linha_consumo, linha_abast])

        # Materiais
        mat1 = MaterialEstoque(
            codigo_material='MAT-PE-001',
            descricao='PEAD Natural',
            saldo_real_kg=15000.0,
            estoque_seguranca_kg=3000.0
        )
        mat2 = MaterialEstoque(
            codigo_material='MAT-PP-002',
            descricao='Polipropileno Branco',
            saldo_real_kg=2000.0,
            estoque_seguranca_kg=2500.0
        )
        db.session.add_all([mat1, mat2])

        db.session.commit()
        print("Banco SQLite criado e populado com dados iniciais.")

# --------------------------------- ROTAS ---------------------------------
@app.route('/')
def menu_principal():
    return render_template('menu.html')


@app.route('/')
def index():
    return redirect(url_for('operador'))

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

@app.route('/operador', methods=['GET', 'POST'])
def operador():
    linha_consumo = LinhaEstoque.query.filter_by(modo='Consumo', status='Ativo').first()
    ops_ativas = OrdemProducao.query.filter_by(status='Ativa').all()

    if request.method == 'POST':
        action = request.form.get('action')

        # --- Ação Baixa ---
        if action == 'baixa':
            op_id = request.form.get('op_id')
            codigo_pallet = request.form.get('codigo_pallet')
            matricula = request.form.get('matricula')
            peso_str = request.form.get('peso_pallet', '0')

            # Validação de matrícula (4 dígitos e existência no banco)
            if not matricula or len(matricula) != 4 or not matricula.isdigit():
                return "Matrícula inválida (4 dígitos)", 400
            operador = Operador.query.filter_by(matricula=matricula).first()
            if not operador:
                return "Operador não cadastrado", 400

            # Peso dinâmico
            try:
                peso = float(peso_str)
            except ValueError:
                return "Peso do pallet inválido", 400
            if peso <= 0:
                return "Peso do pallet deve ser maior que zero", 400

            op = OrdemProducao.query.get(op_id)
            if not op or op.status != 'Ativa':
                return "OP inválida ou não ativa", 400
            if op.saldo_devedor_kg < peso:
                return "Saldo devedor insuficiente na OP", 400
            if not linha_consumo or linha_consumo.pallets_restantes <= 0:
                return "Linha de consumo indisponível", 400

            # 1. Desconto na OP
            op.saldo_devedor_kg -= peso
            op.qtd_entregue_kg += peso

            # 2. Auto-conclusão da OP
            if op.saldo_devedor_kg == 0:
                op.status = 'Concluida'

            # 3. Baixa no estoque do material
            material = MaterialEstoque.query.filter_by(codigo_material=op.codigo_material).first()
            if material:
                material.saldo_real_kg -= peso

            # 4. Inversão de linhas duplas
            linha_consumo.pallets_restantes -= 1
            if linha_consumo.pallets_restantes <= 0:
                linha_consumo.modo = 'Abastecimento'
                linha_consumo.status = 'Aguardando'

                outra_linha = LinhaEstoque.query.filter(
                    LinhaEstoque.id != linha_consumo.id,
                    LinhaEstoque.modo == 'Abastecimento'
                ).first()
                if outra_linha:
                    outra_linha.modo = 'Consumo'
                    outra_linha.status = 'Ativo'
                    linha_consumo = outra_linha   # atualiza referência para o template

            # Registra histórico
            hist = HistoricoBaixa(
                op_id=op.id,
                codigo_pallet_bipado=codigo_pallet,
                qtd_baixada_kg=peso,
                operador_matricula=matricula,
                status_sync='Registrado'
            )
            db.session.add(hist)
            db.session.commit()

            # Emissão em tempo real dos KPIs do dia
            hoje = date.today()
            inicio_dia = datetime(hoje.year, hoje.month, hoje.day)
            fim_dia = inicio_dia + timedelta(days=1)
            total_kg_hoje = db.session.query(func.sum(HistoricoBaixa.qtd_baixada_kg)) \
                .filter(HistoricoBaixa.data_hora >= inicio_dia, HistoricoBaixa.data_hora < fim_dia).scalar() or 0.0
            total_baixas_hoje = db.session.query(func.count(HistoricoBaixa.id)) \
                .filter(HistoricoBaixa.data_hora >= inicio_dia, HistoricoBaixa.data_hora < fim_dia).scalar() or 0
            ops_ativas_agora = OrdemProducao.query.filter_by(status='Ativa').count()

            socketio.emit('atualizacao_dados', {
                'total_kg': round(float(total_kg_hoje), 2),
                'total_baixas': total_baixas_hoje,
                'ops_ativas': ops_ativas_agora
            })

            return redirect(url_for('operador'))

        # --- Ação Bloqueio FIFO ---
        elif action == 'bloqueio':
            op_id = request.form.get('op_id_bloq')
            motivo = request.form.get('motivo')
            matricula = request.form.get('matricula_bloq')
            foto = request.files.get('foto')

            if not matricula or len(matricula) != 4 or not matricula.isdigit():
                return "Matrícula inválida (4 dígitos)", 400
            operador = Operador.query.filter_by(matricula=matricula).first()
            if not operador:
                return "Operador não cadastrado", 400
            if not motivo:
                return "Motivo obrigatório", 400
            if not foto:
                return "Foto obrigatória", 400

            filename = f"{datetime.now().strftime('%Y%m%d%H%M%S')}_{secure_filename(foto.filename)}"
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            foto.save(filepath)

            bloq = BloqueioFifo(
                op_id=op_id,
                motivo=motivo,
                foto_path=filename,
                operador_matricula=matricula,
                status_analise='Pendente'
            )
            db.session.add(bloq)
            db.session.commit()
            return redirect(url_for('operador'))

        else:
            return "Ação inválida", 400

    return render_template('operador.html', linha_consumo=linha_consumo, ops_ativas=ops_ativas)

@app.route('/lider', methods=['GET'])
def lider():
    # Filtro de período
    hoje = date.today()
    data_fim_default = hoje.strftime('%Y-%m-%d')
    data_inicio_default = (hoje - timedelta(days=7)).strftime('%Y-%m-%d')

    data_inicio_str = request.args.get('data_inicio', data_inicio_default)
    data_fim_str = request.args.get('data_fim', data_fim_default)

    try:
        inicio = datetime.strptime(data_inicio_str, '%Y-%m-%d')
        fim = datetime.strptime(data_fim_str, '%Y-%m-%d') + timedelta(days=1)
    except ValueError:
        inicio = datetime.strptime(data_inicio_default, '%Y-%m-%d')
        fim = datetime.strptime(data_fim_default, '%Y-%m-%d') + timedelta(days=1)
        data_inicio_str = data_inicio_default
        data_fim_str = data_fim_default

    # KPIs
    total_kg = db.session.query(func.sum(HistoricoBaixa.qtd_baixada_kg)) \
                .filter(HistoricoBaixa.data_hora >= inicio, HistoricoBaixa.data_hora < fim).scalar() or 0.0
    total_baixas = db.session.query(func.count(HistoricoBaixa.id)) \
                    .filter(HistoricoBaixa.data_hora >= inicio, HistoricoBaixa.data_hora < fim).scalar()
    total_bloqueios = db.session.query(func.count(BloqueioFifo.id)) \
                       .filter(BloqueioFifo.data_hora >= inicio, BloqueioFifo.data_hora < fim).scalar()
    total_ops_ativas = OrdemProducao.query.filter_by(status='Ativa').count()

    # Gráfico volume diário
    volume_por_dia = db.session.query(
        func.date(HistoricoBaixa.data_hora).label('dia'),
        func.sum(HistoricoBaixa.qtd_baixada_kg).label('total_kg')
    ).filter(
        HistoricoBaixa.data_hora >= inicio,
        HistoricoBaixa.data_hora < fim
    ).group_by('dia').order_by('dia').all()
    grafico_volume_labels = [str(dia) for dia, _ in volume_por_dia]
    grafico_volume_data = [float(total) for _, total in volume_por_dia]

    # Gráfico status OPs
    ops_ativas_graf = OrdemProducao.query.filter_by(status='Ativa').count()
    ops_concluidas = OrdemProducao.query.filter(OrdemProducao.status != 'Ativa').count()
    grafico_status_labels = ['Ativas', 'Concluídas']
    grafico_status_data = [ops_ativas_graf, ops_concluidas]

    # Materiais críticos (alerta ERP Central)
    materiais_criticos = MaterialEstoque.query.filter(
        MaterialEstoque.saldo_real_kg <= MaterialEstoque.estoque_seguranca_kg
    ).all()

    # Tabelas detalhadas
    ops = OrdemProducao.query.all()
    linhas = LinhaEstoque.query.all()
    historicos = HistoricoBaixa.query \
        .filter(HistoricoBaixa.data_hora >= inicio, HistoricoBaixa.data_hora < fim) \
        .order_by(HistoricoBaixa.data_hora.desc()).all()
    bloqueios = BloqueioFifo.query \
        .filter(BloqueioFifo.data_hora >= inicio, BloqueioFifo.data_hora < fim) \
        .order_by(BloqueioFifo.data_hora.desc()).all()

    return render_template('lider.html',
                           data_inicio=data_inicio_str,
                           data_fim=data_fim_str,
                           total_kg=total_kg,
                           total_baixas=total_baixas,
                           total_bloqueios=total_bloqueios,
                           total_ops_ativas=total_ops_ativas,
                           grafico_volume_labels=grafico_volume_labels,
                           grafico_volume_data=grafico_volume_data,
                           grafico_status_labels=grafico_status_labels,
                           grafico_status_data=grafico_status_data,
                           materiais_criticos=materiais_criticos,
                           ops=ops,
                           linhas=linhas,
                           historicos=historicos,
                           bloqueios=bloqueios)

# Rota genérica de sincronização com ERP (gatilho WebSocket)
@app.route('/api/sync_erp', methods=['POST'])
def sync_erp():
    dados = request.get_json(silent=True)
    if not dados:
        dados = {}
    # Simulação de processamento de sincronização
    socketio.emit('erp_sync_confirmation', {
        'mensagem': 'Sincronização com ERP Central concluída',
        'dados': dados
    })
    return jsonify({'status': 'ok', 'mensagem': 'Sincronização iniciada'})

# --------------------------------- MAIN ---------------------------------
if __name__ == '__main__':
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    with app.app_context():
        db.create_all()
        seed_data()
    socketio.run(app, debug=True, port=8080)