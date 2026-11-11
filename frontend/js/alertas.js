montarTopo("alertas.html");
preencherBairros(document.getElementById("bairro"));

document.getElementById("form").addEventListener("submit", async (ev) => {
  ev.preventDefault();
  const msg = document.getElementById("msg");
  msg.className = "";
  try {
    const r = await api("/api/inscricoes", {
      method: "POST",
      body: JSON.stringify({
        bairro: document.getElementById("bairro").value,
        telefone: document.getElementById("telefone").value,
        aceite_lgpd: document.getElementById("aceite").checked,
      }),
    });
    msg.className = "ok";
    msg.textContent = `${r.mensagem} Número cadastrado: ${r.telefone}.`;
    ev.target.reset();
  } catch (e) {
    msg.className = "erro";
    msg.textContent = e.message;
  }
});

async function carregar() {
  try {
    const alertas = await api("/api/alertas?limite=20");
    const ul = document.getElementById("lista");
    ul.innerHTML = alertas.length ? alertas.map((a) => `
      <li class="${a.ativo ? "ativo" : ""}">
        <div style="display:flex;justify-content:space-between;gap:8px;flex-wrap:wrap">
          <strong>${esc(a.bairro)}</strong>${selo(a.nivel)}
        </div>
        <p style="margin:6px 0">${esc(a.mensagem)}</p>
        <span class="ajuda">${fmtData(a.criado_em)} · ${a.ativo ? "ATIVO" : "encerrado " + fmtData(a.encerrado_em)} · ${a.destinatarios} SMS enviados</span>
      </li>`).join("") : "<li>Nenhum alerta emitido. Tudo tranquilo por enquanto.</li>";
  } catch (e) {
    document.getElementById("lista").innerHTML = `<li class="erro">${esc(e.message)}</li>`;
  }
}
carregar();
setInterval(carregar, 5000);
