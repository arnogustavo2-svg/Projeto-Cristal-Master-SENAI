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

function matriculaAtual() { return localStorage.getItem("aai_matricula") || ""; }

/* ---------------------------- Acesso ---------------------------- */
const formAcesso = document.querySelector("#form-acesso");
if (formAcesso) {
    formAcesso.addEventListener("submit", async ev => {
        ev.preventDefault();
        const dados = Object.fromEntries(new FormData(formAcesso));
        const msg = document.querySelector("#msg-acesso");
        try {
            const r = await api("/api/operador/identificar", {
                method: "POST", body: JSON.stringify(dados),
            });
            localStorage.setItem("aai_matricula", r.operador.matricula);
            localStorage.setItem("aai_nome", r.operador.nome);
            window.location.href = "/operador/inicio";
        } catch (e) { msg.textContent = e.message; }
    });
}

/* ---------------------------- Início ---------------------------- */
if (document.querySelector("#saudacao")) {
    const matricula = matriculaAtual();
    if (!matricula) { window.location.href = "/operador"; }
    else {
        document.querySelector("#saudacao").textContent = `Olá, ${localStorage.getItem("aai_nome") || matricula}`;
        document.querySelector("#matricula-operador").textContent = matricula;
        (async () => {
            try {
                const r = await api(`/api/operador/tarefas?matricula=${encodeURIComponent(matricula)}`);
                document.querySelector("#cont-pendentes").textContent =
                    r.tarefas.filter(t => t.status === "pendente").length;
                document.querySelector("#cont-andamento").textContent =
                    r.tarefas.filter(t => t.status === "em_andamento").length;
                document.querySelector("#cont-disponiveis").textContent = r.disponiveis.length;
                document.querySelector("#alertas-operacao").innerHTML =
                    r.disponiveis.length
                        ? r.disponiveis.map(t => `<li>Nova tarefa disponível #${t.id} (${t.material_codigo})</li>`).join("")
                        : "<li>Sem alertas.</li>";
            } catch (e) {
                document.querySelector("#alertas-operacao").innerHTML = `<li>${e.message}</li>`;
            }
        })();
        document.querySelector("#btn-sair").addEventListener("click", () => {
            localStorage.removeItem("aai_matricula");
            localStorage.removeItem("aai_nome");
            window.location.href = "/operador";
        });
    }
}

/* ---------------------------- Lista de tarefas ---------------------------- */
async function carregarMinhasTarefas() {
    const matricula = matriculaAtual();
    if (!matricula) { window.location.href = "/operador"; return; }
    try {
        const r = await api(`/api/operador/tarefas?matricula=${encodeURIComponent(matricula)}`);
        const renderLinha = t => `<tr>
            <td>${t.id}</td><td>${t.op_codigo}</td><td>${t.papel === "empilhadeira" ? "Empilhadeira" : "Separador"}</td>
            <td>${t.material_codigo} — ${t.material_descricao}</td>
            <td>${t.quantidade}</td><td>${t.prioridade}</td><td>${t.status}</td>
            <td><a class="button" href="/operador/tarefas/${t.id}">Abrir</a></td>
        </tr>`;
        const minhas = document.querySelector("#tabela-minhas");
        const disponiveis = document.querySelector("#tabela-disponiveis");
        if (minhas) minhas.innerHTML = r.tarefas.length ? r.tarefas.map(renderLinha).join("") : "<tr><td colspan='8'>Sem tarefas.</td></tr>";
        if (disponiveis) disponiveis.innerHTML = r.disponiveis.length ? r.disponiveis.map(renderLinha).join("") : "<tr><td colspan='8'>Sem tarefas disponíveis.</td></tr>";
    } catch (e) {
        document.querySelector("#msg-tarefas").textContent = e.message;
    }
}
if (document.querySelector("#tabela-minhas")) carregarMinhasTarefas();

/* ---------------------------- Detalhe de tarefa ---------------------------- */
const formExec = document.querySelector("#form-execucao");
if (formExec) {
    const id = formExec.dataset.id;
    const matricula = matriculaAtual();
    document.querySelector("#btn-iniciar").addEventListener("click", async () => {
        try {
            await api(`/api/operador/tarefas/${id}/iniciar`, {
                method: "POST", body: JSON.stringify({ matricula }),
            });
            document.querySelector("#msg-execucao").textContent = "Tarefa iniciada.";
        } catch (e) { document.querySelector("#msg-execucao").textContent = e.message; }
    });
    formExec.addEventListener("submit", async ev => {
        ev.preventDefault();
        const dados = Object.fromEntries(new FormData(formExec));
        const payload = {
            matricula,
            quantidade_retirada: Number(dados.quantidade_retirada),
            pallet_id: dados.pallet_id ? Number(dados.pallet_id) : null,
            posicao_id: dados.posicao_id ? Number(dados.posicao_id) : null,
            observacao: dados.observacao || null,
        };
        try {
            await api(`/api/operador/tarefas/${id}/concluir`, {
                method: "POST", body: JSON.stringify(payload),
            });
            document.querySelector("#msg-execucao").textContent = "Tarefa concluída.";
            window.location.href = "/operador/confirmacao";
        } catch (e) { document.querySelector("#msg-execucao").textContent = e.message; }
    });

    async function carregarPalletsSeparacao() {
        const container = document.querySelector("#pallets-separacao");
        if (!container) return;
        try {
            const pallets = await api(`/api/pallets-op?op_id=${container.dataset.op}`);
            const destaTarefa = pallets.filter(p => String(p.item_id) === container.dataset.item);
            container.innerHTML = destaTarefa.map(p => `<section class="pallet-linha">
                <strong>Pallet #${p.id} · ${p.status}</strong>
                <p>${p.sacarias} sacaria(s) + ${p.quantidade_pesagem} em pesagem = ${p.quantidade_total} / ${p.capacidade}</p>
                ${p.status === "previsto" && Math.abs(p.quantidade_total - p.capacidade) < 0.000001
                    ? `<label>Posição após fechamento (ID)<input type="number" min="1" data-posicao-pallet="${p.id}"></label>
                       <button type="button" class="button" data-fechar-pallet="${p.id}" data-sacarias="${p.sacarias}" data-pesagem="${p.quantidade_pesagem}">Confirmar fechamento</button>`
                    : p.status === "em_montagem" ? "<p>Em montagem: não disponível para empilhadeira.</p>" : ""}
            </section>`).join("") || "<p>Sem pallets planejados.</p>";
            container.querySelectorAll("button[data-fechar-pallet]").forEach(botao => {
                botao.addEventListener("click", async () => {
                    const posicao = container.querySelector(`[data-posicao-pallet="${botao.dataset.fecharPallet}"]`).value;
                    const payload = {
                        matricula: matriculaAtual(),
                        sacarias: Number(botao.dataset.sacarias),
                        quantidade_pesagem: Number(botao.dataset.pesagem),
                        posicao_id: posicao ? Number(posicao) : null,
                    };
                    try {
                        await api(`/api/pallets-op/${botao.dataset.fecharPallet}/fechar`, {
                            method: "POST", body: JSON.stringify(payload),
                        });
                        await carregarPalletsSeparacao();
                        document.querySelector("#msg-execucao").textContent = "Pallet fechado; tarefa de empilhadeira criada.";
                    } catch (erro) { document.querySelector("#msg-execucao").textContent = erro.message; }
                });
            });
        } catch (erro) { container.textContent = erro.message; }
    }
    carregarPalletsSeparacao();
}

const formMovimentarPallet = document.querySelector("#form-movimentar-pallet");
if (formMovimentarPallet) {
    const id = formMovimentarPallet.dataset.id;
    const matricula = matriculaAtual();
    document.querySelector("#btn-iniciar").addEventListener("click", async () => {
        try {
            await api(`/api/operador/tarefas/${id}/iniciar`, {
                method: "POST", body: JSON.stringify({ matricula }),
            });
            document.querySelector("#msg-execucao").textContent = "Movimentação iniciada.";
        } catch (erro) { document.querySelector("#msg-execucao").textContent = erro.message; }
    });
    formMovimentarPallet.addEventListener("submit", async evento => {
        evento.preventDefault();
        const dados = Object.fromEntries(new FormData(formMovimentarPallet));
        try {
            await api(`/api/operador/tarefas/${id}/movimentar`, {
                method: "POST", body: JSON.stringify({
                    matricula, posicao_destino_id: Number(dados.posicao_destino_id),
                }),
            });
            window.location.href = "/operador/confirmacao";
        } catch (erro) { document.querySelector("#msg-execucao").textContent = erro.message; }
    });
}

/* ---------------------------- Exceção ---------------------------- */
const formExcecao = document.querySelector("#form-excecao");
if (formExcecao) {
    formExcecao.addEventListener("submit", async ev => {
        ev.preventDefault();
        const dados = Object.fromEntries(new FormData(formExcecao));
        const payload = {
            tarefa_id: dados.tarefa_id ? Number(dados.tarefa_id) : null,
            matricula: matriculaAtual(),
            motivo: dados.motivo,
            observacao: dados.observacao || null,
        };
        const msg = document.querySelector("#msg-excecao");
        try {
            await api("/api/excecoes", { method: "POST", body: JSON.stringify(payload) });
            msg.textContent = "Exceção registrada.";
            formExcecao.reset();
        } catch (e) { msg.textContent = e.message; }
    });
}
