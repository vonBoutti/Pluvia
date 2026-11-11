montarTopo("relatar.html");

const NOMES_CAT = { alagamento: "Alagamento", bueiro_entupido: "Bueiro entupido", deslizamento: "Deslizamento de terra",
  queda_arvore: "Queda de árvore", outros: "Outros" };
const NOMES_SEV = { alta: ["emergencia", "Alta"], media: ["atencao", "Média"], baixa: ["normal", "Baixa"] };

const form = document.getElementById("form");
const texto = document.getElementById("texto");
preencherBairros(document.getElementById("bairro"));
texto.addEventListener("input", () => { document.getElementById("contador").textContent = texto.value.length; });

form.addEventListener("submit", async (ev) => {
  ev.preventDefault();
  const erro = document.getElementById("erro");
  erro.textContent = "";
  if (texto.value.trim().length < 10) { erro.textContent = "Descreva o problema com pelo menos 10 caracteres."; texto.focus(); return; }
  const btn = document.getElementById("enviar");
  btn.disabled = true; btn.textContent = "Analisando…";
  try {
    const r = await api("/api/relatos", { method: "POST", body: JSON.stringify({ bairro: form.bairro.value, texto: texto.value }) });
    const t = r.triagem;
    document.getElementById("vazio").classList.add("oculto");
    document.getElementById("saida").classList.remove("oculto");
    document.getElementById("protocolo").textContent = `Relato recebido! Protocolo nº ${r.id}`;
    document.getElementById("r-cat").textContent = NOMES_CAT[t.categoria];
    const [cls, nome] = NOMES_SEV[t.severidade];
    document.getElementById("r-sev").innerHTML = `<span class="selo n-${cls}">${nome}</span>`;
    document.getElementById("r-orgao").textContent = t.orgao_responsavel;
    document.getElementById("r-prazo").textContent = t.prazo_atendimento;
    document.getElementById("r-conf").textContent = `${Math.round(t.confianca * 100)}%`;
    document.getElementById("r-tempo").textContent = `${num(r.tempo_triagem_ms, 1)} ms (triagem manual: ~2 min)`;
    const extras = [];
    if (t.regra_urgencia_aplicada) extras.push("Palavras de risco à vida detectadas: urgência elevada automaticamente.");
    if (t.revisao_humana) extras.push("Confiança baixa: um atendente vai revisar a classificação.");
    if (r.agente && r.agente.acao === "criar") extras.push(`Seu relato ajudou a disparar um ALERTA para ${form.bairro.value}.`);
    document.getElementById("r-extra").textContent = extras.join(" ");
    texto.value = ""; document.getElementById("contador").textContent = "0";
  } catch (e) {
    erro.textContent = e.message;
  } finally {
    btn.disabled = false; btn.textContent = "Enviar relato";
  }
});
