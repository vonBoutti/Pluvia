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
    msg.textContent = `Pronto! O número ${r.telefone} vai receber os avisos de ${r.bairro}.`;
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
        <div class="linha"><strong>${esc(a.bairro)}</strong>${selo(a.nivel)}</div>
        <p>${esc(a.mensagem)}</p>
        <span class="ajuda">${fmtData(a.criado_em)} · ${a.ativo ? "<b>valendo agora</b>" : "encerrado " + fmtData(a.encerrado_em)} · ${a.destinatarios} SMS enviados</span>
      </li>`).join("") : `<li class="vazio">${icone("ok")}<div>Nenhum aviso por enquanto. Tudo tranquilo!</div></li>`;
  } catch (e) {
    document.getElementById("lista").innerHTML = `<li class="erro">${esc(e.message)}</li>`;
  }
}
repetir(carregar, 5000);
