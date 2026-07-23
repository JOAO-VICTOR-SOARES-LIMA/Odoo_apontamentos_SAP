(function () {
  "use strict";

  let pollTimer = null;

  const $ = (id) => document.getElementById(id);

  // ── Tema ──────────────────────────────────────────────────
  function aplicarBotaoTema() {
    const isDark = document.documentElement.getAttribute("data-theme") === "dark";
    $("btnThemeToggle").textContent = isDark ? "🌙" : "🌕";
  }
  $("btnThemeToggle").addEventListener("click", () => {
    const atual = document.documentElement.getAttribute("data-theme");
    const novo = atual === "dark" ? "light" : "dark";
    document.documentElement.setAttribute("data-theme", novo);
    localStorage.setItem("app_theme_mode", novo);
    aplicarBotaoTema();
  });
  aplicarBotaoTema();

  // ── Ambiente ─────────────────────────────────────────────
  // Essa app so opera contra producao - sem seletor, sempre "prod".
  const AMBIENTE = "prod";

  // ── Formatação de data/hora ───────────────────────────────
  function formatarDataHora(iso) {
    if (!iso) return "";
    const d = new Date(iso);
    if (isNaN(d.getTime())) return iso;
    return d.toLocaleString("pt-BR", {
      day: "2-digit", month: "2-digit", year: "numeric",
      hour: "2-digit", minute: "2-digit", second: "2-digit",
    });
  }

  (function preencherDataOntem() {
    const ontem = new Date();
    ontem.setDate(ontem.getDate() - 1);
    $("dataReferencia").value = ontem.toISOString().slice(0, 10);
  })();

  function mostrarErro(msg) {
    const el = $("avisoErro");
    el.textContent = msg;
    el.classList.remove("hidden");
  }

  // ── Modo manual/automatico ──────────────────────────────────
  function renderModo(modo) {
    $("chkModoAutomatico").checked = modo === "automatico";
    $("modoLabel").textContent = modo === "automatico" ? "Automático" : "Manual";
  }

  async function carregarModo() {
    try {
      const resp = await fetch("/api/modo");
      const data = await resp.json();
      renderModo(data.modo);
    } catch (e) { /* mantem default "manual" do HTML */ }
  }

  $("chkModoAutomatico").addEventListener("change", async (ev) => {
    const novoModo = ev.target.checked ? "automatico" : "manual";
    ev.target.disabled = true;
    try {
      const resp = await fetch("/api/modo", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ modo: novoModo }),
      });
      const data = await resp.json();
      if (!resp.ok) throw new Error(data.detail || "Erro ao alterar o modo");
      renderModo(data.modo);
    } catch (e) {
      mostrarErro(e.message);
      ev.target.checked = !ev.target.checked;
    } finally {
      ev.target.disabled = false;
    }
  });

  // ── Preview (só leitura, sem senha) ────────────────────────
  $("btnVerPreview").addEventListener("click", verPreview);

  function kpiClasse(status) {
    if (status === "pronto_para_envio") return "ok";
    if (status.startsWith("erro_")) return "crit";
    if (status === "ja_existe_sap" || status === "pulado_zero_horas") return "";
    return "amber";
  }

  function renderKpis(contagem) {
    const row = $("kpiRow");
    row.innerHTML = "";
    Object.entries(contagem).forEach(([status, qtd]) => {
      const div = document.createElement("div");
      div.className = "kpi " + kpiClasse(status);
      div.innerHTML = `
        <div class="rail"></div>
        <div class="lab">${status}</div>
        <div class="val">${qtd}</div>
      `;
      row.appendChild(div);
    });
  }

  function renderTabelaPreview(preview) {
    const body = $("gridBody");
    body.innerHTML = "";
    if (!preview.length) {
      body.innerHTML = '<tr><td colspan="10" class="empty-state">Nenhum apontamento validado nessa data.</td></tr>';
      return;
    }
    preview.forEach((row) => {
      const tr = document.createElement("tr");
      tr.innerHTML = `
        <td>${row.linha_excel}</td>
        <td>${row.colaborador ?? ""}</td>
        <td>${row.data ?? ""}</td>
        <td>${row.projeto ?? ""}</td>
        <td>${row.idsap ?? ""}</td>
        <td>${row.tarefa ?? ""}</td>
        <td class="col-valor">${row.horas ?? ""}</td>
        <td>${row.employee_id_sap ?? ""}</td>
        <td><span class="status-chip status-${row.status}">${row.status}</span></td>
        <td>${row.motivo ?? ""}</td>
      `;
      body.appendChild(tr);
    });
  }

  async function verPreview() {
    $("avisoErro").classList.add("hidden");
    $("avisoCarregando").classList.remove("hidden");
    $("btnVerPreview").disabled = true;

    try {
      const resp = await fetch("/api/preview", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          ambiente: AMBIENTE,
          data: $("dataReferencia").value || null,
        }),
      });
      const data = await resp.json();
      if (!resp.ok) throw new Error(data.detail || "Erro ao gerar preview");

      renderKpis(data.contagem);
      renderTabelaPreview(data.preview);
      $("previewSection").classList.remove("hidden");
      $("kpiRow").classList.remove("hidden");
    } catch (e) {
      mostrarErro(e.message);
    } finally {
      $("avisoCarregando").classList.add("hidden");
      $("btnVerPreview").disabled = false;
    }
  }

  // ── Rodar agora (exige senha da TI) ─────────────────────────
  $("btnRodarAgora").addEventListener("click", rodarAgora);

  async function rodarAgora() {
    $("avisoErro").classList.add("hidden");
    $("btnRodarAgora").disabled = true;

    try {
      const resp = await fetch("/api/rodar-agora", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          ambiente: AMBIENTE,
          data: $("dataReferencia").value || null,
        }),
      });
      const data = await resp.json();
      if (!resp.ok) throw new Error(data.detail || "Erro ao iniciar execução");

      $("progressoWrap").classList.remove("hidden");
      $("resumoEnvio").classList.add("hidden");
      $("logBox").textContent = "";
      $("progressBar").style.width = "0%";
      iniciarPolling();
    } catch (e) {
      mostrarErro(e.message);
      $("btnRodarAgora").disabled = false;
    }
  }

  function iniciarPolling() {
    if (pollTimer) clearInterval(pollTimer);
    pollTimer = setInterval(async () => {
      const resp = await fetch("/api/progresso");
      const p = await resp.json();

      const pct = p.total > 0 ? (p.pos / p.total) * 100 : 0;
      $("progressBar").style.width = pct + "%";
      $("logBox").textContent = p.logs.join("\n");
      $("logBox").scrollTop = $("logBox").scrollHeight;

      if (!p.em_andamento) {
        clearInterval(pollTimer);
        pollTimer = null;
        $("btnRodarAgora").disabled = false;

        if (p.erro) {
          mostrarErro(p.erro);
        } else if (p.resumo) {
          const r = $("resumoEnvio");
          r.textContent = `Execução ${p.execucao_id} concluída: ${p.resumo.total_enviadas} enviadas, ` +
            `${p.resumo.total_ja_existentes} já existentes, ${p.resumo.total_puladas} puladas, ` +
            `${p.resumo.total_erros} erros.`;
          r.classList.remove("hidden");
        }
        carregarHistorico();
      }
    }, 1200);
  }

  // ── Histórico (so leitura, sem senha) ────────────────────────
  $("btnAtualizarHistorico").addEventListener("click", carregarHistorico);

  $("btnExportarHistorico").addEventListener("click", () => {
    const params = new URLSearchParams();
    if ($("exportDataInicio").value) params.set("data_inicio", $("exportDataInicio").value);
    if ($("exportDataFim").value) params.set("data_fim", $("exportDataFim").value);
    const qs = params.toString();
    window.open("/api/historico/exportar" + (qs ? "?" + qs : ""), "_blank");
  });

  async function carregarHistorico() {
    try {
      const resp = await fetch("/api/historico");
      const data = await resp.json();
      const body = $("historicoBody");
      body.innerHTML = "";

      if (!data.execucoes || data.execucoes.length === 0) {
        body.innerHTML = '<tr><td colspan="13" class="empty-state">Sem execuções ainda.</td></tr>';
        return;
      }

      data.execucoes.forEach((e) => {
        const tr = document.createElement("tr");
        const temErros = (e.total_erros ?? 0) > 0;
        tr.innerHTML = `
          <td>${e.id}</td>
          <td>${e.origem ?? ""}</td>
          <td>${e.ambiente ?? ""}</td>
          <td>${e.arquivo_origem ?? ""}</td>
          <td>${e.status ?? ""}</td>
          <td class="col-valor">${e.total_linhas ?? ""}</td>
          <td class="col-valor">${e.total_enviadas ?? ""}</td>
          <td class="col-valor">${e.total_ja_existentes ?? ""}</td>
          <td class="col-valor">${e.total_puladas ?? ""}</td>
          <td class="col-valor">${e.total_erros ?? ""}</td>
          <td>${formatarDataHora(e.iniciado_em)}</td>
          <td>${formatarDataHora(e.finalizado_em)}</td>
          <td>
            <button class="btn-link" data-execucao="${e.id}" ${temErros ? "" : "disabled"}>Ver erros${temErros ? ` (${e.total_erros})` : ""}</button>
            <a class="btn-link" href="/api/historico/${e.id}/exportar" target="_blank" rel="noopener">⬇ Exportar Excel</a>
          </td>
        `;
        const btn = tr.querySelector("button.btn-link");
        if (temErros) btn.addEventListener("click", () => verErros(e.id));
        body.appendChild(tr);
      });
    } catch (e) {
      $("historicoBody").innerHTML = '<tr><td colspan="13" class="empty-state">Erro ao carregar histórico.</td></tr>';
    }
  }

  // ── Copiar texto (Motivo, Resposta do SAP, JSON) ─────────
  function escapeHtml(str) {
    return String(str).replace(/[&<>"']/g, (c) => ({
      "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
    }[c]));
  }

  function celulaTextoCopiavel(texto) {
    if (!texto) return "";
    return `<div class="td-texto-copiavel"><span class="texto">${escapeHtml(texto)}</span><button class="btn-copy" type="button" title="Copiar">⧉</button></div>`;
  }

  async function copiarTexto(botao, texto) {
    try {
      await navigator.clipboard.writeText(texto);
      botao.classList.add("copied");
      const original = botao.textContent;
      botao.textContent = "✓";
      setTimeout(() => { botao.classList.remove("copied"); botao.textContent = original; }, 1200);
    } catch (e) { /* clipboard indisponivel nesse contexto - ignora */ }
  }

  function ativarBotoesCopia(container) {
    container.querySelectorAll(".btn-copy").forEach((btn) => {
      const texto = btn.previousElementSibling.textContent;
      btn.addEventListener("click", () => copiarTexto(btn, texto));
    });
  }

  // ── Modal de erros ────────────────────────────────────────
  async function verErros(execucaoId) {
    $("modalTitle").textContent = `Erros da execução ${execucaoId}`;
    $("modalBody").innerHTML = '<tr><td colspan="10" class="empty-state">Carregando...</td></tr>';
    $("modalOverlay").classList.remove("hidden");

    try {
      const resp = await fetch(`/api/historico/${execucaoId}/linhas?apenas_erros=true`);
      const data = await resp.json();
      const body = $("modalBody");
      body.innerHTML = "";

      if (!data.linhas || data.linhas.length === 0) {
        body.innerHTML = '<tr><td colspan="10" class="empty-state">Nenhuma linha com erro nessa execução.</td></tr>';
        return;
      }

      data.linhas.forEach((l) => {
        const sapMsg = l.sap_response?.error?.message?.value
          || (l.sap_response ? JSON.stringify(l.sap_response) : "");
        const requestJson = l.sap_request ? JSON.stringify(l.sap_request) : "";
        const tr = document.createElement("tr");
        tr.innerHTML = `
          <td>${l.linha_excel}</td>
          <td>${l.colaborador ?? ""}</td>
          <td>${l.data ?? ""}</td>
          <td>${l.projeto ?? ""}</td>
          <td>${l.idsap ?? ""}</td>
          <td class="col-valor">${l.horas ?? ""}</td>
          <td><span class="status-chip status-${l.status}">${l.status}</span></td>
          <td class="td-expandivel">${celulaTextoCopiavel(l.motivo)}</td>
          <td>${requestJson ? `<button class="btn-link" data-json='${requestJson.replace(/'/g, "&#39;")}'>Ver</button>` : ""}</td>
          <td class="td-expandivel">${celulaTextoCopiavel(sapMsg)}</td>
        `;
        const btnJson = tr.querySelector("[data-json]");
        if (btnJson) {
          btnJson.addEventListener("click", () => {
            abrirModalJson(`Payload enviado — linha ${l.linha_excel}`, JSON.parse(btnJson.dataset.json));
          });
        }
        ativarBotoesCopia(tr);
        body.appendChild(tr);
      });
    } catch (e) {
      $("modalBody").innerHTML = `<tr><td colspan="10" class="empty-state">Erro ao carregar: ${e.message}</td></tr>`;
    }
  }

  $("modalClose").addEventListener("click", () => $("modalOverlay").classList.add("hidden"));
  $("modalOverlay").addEventListener("click", (ev) => {
    if (ev.target.id === "modalOverlay") $("modalOverlay").classList.add("hidden");
  });

  // ── Modal de JSON ─────────────────────────────────────────
  function abrirModalJson(titulo, payloadObjOuTexto) {
    const texto = typeof payloadObjOuTexto === "string"
      ? payloadObjOuTexto
      : JSON.stringify(payloadObjOuTexto, null, 2);
    $("jsonModalTitle").textContent = titulo;
    $("jsonModalContent").textContent = texto;
    $("jsonModalOverlay").classList.remove("hidden");
  }

  $("jsonModalCopy").addEventListener("click", () => copiarTexto($("jsonModalCopy"), $("jsonModalContent").textContent));
  $("jsonModalClose").addEventListener("click", () => $("jsonModalOverlay").classList.add("hidden"));
  $("jsonModalOverlay").addEventListener("click", (ev) => {
    if (ev.target.id === "jsonModalOverlay") $("jsonModalOverlay").classList.add("hidden");
  });

  // ── Bootstrap ─────────────────────────────────────────────
  carregarModo();
  carregarHistorico();
})();
