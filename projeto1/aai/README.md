# AAI — Almoxarifado Assistido por IA

Base consolidada de apoio ao controle de almoxarifado e à retirada de
materiais para Ordens de Produção (OP). Duas áreas: **Líder** (administra) e
**Operador** (executa).

Este README reflete o estado real desta versão-base. Ele não afirma que o
sistema está pronto para produção nem que todas as regras operacionais
estão concluídas.

## Stack

Python, Flask, SQLite3, Pydantic, HTML, CSS, JavaScript. Sem Blueprints,
Application Factory, ORM, frameworks JS ou Docker.

## Estrutura de pastas

```
.
├── app.py
├── database.py
├── schemas.py
├── run.py
├── requirements.txt
├── README.md
├── .env.example
├── .gitignore
├── templates/
│   ├── base.html
│   ├── index.html
│   ├── lider/        (dashboard, materiais, estoque, operadores, ordens,
│   │                   ordem-detalhes, tarefas, movimentacoes, auditoria,
│   │                   dispositivos, excecoes, _sidebar)
│   └── operador/      (acesso, inicio, tarefas, tarefa-detalhes,
│                        confirmacao, excecao)
├── static/
│   ├── css/style.css
│   ├── js/{lider.js, operador.js}
│   └── images/banner_smartcolector.jpg
└── scripts/
    └── smoke_test.py
```

## Instalação

```bash
python3 -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

## Execução

```bash
python run.py
# abrir http://127.0.0.1:5000
```

## Testes

```bash
python scripts/smoke_test.py
```

## Regra de permissão

```
Líder administra.
Operador executa.
```

A OP pertence à área do líder. Operadores têm função `separador` ou
`empilhadeira`; a API restringe cada tarefa à função correspondente.

## Rotas HTML

```
GET  /
GET  /lider
GET  /lider/materiais
GET  /lider/estoque
GET  /lider/operadores
GET  /lider/ordens
GET  /lider/ordens/<id>
GET  /lider/tarefas
GET  /lider/movimentacoes
GET  /lider/auditoria
GET  /lider/dispositivos
GET  /lider/excecoes
GET  /operador
GET  /operador/inicio
GET  /operador/tarefas
GET  /operador/tarefas/<id>
GET  /operador/confirmacao
GET  /operador/excecao
```

## Rotas API

```
GET  /api/health
GET  /api/materiais                    POST /api/materiais
PUT  /api/materiais/<id>
POST /api/materiais/<id>/ativar        POST /api/materiais/<id>/desativar
GET  /api/operadores                   POST /api/operadores
PUT  /api/operadores/<id>
POST /api/operador/identificar
GET  /api/operador/tarefas?matricula=
POST /api/operador/tarefas/<id>/iniciar
POST /api/operador/tarefas/<id>/concluir
POST /api/operador/tarefas/<id>/movimentar
GET  /api/posicoes                     POST /api/posicoes
GET  /api/lotes                        POST /api/lotes
GET  /api/pallets                      POST /api/pallets
POST /api/pallets/<id>/bloquear        POST /api/pallets/<id>/desbloquear
GET  /api/estoque
POST /api/movimentacoes/entrada
GET  /api/movimentacoes
GET  /api/ajustes-estoque              POST /api/ajustes-estoque
GET/POST /api/demandas
GET/PUT  /api/demandas/<id>
POST /api/demandas/<id>/confirmar
POST /api/gemini/interpretar
GET  /api/pallets-op?op_id=<id>
POST /api/pallets-op/<id>/fechar
POST /api/pallets-op/<id>/bloquear
POST /api/pallets-op/<id>/desbloquear
GET  /api/ordens                       POST /api/ordens
GET  /api/ordens/<id>
POST /api/ordens/<id>/gerar-tarefas
POST /api/ordens/<id>/finalizar        POST /api/ordens/<id>/cancelar
GET  /api/tarefas                      GET /api/tarefas/<id>
POST /api/tarefas/<id>/cancelar
GET  /api/excecoes                     POST /api/excecoes
POST /api/excecoes/<id>/resolver
GET  /api/dispositivos                 GET /api/dispositivos/eventos
POST /api/dispositivos/eventos
GET  /api/auditoria
GET  /api/dashboard
```

## Códigos HTTP

- 200 — OK
- 201 — criado
- 404 — registro inexistente (material, lote, pallet, posição, operador,
  tarefa, exceção, OP)
- 409 — conflito (duplicidade de código, referência incoerente, pallet
  bloqueado, saldo insuficiente, OP já encerrada, tarefa de outro operador)
- 422 — dados inválidos (validação Pydantic)
- 500 — erro inesperado não previsto (nunca expõe traceback; última
  barreira via `errorhandler(Exception)`)

## Tabelas

`materiais`, `operadores`, `posicoes`, `lotes`, `pallets`,
`ordens_producao`, `itens_ordem_producao`, `tarefas`, `movimentacoes`,
`auditoria`, `eventos_dispositivo`, `excecoes`, `configuracoes_embalagem`,
`demandas`, `demanda_itens`, `pallets_op`, `ajustes_estoque`. A inicialização
adiciona as colunas novas às tabelas legadas sem apagar os dados existentes.

## Existe e funciona

- Cadastro/listagem/ativação/desativação de materiais, com validação de
  duplicidade e de existência (404 para ID inexistente).
- Cadastro/listagem/atualização de operadores; identificação por matrícula
  (sem senha).
- Posições, lotes e pallets, com validação de referência: lote exige
  material existente; pallet exige lote (e posição, se informada)
  existentes; mensagens de erro coerentes com a causa real.
- Bloqueio/desbloqueio de pallet, incluindo tratamento de ID inexistente
  (404, sem erro 500).
- Entrada de estoque com validação completa de referências e coerência:
  material, lote, pallet e posição precisam existir; lote precisa
  pertencer ao material informado; pallet precisa pertencer ao lote (ou
  ao material, quando só o pallet é informado).
- Ordens de Produção com itens, prioridade e prazo; validação de material
  inexistente antes da criação.
- Demanda simulada em rascunho com múltiplas cargas e materiais, edição antes
  da confirmação, snapshot por fornecedor/material da embalagem e visualização
  de saldo/falta estimada sem reserva ou criação de estoque.
- Confirmação de demanda cria OP, itens e tarefa de separação por item, mantendo
  o vínculo demanda → OP → item → tarefa.
- Sacarias completas calculadas por divisão inteira; resto tratado como
  pesagem. Capacidade configurável por material/fornecedor e pallets múltiplos
  planejados individualmente, sem capacidade universal fixa.
- Tarefa separadora e tarefa de empilhadeira são distintas. Apenas pallet
  fechado cria tarefa de transporte; movimentação registra pallet da OP e
  posições de origem/destino sem duplicar saldo.
- Ajustes manuais append-only guardam saldo anterior, delta, posterior,
  referência física, motivo, responsável e data; divergências de lote/posição
  registram valor anterior e correção sem ajuste fictício de quantidade.
- Geração de tarefas a partir da OP, com recomendação FIFO de lote (regra
  já existente, não foi criada política nova) e validação de operador
  inexistente.
- Execução de tarefa pelo operador:
  - uma tarefa pré-atribuída a um operador não pode ser iniciada por outro;
  - bloqueio de pallet impede movimentação;
  - conclusão rejeita pallet de material diferente do da tarefa;
  - validação de saldo suficiente **antes** de gravar a saída, sempre
    numa única granularidade (pallet > lote > material), nunca combinando
    identificadores de forma ambígua.
- Finalização automática da OP quando todas as tarefas são concluídas.
- Abertura de exceção pelo operador (com validação de tarefa inexistente)
  e resolução pelo líder.
- Recebimento idempotente de evento de dispositivo (ESP/RFID) — duplicidade
  tratada.
- Auditoria de ações (criação, alteração, bloqueio, conclusão etc.).
- Dashboard do líder com dados reais do banco, atualizado por polling
  JavaScript a cada 5s (sem WebSocket).
- Todas as telas do líder e do operador abrem, carregam CSS/JS e não
  apresentam `TemplateNotFound`, seletor JS órfão ou link quebrado.
- Tratamento de erros em três camadas: 404 específico, `HTTPException`
  genérica e `Exception` genérica — nenhuma rota expõe traceback.

## Existe parcialmente

- **FIFO**: recomendação do lote mais antigo com saldo, usada na geração
  de tarefas. Não há divisão automática entre múltiplos lotes — se um
  único lote não cobre a quantidade, o sistema recomenda o primeiro com
  saldo positivo e deixa a conclusão validar o saldo disponível.
- **Integração ESP/RFID**: apenas recepção de evento JSON com idempotência
  básica (classificada como PREPARAÇÃO EXISTENTE). Nenhum firmware, GPIO
  ou protocolo elétrico é implementado; o formato final do evento depende
  da especificação da parte elétrica, ainda não entregue.
- **Gemini**: interpretação opcional de foto/PDF retorna apenas uma proposta
  JSON para revisão. Sem chave ou sem chamada externa, a demanda manual funciona;
  a API não grava a OP nem altera estoque durante a interpretação.

## Pendente

- Telas dedicadas de lote, pallet e posição no painel do líder (hoje
  geridos via API/telas de estoque existentes; não fazem parte desta
  entrega como telas próprias).
- Consolidação e conclusão automática de pallets parciais entre separações;
  sobras ficam em montagem e continuam sob o separador, sem tarefa de
  empilhadeira.
- FEFO — a tabela `lotes` guarda `validade`, mas não há regra que
  priorize lote por vencimento (decisão intencional: não foi criada
  política nova nesta etapa).

## Fora do escopo desta base

- Autenticação real (login/senha) do líder — o painel está aberto, sem
  sessão, cookies ou tokens. Ambiente de desenvolvimento apenas. A
  matrícula do operador continua sendo identificação provisória, não
  autenticação.
- Reserva de estoque, divisão de tarefa entre lotes, estorno, contagem
  física, replanejamento automático.
- Relatórios, exportações, impressão.
- WebSocket / notificações em tempo real.
- Integração com ERP externo.
- Captura por câmera, leitura real de RFID/leitor físico, integração elétrica,
  firmware e ERP externo.

## Limitações conhecidas

- Painel do líder aberto, sem autenticação — ambiente de desenvolvimento.
- O cálculo de saldo por pallet pressupõe que todas as entradas e saídas
  relevantes foram registradas com `pallet_id`. Sem isso, a granularidade
  cai para lote ou material.
- A recomendação FIFO não distribui uma tarefa entre múltiplos lotes.

## Exemplos

```bash
curl -X POST http://127.0.0.1:5000/api/materiais \
  -H 'Content-Type: application/json' \
  -d '{"codigo":"MAT-001","descricao":"Resina","unidade":"kg"}'

curl -X POST http://127.0.0.1:5000/api/dispositivos/eventos \
  -H 'Content-Type: application/json' \
  -d '{"evento_id":"EVT-001","dispositivo_id":"ESP32-A1","uid_rfid":"RFID-001","tipo_evento":"tag_detectada","valor":true}'
```

## Fluxo de demanda, separação e empilhadeira

O painel do líder permite salvar uma demanda simulada como rascunho e revisar
produto, cargas e itens antes de confirmar. A confirmação cria a OP, seus itens,
uma tarefa de separação por material e os registros individuais dos pallets.
Materiais novos podem ser cadastrados no catálogo durante o rascunho; isso não
cria saldo de estoque.

Por item, o total é `quantidade_por_carga × quantidade_cargas`. Sacarias são
calculadas por divisão inteira pelo peso da embalagem; o restante é pesagem.
A configuração de embalagem é identificada por material e fornecedor e seus
valores são copiados para o item da demanda para preservar o planejamento
original. O código não assume capacidade fixa de pallet.

Cada pallet planejado possui status e quantidade próprios. O separador inicia a
tarefa, confirma o fechamento de cada pallet que atingiu a capacidade e conclui
a quantidade separada. Cada fechamento cria uma tarefa independente de
empilhadeira; o operador dessa função só consegue iniciar pallets fechados e
registra a posição de destino. Transferências são auditadas e não alteram o
saldo de material pela segunda vez.

O painel de estoque aceita ajustes físicos explícitos para falta, sobra,
pallet encontrado/sem identificação e divergência de lote/posição. O registro
guarda saldo anterior, delta e saldo posterior e não oferece edição ou exclusão
pela API. Ajuste positivo exige ação manual; nenhuma demanda ou leitura de
documento gera estoque automaticamente.

## Gemini opcional

A interpretação de foto/PDF da OP é assistida e não autoritativa. Só ocorre
quando o líder solicita na tela de ordens. A API valida a resposta estruturada
com Pydantic e a compara com materiais e posições cadastrados. A resposta inclui
`campos_ausentes` e `alertas` para material não encontrado, divergência de
descrição/unidade ou localização sem cadastro; esses alertas não bloqueiam a
interpretação, mas precisam ser revisados.

A tela apresenta prévia local da imagem ou PDF selecionado; selecionar o arquivo
não o envia. Após a interpretação, o líder precisa revisar/corrigir os campos e
salvar a demanda como rascunho. A confirmação manual continua obrigatória.
Interpretar um documento não cria demanda, OP, material ou movimentação e não
altera estoque.

Configure a chave somente localmente, sem colocá-la no código, README, Git ou
mensagens:

```powershell
Copy-Item .env.example .env
```

Edite `.env` na máquina local e preencha `GEMINI_API_KEY=`. O arquivo `.env`
já está ignorado pelo Git. `GEMINI_MODEL` pode ser ajustado localmente; o padrão
é `gemini-2.5-flash`. Alternativamente, defina `GEMINI_API_KEY` no ambiente do
processo antes de iniciar `python run.py`. `.env` permanece no `.gitignore` e
nunca deve ser incluído em commit ou ZIP. A chave não é devolvida nem registrada
na auditoria.

O modelo apenas preenche uma proposta estruturada. A auditoria guarda nome,
tipo e tamanho do arquivo, modelo, contagens de alertas/campos ausentes e ações
de revisão; não guarda a chave, cabeçalhos, Base64 nem o documento. Sem chave,
a tela manual continua funcionando e a rota responde `503`.

## Rotas adicionadas

```text
GET/POST /api/demandas
GET/PUT  /api/demandas/<id>
POST     /api/demandas/<id>/confirmar
POST     /api/gemini/interpretar
GET      /api/pallets-op?op_id=<id>
POST     /api/pallets-op/<id>/fechar
POST     /api/pallets-op/<id>/bloquear
POST     /api/pallets-op/<id>/desbloquear
POST     /api/operador/tarefas/<id>/movimentar
GET/POST /api/ajustes-estoque
```

## Testes e isolamento

Execute `python3 -m compileall -q .` e `python3 scripts/smoke_test.py`. O teste
troca o caminho SQLite por arquivos temporários antes de importar `app.py`; não
usa `almoxarifado.db`, não depende de chave real e mocka `urlopen` nos cenários
de resposta Gemini válida, inválida, timeout e falha de conexão.

## Limitações desta evolução

- A capacidade fica configurada por material/fornecedor e copiada na demanda;
  não há sobrescrita por lote nesta versão.
- Pallets parciais continuam em montagem sob responsabilidade do separador.
  Não há consolidação de sobras entre demandas, então a tarefa de separação
  permanece aberta até que todos os pallets do item sejam fechados.
- A posição origem informada como texto na demanda não é conciliada
  automaticamente com posições cadastradas; o destino da empilhadeira é
  validado por ID.
- O campo responsável do ajuste é uma declaração digitada. Como o painel do
  líder ainda não possui autenticação, isso não comprova identidade.
- A integração Gemini exige credencial e rede e não é chamada pelo smoke test.
  O smoke test valida o contrato com mock, não a disponibilidade real do modelo
  ou a qualidade de OCR. Interpretar documento não confirma OP nem atualiza saldo.
- Nenhuma integração elétrica, firmware, RFID físico, ERP ou autenticação real
  foi concluída.
