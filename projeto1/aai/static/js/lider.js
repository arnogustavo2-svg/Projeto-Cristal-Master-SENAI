async function api(url, opcoes = {}) {
    const resp = await fetch(url, {
        headers: { "Content-Type": "application/json" },
        ...opcoes,
    });
    let dados = null;
    try { dados = await resp.json(); } catch (_) {}
    if (!resp.ok) {
        const msg = (dados && (dados.erro || (dados.detalhes && dados.detalhes[0]?.msg))) || `Erro ${resp.status}`;
        throw new Error(msg);
    }
    return dados;
}

function texto(valor) { return valor === null || valor === undefined ? "—" : String(valor); }

/* ---------------------------- Dashboard ---------------------------- */
async function carregarDashboard() {
    const cards = document.querySelector("#dashboard-cards");
    if (!cards) return;
    try {
        const d = await api("/api/dashboard");
        cards.innerHTML = `
            <div class="card"><span>${d.materiais_cadastrados}</span><small>Materiais</small></div>
            <div class="card"><span>${d.operadores_ativos}</span><small>Operadores ativos</small></div>
            <div class="card"><span>${d.tarefas_pendentes}</span><small>Pendentes</small></div>
            <div class="card"><span>${d.tarefas_em_andamento}</span><small>Em andamento</small></div>
            <div class="card"><span>${d.tarefas_concluidas}</span><small>Concluídas</small></div>
            <div class="card"><span>${d.tarefas_bloqueadas}</span><small>Bloqueadas</small></div>
            <div class="card"><span>${d.excecoes_abertas}</span><small>Exceções abertas</small></div>`;
        const movs = document.querySelector("#dashboard-movs");
        movs.innerHTML = d.movimentacoes_recentes.length
            ? d.movimentacoes_recentes.map(m => `<li>#${m.id} ${m.tipo} — material ${m.material_id} — qtd ${m.quantidade} — ${m.criado_em}</li>`).join("")
            : "<li>Sem movimentações.</li>";
        document.querySelector("#dashboard-excecoes").textContent = `${d.excecoes_abertas} aberta(s)`;
        const alertas = document.querySelector("#dashboard-alertas");
        alertas.innerHTML = d.alertas_estoque.length
            ? d.alertas_estoque.map(a => `<li>${a.codigo}: saldo ${a.saldo}</li>`).join("")
            : "<li>Sem alertas.</li>";
        const ev = document.querySelector("#dashboard-eventos");
        ev.innerHTML = d.eventos_dispositivos.length
            ? d.eventos_dispositivos.map(e => `<li>${e.criado_em} — ${e.dispositivo_id} — ${e.tipo_evento}</li>`).join("")
            : "<li>Sem eventos.</li>";
    } catch (e) {
        cards.innerHTML = `<p class="message">Erro: ${e.message}</p>`;
    }
}

/* ---------------------------- Materiais ---------------------------- */
async function carregarMateriais() {
    const tabela = document.querySelector("#tabela-materiais");
    if (!tabela) return;
    try {
        const materiais = await api("/api/materiais");
        const filtro = (document.querySelector("#busca-material")?.value || "").toLowerCase();
        tabela.innerHTML = materiais
            .filter(m => !filtro || m.codigo.toLowerCase().includes(filtro) || m.descricao.toLowerCase().includes(filtro))
            .map(m => `<tr>
                <td>${m.codigo}</td><td>${m.descricao}</td><td>${m.unidade}</td>
                <td>${m.ativo ? "Sim" : "Não"}</td>
                <td>
                    <button class="button secondary" data-acao="${m.ativo ? "desativar" : "ativar"}" data-id="${m.id}">
                        ${m.ativo ? "Desativar" : "Ativar"}
                    </button>
                </td></tr>`).join("") || "<tr><td colspan='5'>Nenhum material.</td></tr>";
        tabela.querySelectorAll("button[data-acao]").forEach(b => {
            b.addEventListener("click", async () => {
                try {
                    await api(`/api/materiais/${b.dataset.id}/${b.dataset.acao}`, { method: "POST", body: "{}" });
                    carregarMateriais();
                } catch (e) { alert(e.message); }
            });
        });
    } catch (e) { tabela.innerHTML = `<tr><td colspan="5">Erro: ${e.message}</td></tr>`; }
}

const formMaterial = document.querySelector("#form-material");
if (formMaterial) {
    formMaterial.addEventListener("submit", async ev => {
        ev.preventDefault();
        const dados = Object.fromEntries(new FormData(formMaterial));
        const msg = document.querySelector("#msg-material");
        try {
            await api("/api/materiais", { method: "POST", body: JSON.stringify(dados) });
            msg.textContent = "Material cadastrado.";
            formMaterial.reset();
            carregarMateriais();
        } catch (e) { msg.textContent = e.message; }
    });
    document.querySelector("#refresh-materiais")?.addEventListener("click", carregarMateriais);
    document.querySelector("#busca-material")?.addEventListener("input", carregarMateriais);
    carregarMateriais();
}

/* ---------------------------- Operadores ---------------------------- */
async function carregarOperadores() {
    const tabela = document.querySelector("#tabela-operadores");
    if (!tabela) return;
    try {
        const ops = await api("/api/operadores");
        tabela.innerHTML = ops.map(o => `<tr>
            <td>${o.matricula}</td><td>${o.nome}</td><td>${o.funcao === "empilhadeira" ? "Empilhadeira" : "Separador"}</td>
            <td>${o.ativo ? "Sim" : "Não"}</td>
            <td>
                <button class="button secondary" data-id="${o.id}" data-ativo="${o.ativo ? 0 : 1}">
                    ${o.ativo ? "Desativar" : "Ativar"}
                </button>
            </td>
            <td><a href="/api/tarefas?operador_id=${o.id}" target="_blank">Ver</a></td>
        </tr>`).join("") || "<tr><td colspan='6'>Nenhum operador.</td></tr>";
        tabela.querySelectorAll("button[data-id]").forEach(b => {
            b.addEventListener("click", async () => {
                try {
                    await api(`/api/operadores/${b.dataset.id}`, {
                        method: "PUT",
                        body: JSON.stringify({ ativo: b.dataset.ativo === "1" }),
                    });
                    carregarOperadores();
                } catch (e) { alert(e.message); }
            });
        });
    } catch (e) { tabela.innerHTML = `<tr><td colspan="5">Erro: ${e.message}</td></tr>`; }
}

const formOperador = document.querySelector("#form-operador");
if (formOperador) {
    formOperador.addEventListener("submit", async ev => {
        ev.preventDefault();
        const dados = Object.fromEntries(new FormData(formOperador));
        const msg = document.querySelector("#msg-operador");
        try {
            await api("/api/operadores", { method: "POST", body: JSON.stringify(dados) });
            msg.textContent = "Operador cadastrado.";
            formOperador.reset();
            carregarOperadores();
        } catch (e) { msg.textContent = e.message; }
    });
    carregarOperadores();
}

/* ---------------------------- Ordens ---------------------------- */
const escaparHtml = valor => String(valor ?? "").replace(/[&<>"']/g, caractere => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
}[caractere]));

let demandaAtualId = null;
let demandaAtual = null;
let interpretacaoIdPendente = null;

function adicionarLinhaDemanda(item = {}) {
    const container = document.querySelector("#itens-demanda");
    if (!container) return;
    const linha = document.createElement("fieldset");
    linha.className = "linha-demanda";
    linha.innerHTML = `
        <legend>Material</legend>
        <label>Código<input class="codigo-material" required maxlength="50"></label>
        <label>Descrição<input class="descricao-material" required maxlength="200"></label>
        <label>Localização<input class="localizacao-material" required maxlength="100"></label>
        <label>Quantidade por carga<input class="quantidade-carga" type="number" min="0.000001" step="any" required></label>
        <label>Unidade<input class="unidade-material" required maxlength="20"></label>
        <label>Fornecedor<input class="fornecedor-material" required maxlength="120"></label>
        <label>Peso da sacaria<input class="peso-sacaria" type="number" min="0.000001" step="any" required></label>
        <label>Capacidade do pallet<input class="capacidade-pallet" type="number" min="0.000001" step="any" required></label>
        <label>Observação<textarea class="observacao-material" maxlength="500"></textarea></label>
        <button class="button danger remover-material" type="button">Remover material</button>`;
    const campos = {
        ".codigo-material": item.codigo_material,
        ".descricao-material": item.descricao_material,
        ".localizacao-material": item.localizacao,
        ".quantidade-carga": item.quantidade_por_carga,
        ".unidade-material": item.unidade,
        ".fornecedor-material": item.fornecedor,
        ".peso-sacaria": item.peso_sacaria,
        ".capacidade-pallet": item.capacidade_pallet,
        ".observacao-material": item.observacao,
    };
    for (const [seletor, valor] of Object.entries(campos)) {
        linha.querySelector(seletor).value = valor ?? "";
    }
    linha.querySelector(".remover-material").addEventListener("click", () => {
        if (container.children.length > 1) linha.remove();
    });
    container.appendChild(linha);
}

function coletarDadosDemanda() {
    const base = Object.fromEntries(new FormData(document.querySelector("#form-demanda")));
    return {
        codigo: base.codigo,
        produto: base.produto,
        quantidade_cargas: Number(base.quantidade_cargas),
        observacao: base.observacao || null,
        itens: [...document.querySelectorAll("#itens-demanda .linha-demanda")].map(linha => ({
            codigo_material: linha.querySelector(".codigo-material").value.trim(),
            descricao_material: linha.querySelector(".descricao-material").value.trim(),
            localizacao: linha.querySelector(".localizacao-material").value.trim(),
            quantidade_por_carga: Number(linha.querySelector(".quantidade-carga").value),
            unidade: linha.querySelector(".unidade-material").value.trim(),
            fornecedor: linha.querySelector(".fornecedor-material").value.trim(),
            peso_sacaria: Number(linha.querySelector(".peso-sacaria").value),
            capacidade_pallet: Number(linha.querySelector(".capacidade-pallet").value),
            observacao: linha.querySelector(".observacao-material").value || null,
        })),
    };
}

function preencherDemanda(demanda) {
    const form = document.querySelector("#form-demanda");
    form.elements.codigo.value = demanda.codigo || "";
    form.elements.produto.value = demanda.produto || "";
    form.elements.quantidade_cargas.value = demanda.quantidade_cargas || "";
    form.elements.observacao.value = demanda.observacao || "";
    const container = document.querySelector("#itens-demanda");
    container.innerHTML = "";
    (demanda.itens || []).forEach(adicionarLinhaDemanda);
    if (!container.children.length) adicionarLinhaDemanda();
}

function mostrarRevisaoDemanda(demanda) {
    demandaAtual = demanda;
    demandaAtualId = demanda.id;
    document.querySelector("#revisao-demanda").hidden = false;
    document.querySelector("#resumo-demanda").innerHTML = `
        <p><strong>${escaparHtml(demanda.codigo)}</strong> | ${escaparHtml(demanda.produto)} |
        ${escaparHtml(demanda.quantidade_cargas)} carga(s) | ${escaparHtml(demanda.status)}</p>
        <table class="tabela"><thead><tr><th>Material</th><th>Local</th><th>Total</th><th>Saldo atual</th><th>Falta estimada</th><th>Sacarias</th><th>Pesagem</th><th>Fornecedor</th><th>Capacidade pallet</th></tr></thead>
        <tbody>${demanda.itens.map(item => `<tr>
            <td>${escaparHtml(item.codigo_material)} - ${escaparHtml(item.descricao_material)}</td>
            <td>${escaparHtml(item.localizacao)}</td>
            <td>${escaparHtml(item.quantidade_total)} ${escaparHtml(item.unidade)}</td>
            <td>${escaparHtml(item.saldo_disponivel ?? "—")} ${escaparHtml(item.unidade)}</td>
            <td>${escaparHtml(item.saldo_faltante ?? "—")} ${escaparHtml(item.unidade)}</td>
            <td>${escaparHtml(item.sacarias_fechadas)} (${escaparHtml(item.quantidade_em_sacarias)} ${escaparHtml(item.unidade)})</td>
            <td>${escaparHtml(item.quantidade_em_pesagem)} ${escaparHtml(item.unidade)}</td>
            <td>${escaparHtml(item.fornecedor)}</td>
            <td>${escaparHtml(item.capacidade_pallet)} ${escaparHtml(item.unidade)}</td>
        </tr>`).join("")}</tbody></table>`;
    document.querySelector("#confirmar-demanda").hidden = demanda.status !== "rascunho";
    document.querySelector("#msg-revisao").textContent = demanda.status === "rascunho"
        ? "Confira os dados. Nada foi convertido em OP até a confirmação."
        : `OP ${demanda.codigo_op || demanda.op_id || ""} já confirmada.`;
}

const formDemanda = document.querySelector("#form-demanda");
if (formDemanda) {
    adicionarLinhaDemanda();
    document.querySelector("#add-item-demanda").addEventListener("click", () => adicionarLinhaDemanda());
    formDemanda.addEventListener("submit", async evento => {
        evento.preventDefault();
        const mensagem = document.querySelector("#msg-demanda");
        try {
            const dados = coletarDadosDemanda();
            if (interpretacaoIdPendente) dados.interpretacao_id = interpretacaoIdPendente;
            const resposta = demandaAtualId
                ? await api(`/api/demandas/${demandaAtualId}`, { method: "PUT", body: JSON.stringify(dados) })
                : await api("/api/demandas", { method: "POST", body: JSON.stringify(dados) });
            interpretacaoIdPendente = null;
            mostrarRevisaoDemanda(resposta);
            mensagem.textContent = "Rascunho salvo. Revise os cálculos antes de confirmar.";
            carregarDemandas();
        } catch (erro) { mensagem.textContent = erro.message; }
    });
    document.querySelector("#editar-demanda").addEventListener("click", () => {
        document.querySelector("#revisao-demanda").hidden = true;
        formDemanda.scrollIntoView({ behavior: "smooth", block: "start" });
    });
    document.querySelector("#confirmar-demanda").addEventListener("click", async () => {
        if (!demandaAtualId) return;
        const mensagem = document.querySelector("#msg-revisao");
        try {
            const resposta = await api(`/api/demandas/${demandaAtualId}/confirmar`, { method: "POST", body: "{}" });
            window.location.href = `/lider/ordens/${resposta.ordem.id}`;
        } catch (erro) { mensagem.textContent = erro.message; }
    });
}

async function carregarDemandas() {
    const tabela = document.querySelector("#tabela-demandas");
    if (!tabela) return;
    try {
        const demandas = await api("/api/demandas");
        tabela.innerHTML = demandas.map(d => `<tr>
            <td>${escaparHtml(d.codigo)}</td><td>${escaparHtml(d.produto)}</td>
            <td>${escaparHtml(d.quantidade_cargas)}</td><td>${escaparHtml(d.status)}</td>
            <td>${escaparHtml(d.codigo_op)}</td>
            <td><button class="button secondary" data-demanda="${d.id}">Revisar</button></td>
        </tr>`).join("") || "<tr><td colspan='6'>Nenhuma demanda.</td></tr>";
        tabela.querySelectorAll("button[data-demanda]").forEach(botao => {
            botao.addEventListener("click", async () => {
                try {
                    const demanda = await api(`/api/demandas/${botao.dataset.demanda}`);
                    preencherDemanda(demanda);
                    mostrarRevisaoDemanda(demanda);
                    formDemanda.scrollIntoView({ behavior: "smooth", block: "start" });
                } catch (erro) { alert(erro.message); }
            });
        });
    } catch (erro) { tabela.innerHTML = `<tr><td colspan='6'>Erro: ${escaparHtml(erro.message)}</td></tr>`; }
}

const formGemini = document.querySelector("#form-gemini");
if (formGemini) {
    let urlPreviaDocumento = null;
    const inputArquivo = formGemini.elements.arquivo;
    const areaPrevia = document.querySelector("#previsualizacao-documento");
    const previaImagem = document.querySelector("#previa-imagem-documento");
    const previaPdf = document.querySelector("#previa-pdf-documento");
    inputArquivo.addEventListener("change", () => {
        if (urlPreviaDocumento) URL.revokeObjectURL(urlPreviaDocumento);
        urlPreviaDocumento = null;
        previaImagem.hidden = true;
        previaPdf.hidden = true;
        const arquivo = inputArquivo.files[0];
        if (!arquivo) {
            areaPrevia.hidden = true;
            document.querySelector("#nome-documento-selecionado").textContent = "";
            return;
        }
        areaPrevia.hidden = false;
        document.querySelector("#nome-documento-selecionado").textContent = arquivo.name;
        urlPreviaDocumento = URL.createObjectURL(arquivo);
        if (arquivo.type.startsWith("image/")) {
            previaImagem.src = urlPreviaDocumento;
            previaImagem.hidden = false;
        } else if (arquivo.type === "application/pdf") {
            previaPdf.src = urlPreviaDocumento;
            previaPdf.hidden = false;
        }
    });

    formGemini.addEventListener("submit", async evento => {
        evento.preventDefault();
        const arquivo = formGemini.elements.arquivo.files[0];
        const mensagem = document.querySelector("#msg-gemini");
        if (!arquivo) { mensagem.textContent = "Selecione um PDF ou uma imagem."; return; }
        if (arquivo.size > 20 * 1024 * 1024) { mensagem.textContent = "Arquivo excede 20 MB."; return; }
        try {
            const base64 = await new Promise((resolve, reject) => {
                const leitor = new FileReader();
                leitor.onerror = () => reject(new Error("Não foi possível ler o arquivo."));
                leitor.onload = () => resolve(String(leitor.result).split(",")[1]);
                leitor.readAsDataURL(arquivo);
            });
            const resposta = await api("/api/gemini/interpretar", {
                method: "POST",
                body: JSON.stringify({ nome_arquivo: arquivo.name, mime_type: arquivo.type, conteudo_base64: base64 }),
            });
            const interpretacao = resposta.interpretacao;
            const camposAusentes = resposta.campos_ausentes || [];
            const alertas = resposta.alertas || [];
            interpretacaoIdPendente = resposta.interpretacao_id || null;
            document.querySelector("#resultado-gemini").hidden = false;
            document.querySelector("#resumo-alertas-gemini").textContent =
                `Proposta não autoritativa. Revise e corrija antes de salvar o rascunho. ` +
                `${camposAusentes.length} campo(s) ausente(s); ${alertas.length} alerta(s).`;
            document.querySelector("#campos-ausentes-gemini").innerHTML = camposAusentes.length
                ? camposAusentes.map(campo => `<li>${escaparHtml(campo)}</li>`).join("")
                : "<li>Nenhum campo obrigatório ausente na interpretação.</li>";
            document.querySelector("#alertas-gemini").innerHTML = alertas.length
                ? alertas.map(alerta => `<li><strong>${escaparHtml(alerta.tipo)}</strong> · ${escaparHtml(alerta.campo)}: ${escaparHtml(alerta.mensagem)}</li>`).join("")
                : "<li>Nenhuma divergência encontrada nos cadastros consultados.</li>";
            preencherDemanda({
                ...interpretacao,
                itens: (interpretacao.itens || []).map(item => ({
                    ...item, quantidade_por_carga: item.quantidade_por_carga ?? "",
                    peso_sacaria: item.peso_sacaria ?? "", capacidade_pallet: item.capacidade_pallet ?? "",
                })),
            });
            demandaAtualId = null;
            demandaAtual = null;
            document.querySelector("#revisao-demanda").hidden = true;
            mensagem.textContent = "Proposta preenchida. A revisão é obrigatória; confira alertas e complete os campos antes de salvar o rascunho.";
            formDemanda.scrollIntoView({ behavior: "smooth", block: "start" });
        } catch (erro) { mensagem.textContent = erro.message; }
    });
}

carregarDemandas();

async function carregarOrdens() {
    const tabela = document.querySelector("#tabela-ordens");
    if (!tabela) return;
    try {
        const ordens = await api("/api/ordens");
        tabela.innerHTML = ordens.map(o => `<tr>
            <td>${o.id}</td><td>${o.codigo}</td><td>${o.produto}</td>
            <td>${o.prioridade}</td><td>${o.status}</td>
            <td>
                <a class="button secondary" href="/lider/ordens/${o.id}">Abrir</a>
                <button class="button" data-gerar="${o.id}">Gerar tarefas</button>
            </td></tr>`).join("") || "<tr><td colspan='6'>Nenhuma OP.</td></tr>";
        tabela.querySelectorAll("button[data-gerar]").forEach(b => {
            b.addEventListener("click", async () => {
                try {
                    await api(`/api/ordens/${b.dataset.gerar}/gerar-tarefas`, { method: "POST", body: "{}" });
                    alert("Tarefas geradas.");
                } catch (e) { alert(e.message); }
            });
        });
    } catch (e) { tabela.innerHTML = `<tr><td colspan="6">Erro: ${e.message}</td></tr>`; }
}

carregarOrdens();

/* ---------------------------- OP Detalhes ---------------------------- */
const btnGerar = document.querySelector("#btn-gerar-tarefas");
if (btnGerar) {
    btnGerar.addEventListener("click", async () => {
        try {
            await api(`/api/ordens/${btnGerar.dataset.op}/gerar-tarefas`, { method: "POST", body: "{}" });
            document.querySelector("#msg-op").textContent = "Tarefas geradas.";
        } catch (e) { document.querySelector("#msg-op").textContent = e.message; }
    });
    document.querySelector("#btn-finalizar-op").addEventListener("click", async () => {
        try {
            await api(`/api/ordens/${btnGerar.dataset.op}/finalizar`, { method: "POST", body: "{}" });
            document.querySelector("#msg-op").textContent = "OP finalizada.";
        } catch (e) { document.querySelector("#msg-op").textContent = e.message; }
    });
    document.querySelector("#btn-cancelar-op").addEventListener("click", async () => {
        try {
            await api(`/api/ordens/${btnGerar.dataset.op}/cancelar`, { method: "POST", body: "{}" });
            document.querySelector("#msg-op").textContent = "OP cancelada.";
        } catch (e) { document.querySelector("#msg-op").textContent = e.message; }
    });
    (async () => {
        try {
            const tarefas = await api(`/api/tarefas?op_id=${btnGerar.dataset.op}`);
            document.querySelector("#lista-tarefas-op").innerHTML =
                tarefas.length ? tarefas.map(t =>
                    `<li>#${t.id} — ${t.papel === "empilhadeira" ? "Empilhadeira" : "Separador"} — ${t.material_codigo} — qtd ${t.quantidade} — ${t.status}</li>`
                ).join("") : "<li>Sem tarefas.</li>";
            const pallets = await api(`/api/pallets-op?op_id=${btnGerar.dataset.op}`);
            const tabelaPallets = document.querySelector("#tabela-pallets-op");
            tabelaPallets.innerHTML = pallets.map(p => `<tr>
                <td>#${p.id} / ${p.op_codigo}</td><td>${escaparHtml(p.material_codigo)}</td>
                <td>${p.sacarias}</td><td>${p.quantidade_pesagem}</td>
                <td>${p.quantidade_total} / ${p.capacidade}</td><td>${escaparHtml(p.status)}</td>
                <td>${escaparHtml(p.posicao_id)}</td>
                <td>${p.status === "bloqueado"
                    ? `<button class="button secondary" data-pallet-op="${p.id}" data-acao="desbloquear">Desbloquear</button>`
                    : p.status !== "movimentado" ? `<button class="button danger" data-pallet-op="${p.id}" data-acao="bloquear">Bloquear</button>` : "—"}</td>
            </tr>`).join("") || "<tr><td colspan='8'>Nenhum pallet planejado.</td></tr>";
            tabelaPallets.querySelectorAll("button[data-pallet-op]").forEach(botao => {
                botao.addEventListener("click", async () => {
                    try {
                        await api(`/api/pallets-op/${botao.dataset.palletOp}/${botao.dataset.acao}`, { method: "POST", body: "{}" });
                        window.location.reload();
                    } catch (erro) { alert(erro.message); }
                });
            });
        } catch (e) {}
    })();
}

/* ---------------------------- Tarefas ---------------------------- */
async function carregarTarefas() {
    const tabela = document.querySelector("#tabela-tarefas");
    if (!tabela) return;
    const status = document.querySelector("#filtro-status")?.value || "";
    const url = status ? `/api/tarefas?status=${status}` : "/api/tarefas";
    try {
        const tarefas = await api(url);
        tabela.innerHTML = tarefas.map(t => `<tr>
            <td>${t.id}</td><td>${texto(t.op_codigo)}</td>
            <td>${texto(t.papel)}${t.pallet_op_id ? ` · pallet #${t.pallet_op_id}` : ""}</td>
            <td>${texto(t.material_codigo)}</td><td>${t.quantidade}</td>
            <td>${texto(t.operador_nome)}</td><td>${t.status}</td><td>${t.prioridade}</td>
        </tr>`).join("") || "<tr><td colspan='8'>Sem tarefas.</td></tr>";
    } catch (e) { tabela.innerHTML = `<tr><td colspan="8">Erro: ${e.message}</td></tr>`; }
}
if (document.querySelector("#tabela-tarefas")) {
    document.querySelector("#refresh-tarefas").addEventListener("click", carregarTarefas);
    carregarTarefas();
}

/* ---------------------------- Movimentações ---------------------------- */
async function carregarMovimentacoes() {
    const tabela = document.querySelector("#tabela-movimentacoes");
    if (!tabela) return;
    try {
        const movs = await api("/api/movimentacoes");
        tabela.innerHTML = movs.map(m => `<tr>
            <td>${m.id}</td><td>${m.tipo}</td><td>${m.material_codigo}</td>
            <td>${m.quantidade}</td><td>${texto(m.operador_nome)}</td>
            <td>${texto(m.op_codigo)}</td><td>${m.criado_em}</td>
        </tr>`).join("") || "<tr><td colspan='7'>Sem movimentações.</td></tr>";
    } catch (e) { tabela.innerHTML = `<tr><td colspan="7">Erro: ${e.message}</td></tr>`; }
}
if (document.querySelector("#tabela-movimentacoes")) carregarMovimentacoes();

/* ---------------------------- Auditoria ---------------------------- */
async function carregarAuditoria() {
    const tabela = document.querySelector("#tabela-auditoria");
    if (!tabela) return;
    try {
        const registros = await api("/api/auditoria");
        tabela.innerHTML = registros.map(a => `<tr>
            <td>${a.id}</td><td>${a.entidade}</td><td>${texto(a.entidade_id)}</td>
            <td>${a.acao}</td><td>${a.criado_em}</td>
        </tr>`).join("") || "<tr><td colspan='5'>Sem registros.</td></tr>";
    } catch (e) { tabela.innerHTML = `<tr><td colspan="5">Erro: ${e.message}</td></tr>`; }
}
if (document.querySelector("#tabela-auditoria")) {
    document.querySelector("#refresh-auditoria").addEventListener("click", carregarAuditoria);
    carregarAuditoria();
}

/* ---------------------------- Dispositivos ---------------------------- */
async function carregarDispositivos() {
    const lista = document.querySelector("#lista-dispositivos");
    const tabela = document.querySelector("#tabela-eventos");
    if (!lista || !tabela) return;
    try {
        const disps = await api("/api/dispositivos");
        lista.innerHTML = disps.length
            ? disps.map(d => `<li>${d.dispositivo_id} — ${d.total_eventos} evento(s) — último: ${texto(d.ultimo_contato)}</li>`).join("")
            : "<li>Nenhum dispositivo identificado.</li>";
        const eventos = await api("/api/dispositivos/eventos");
        tabela.innerHTML = eventos.map(e => `<tr>
            <td>${e.id}</td><td>${e.dispositivo_id}</td><td>${texto(e.baia)}</td>
            <td>${texto(e.uid_rfid)}</td><td>${e.tipo_evento}</td><td>${e.criado_em}</td>
        </tr>`).join("") || "<tr><td colspan='6'>Sem eventos.</td></tr>";
    } catch (e) { tabela.innerHTML = `<tr><td colspan="6">Erro: ${e.message}</td></tr>`; }
}
if (document.querySelector("#tabela-eventos")) {
    document.querySelector("#refresh-dispositivos").addEventListener("click", carregarDispositivos);
    carregarDispositivos();
}

/* ---------------------------- Exceções ---------------------------- */
async function carregarExcecoes() {
    const tabela = document.querySelector("#tabela-excecoes");
    if (!tabela) return;
    try {
        const excecoes = await api("/api/excecoes");
        tabela.innerHTML = excecoes.map(e => `<tr>
            <td>${e.id}</td><td>${texto(e.operador_nome)}</td>
            <td>${texto(e.op_codigo)}</td><td>${texto(e.tarefa_id)}</td>
            <td>${e.motivo}</td><td>${e.status}</td>
            <td>${e.status === "aberta"
                ? `<button class="button" data-resolver="${e.id}">Resolver</button>`
                : texto(e.decisao)}</td>
        </tr>`).join("") || "<tr><td colspan='7'>Sem exceções.</td></tr>";
        tabela.querySelectorAll("button[data-resolver]").forEach(b => {
            b.addEventListener("click", async () => {
                const decisao = prompt("Decisão:");
                if (!decisao) return;
                try {
                    await api(`/api/excecoes/${b.dataset.resolver}/resolver`, {
                        method: "POST", body: JSON.stringify({ decisao }),
                    });
                    carregarExcecoes();
                } catch (e) { alert(e.message); }
            });
        });
    } catch (e) { tabela.innerHTML = `<tr><td colspan="7">Erro: ${e.message}</td></tr>`; }
}
if (document.querySelector("#tabela-excecoes")) {
    document.querySelector("#refresh-excecoes").addEventListener("click", carregarExcecoes);
    carregarExcecoes();
}

/* ---------------------------- Estoque ---------------------------- */
const formEntrada = document.querySelector("#form-entrada");
if (formEntrada) {
    formEntrada.addEventListener("submit", async ev => {
        ev.preventDefault();
        const dados = Object.fromEntries(new FormData(formEntrada));
        for (const k of Object.keys(dados)) if (dados[k] === "") delete dados[k];
        dados.material_id = Number(dados.material_id);
        dados.quantidade = Number(dados.quantidade);
        if (dados.lote_id) dados.lote_id = Number(dados.lote_id);
        if (dados.pallet_id) dados.pallet_id = Number(dados.pallet_id);
        if (dados.posicao_id) dados.posicao_id = Number(dados.posicao_id);
        const msg = document.querySelector("#msg-entrada");
        try {
            await api("/api/movimentacoes/entrada", { method: "POST", body: JSON.stringify(dados) });
            msg.textContent = "Entrada registrada.";
            formEntrada.reset();
            carregarEstoque();
        } catch (e) { msg.textContent = e.message; }
    });
    carregarEstoque();
}

async function carregarEstoque() {
    const alvo = document.querySelector("#tab-saldo-material");
    if (!alvo) return;
    try {
        const d = await api("/api/estoque");
        alvo.innerHTML = d.por_material.map(m => `<tr><td>${m.codigo}</td><td>${m.descricao}</td><td>${m.unidade}</td><td>${m.saldo}</td></tr>`).join("");
        document.querySelector("#tab-saldo-lote").innerHTML =
            d.por_lote.map(l => `<tr><td>${l.codigo}</td><td>${l.material_codigo}</td><td>${texto(l.validade)}</td><td>${l.saldo}</td></tr>`).join("");
        document.querySelector("#tab-pallets").innerHTML = d.pallets.map(p => `<tr>
            <td>${p.id}</td><td>${p.codigo}</td><td>${p.lote_codigo}</td>
            <td>${texto(p.posicao_codigo)}</td><td>${p.bloqueado ? "Sim" : "Não"}</td>
            <td>${p.bloqueado
                ? `<button class="button secondary" data-pallet="${p.id}" data-bloq="0">Desbloquear</button>`
                : `<button class="button danger" data-pallet="${p.id}" data-bloq="1">Bloquear</button>`}</td>
        </tr>`).join("");
        document.querySelector("#tab-pallets").querySelectorAll("button[data-pallet]").forEach(b => {
            b.addEventListener("click", async () => {
                const acao = b.dataset.bloq === "1" ? "bloquear" : "desbloquear";
                try {
                    await api(`/api/pallets/${b.dataset.pallet}/${acao}`, { method: "POST", body: "{}" });
                    carregarEstoque();
                } catch (e) { alert(e.message); }
            });
        });
        document.querySelector("#lista-posicoes").innerHTML =
            d.posicoes.map(p => `<li>#${p.id} ${p.codigo} — ${texto(p.descricao)}</li>`).join("") || "<li>Sem posições.</li>";
        document.querySelector("#lista-bloqueados").innerHTML =
            d.itens_bloqueados.map(i => `<li>Pallet ${i.codigo} (${i.material_codigo}/${i.lote_codigo})</li>`).join("") || "<li>Sem itens bloqueados.</li>";
        const ajustes = document.querySelector("#tab-ajustes-estoque");
        if (ajustes) ajustes.innerHTML = d.ajustes.map(a => `<tr>
            <td>${escaparHtml(a.criado_em)}</td>
            <td>${escaparHtml(a.material_codigo)} / ${escaparHtml(a.lote_anterior_codigo || a.lote_codigo)}${a.lote_anterior_codigo ? ` → ${escaparHtml(a.lote_codigo)}` : ""} / ${escaparHtml(a.pallet_codigo)}</td>
            <td>${escaparHtml(a.tipo)}</td><td>${a.quantidade_antes}</td>
            <td>${a.quantidade_ajuste}</td><td>${a.quantidade_depois}</td>
            <td>${escaparHtml(a.responsavel)}</td><td>${escaparHtml(a.motivo)}</td>
        </tr>`).join("") || "<tr><td colspan='8'>Sem ajustes.</td></tr>";
    } catch (e) {}
}
if (document.querySelector("#tab-saldo-material")) {
    document.querySelector("#refresh-estoque").addEventListener("click", carregarEstoque);
}

const formAjusteEstoque = document.querySelector("#form-ajuste-estoque");
if (formAjusteEstoque) {
    formAjusteEstoque.addEventListener("submit", async evento => {
        evento.preventDefault();
        const dados = Object.fromEntries(new FormData(formAjusteEstoque));
        for (const chave of Object.keys(dados)) if (dados[chave] === "") delete dados[chave];
        for (const chave of ["material_id", "lote_id", "pallet_id", "posicao_anterior_id", "posicao_id"]) {
            if (dados[chave]) dados[chave] = Number(dados[chave]);
        }
        dados.quantidade_ajuste = Number(dados.quantidade_ajuste);
        const mensagem = document.querySelector("#msg-ajuste-estoque");
        try {
            const ajuste = await api("/api/ajustes-estoque", { method: "POST", body: JSON.stringify(dados) });
            mensagem.textContent = `Ajuste #${ajuste.id}: ${ajuste.quantidade_antes} + ${ajuste.quantidade_ajuste} = ${ajuste.quantidade_depois}`;
            formAjusteEstoque.reset();
            carregarEstoque();
        } catch (erro) { mensagem.textContent = erro.message; }
    });
}

/* ---------------------------- Dashboard periódico ---------------------------- */
if (document.querySelector("#dashboard-cards")) {
    carregarDashboard();
    setInterval(carregarDashboard, 5000);
}
