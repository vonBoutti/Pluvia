montarTopo("index.html");

const COR_NIVEL = { normal: "#1e7a46", atencao: "#c99100", alerta: "#d35400", emergencia: "#b3122e" };
let bairroAberto = null;
let grafico = null;

function cartao(b) {
  const nivel = b.risco ? b.risco.nivel : "normal";
  const pct = b.nivel_pct_cota ?? 0;
  const ult = b.ultima_leitura;
  const prob = b.risco ? Math.round(b.risco.probabilidade * 100) : 0;
  return `
    <button type="button" class="cartao bairro b-${nivel}" data-bairro="${esc(b.bairro)}"
            aria-label="${esc(b.bairro)}: ${ROTULOS[nivel]}, córrego em ${num(pct)}% da cota, chance de alagar ${prob}%">
      <div class="topo-card"><h3>${esc(b.bairro)}</h3>${selo(nivel)}</div>
      <div class="dados"><span>Córrego: <strong>${ult ? num(ult.nivel_cm) : "-"} cm</strong> de ${b.cota_cm}</span><span>${num(pct)}%</span></div>
      <div class="medidor" aria-hidden="true"><span style="width:${Math.min(pct, 100)}%;background:${COR_NIVEL[nivel]}"></span></div>
      <div class="dados"><span>Chuva última hora: <strong>${ult ? num(ult.chuva_mm, 1) : "-"} mm</strong></span><span>IA: ${prob}%</span></div>
      ${b.alerta_ativo ? `<p class="msg-alerta">${esc(b.alerta_ativo.mensagem)}</p>` : ""}
      <div class="dados" style="margin-top:6px"><span>Estação ${esc(b.estacao)}</span><span>${ult ? fmtData(ult.ts) : ""}</span></div>
    </button>`;
}

async function atualizar() {
  try {
    const bairros = await api("/api/bairros");
    const el = document.getElementById("bairros");
    const ordem = { emergencia: 0, alerta: 1, atencao: 2, normal: 3 };
    bairros.sort((a, b) => ordem[a.risco?.nivel ?? "normal"] - ordem[b.risco?.nivel ?? "normal"]);
    el.innerHTML = bairros.map(cartao).join("");
    el.querySelectorAll("[data-bairro]").forEach((c) => c.addEventListener("click", () => abrir(c.dataset.bairro)));

    const ativos = bairros.filter((b) => b.alerta_ativo);
    const faixa = document.getElementById("faixa");
    faixa.classList.toggle("ativa", ativos.length > 0);
    faixa.textContent = ativos.length
      ? `⚠ ${ativos.length} bairro(s) com alerta ativo: ${ativos.map((b) => b.bairro).join(", ")}. Siga as orientações abaixo.`
      : "";
    if (bairroAberto) abrir(bairroAberto, false);
  } catch (e) {
    document.getElementById("bairros").innerHTML = `<p class="erro">Não foi possível carregar os dados (${esc(e.message)}). Tentando de novo…</p>`;
  }
}

async function abrir(bairro, rolar = true) {
  bairroAberto = bairro;
  const h = await api(`/api/bairros/${encodeURIComponent(bairro)}/historico?limite=24`);
  const sec = document.getElementById("detalhe");
  sec.classList.remove("oculto");
  document.getElementById("det-titulo").textContent = `${bairro} — últimas ${h.leituras.length} leituras`;
  // cada leitura = 1 hora consolidada pela estação; eixo em horas relativas ao momento atual
  const n = h.leituras.length;
  const rotulos = h.leituras.map((_, i) => (i === n - 1 ? "agora" : `-${n - 1 - i}h`));
  const max = Math.max(...h.leituras.map((l) => l.nivel_cm));
  document.getElementById("det-resumo").textContent =
    `Nível máximo no período: ${num(max)} cm (cota de transbordamento: ${h.cota_cm} cm).`;
  if (window.Chart) {
    const dados = {
      labels: rotulos,
      datasets: [
        { type: "line", label: "Nível do córrego (cm)", data: h.leituras.map((l) => l.nivel_cm), borderColor: "#0b6e4f", backgroundColor: "#0b6e4f", yAxisID: "y", tension: .25 },
        { type: "line", label: "Cota de transbordamento", data: h.leituras.map(() => h.cota_cm), borderColor: "#b3122e", borderDash: [6, 4], pointRadius: 0, yAxisID: "y" },
        { type: "bar", label: "Chuva (mm/h)", data: h.leituras.map((l) => l.chuva_mm), backgroundColor: "#7aa6d8", yAxisID: "y2" },
      ],
    };
    if (grafico) { grafico.data = dados; grafico.update("none"); }
    else {
      grafico = new Chart(document.getElementById("grafico-nivel"), {
        data: dados,
        options: { maintainAspectRatio: false, animation: false, interaction: { mode: "index", intersect: false },
          scales: { y: { title: { display: true, text: "cm" }, beginAtZero: true },
                    y2: { position: "right", title: { display: true, text: "mm" }, beginAtZero: true, grid: { drawOnChartArea: false } } } },
      });
    }
  }
  if (rolar) sec.scrollIntoView({ behavior: "smooth", block: "start" });
}

atualizar();
setInterval(atualizar, 4000);
