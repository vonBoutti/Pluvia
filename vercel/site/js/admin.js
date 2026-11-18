montarTopo("admin.html");
const SEV = { alta: "emergencia", media: "atencao", baixa: "normal" };

function mostrarPainel(logado) {
  document.getElementById("login").classList.toggle("oculto", logado);
  document.getElementById("painel").classList.toggle("oculto", !logado);
  if (logado) carregar();
}

document.getElementById("login").addEventListener("submit", async (e) => {
  e.preventDefault();
  const erro = document.getElementById("erro-login");
  erro.textContent = "";
  try {
    const r = await api("/api/auth/login", { method: "POST", body: JSON.stringify({
      usuario: document.getElementById("usuario").value, senha: document.getElementById("senha").value }) });
    sessionStorage.setItem("token", r.access_token);
    document.getElementById("senha").value = "";
    mostrarPainel(true);
  } catch (er) { erro.textContent = er.message; }
});

document.getElementById("sair").addEventListener("click", () => { sessionStorage.removeItem("token"); mostrarPainel(false); });
document.getElementById("reset").addEventListener("click", async () => {
  if (!confirm("Apagar leituras e alertas da demonstração?")) return;
  await api("/api/admin/reset", { method: "POST", auth: true });
  carregar();
});

async function mudarStatus(id, status) {
  await api(`/api/relatos/${id}`, { method: "PATCH", auth: true, body: JSON.stringify({ status }) });
}

async function carregar() {
  try {
    const [relatos, alertas, mon] = await Promise.all([
      api("/api/relatos", { auth: true }), api("/api/alertas?limite=50"), api("/api/metricas"),
    ]);
    document.getElementById("monitor").innerHTML = [
      [mon.negocio.alertas_ativos, "Alertas ativos"], [mon.negocio.relatos, "Relatos recebidos"],
      [mon.negocio.leituras, "Leituras IoT"], [`${num(mon.latencia_media_ms, 1)} ms`, "Latência média da API"],
      [`${Math.floor(mon.uptime_s / 60)} min`, "Tempo no ar"],
    ].map(([v, r]) => `<div class="cartao kpi"><div class="valor">${v}</div><div class="rotulo">${r}</div></div>`).join("");

    document.getElementById("t-relatos").innerHTML = `
      <thead><tr><th>#</th><th>Quando</th><th>Bairro</th><th>Relato</th><th>IA</th><th>Órgão / prazo</th><th>Status</th></tr></thead>
      <tbody>${relatos.map((r) => `<tr>
        <td>${r.id}</td><td>${fmtData(r.criado_em)}</td><td>${esc(r.bairro)}</td><td>${esc(r.texto)}</td>
        <td><span class="selo n-${SEV[r.severidade]}">${esc(r.severidade)}</span><br>
            <span class="ajuda">${esc(r.categoria)} · ${Math.round(r.confianca * 100)}%${r.revisao_humana ? " · revisar" : ""}${r.regra_urgencia ? " · regra urgência" : ""}</span></td>
        <td>${esc(r.orgao)}<br><span class="ajuda">${esc(r.prazo)}</span></td>
        <td><label class="oculto" for="st-${r.id}">Status</label><select id="st-${r.id}" data-id="${r.id}">
          ${["aberto", "em_atendimento", "resolvido"].map((s) => `<option ${s === r.status ? "selected" : ""}>${s}</option>`).join("")}
        </select></td></tr>`).join("") || '<tr><td colspan="7">Nenhum relato.</td></tr>'}</tbody>`;
    document.querySelectorAll("#t-relatos select").forEach((s) =>
      s.addEventListener("change", () => mudarStatus(s.dataset.id, s.value).catch((e) => alert(e.message))));

    document.getElementById("t-alertas").innerHTML = `
      <thead><tr><th>Quando</th><th>Bairro</th><th>Nível</th><th>Prob.</th><th>Motivo (regras)</th><th>Ação recomendada</th><th>Situação</th></tr></thead>
      <tbody>${alertas.map((a) => `<tr><td>${fmtData(a.criado_em)}</td><td>${esc(a.bairro)}</td><td>${selo(a.nivel)}</td>
        <td>${Math.round(a.probabilidade * 100)}%</td><td class="ajuda">${esc(a.motivo)}</td><td>${esc(a.acao_defesa_civil)}</td>
        <td>${a.ativo ? "<strong>ativo</strong>" : "encerrado"}</td></tr>`).join("") || '<tr><td colspan="7">Nenhum alerta.</td></tr>'}</tbody>`;
  } catch (e) {
    if (e.status === 401) { sessionStorage.removeItem("token"); mostrarPainel(false); document.getElementById("erro-login").textContent = "Sessão expirada. Entre novamente."; }
  }
}

mostrarPainel(!!sessionStorage.getItem("token"));
setTimeout(() => repetir(() => (sessionStorage.getItem("token") ? carregar() : null), 6000), 6000);
