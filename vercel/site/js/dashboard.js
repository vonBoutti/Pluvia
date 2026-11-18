montarTopo("dashboard.html");
preencherBairros(document.getElementById("f-bairro"), true);
document.getElementById("box-rec").insertAdjacentHTML("afterbegin", icone("lampada"));

const NOMES_CAT = { alagamento: "Alagamento", bueiro_entupido: "Bueiro", deslizamento: "Deslizamento", queda_arvore: "Árvore", outros: "Outros" };
const graficos = {};
let ultimo = null;

function desenhar(id, config) {
  if (!window.Chart) return;
  if (graficos[id]) graficos[id].destroy();
  config.options = { maintainAspectRatio: false, animation: false, ...config.options };
  config.options.plugins = { legend: { position: "bottom" }, ...(config.options.plugins || {}) };
  graficos[id] = new Chart(document.getElementById(id), config);
}

const KPIS = [
  ["alagamentos", "alagamentos registrados", 0, true],
  ["familias_afetadas", "famílias afetadas", 0],
  ["horas_criticas", "horas com o córrego acima do limite", 0],
  ["chuva_acumulada_mm", "mm de chuva acumulada", 0],
  ["indice_vulnerabilidade", "alagamentos a cada 100 mm de chuva", 2],
  ["dias_chuva_forte", "dias de chuva forte (20 mm/h ou mais)", 0],
  ["relatos", "relatos de moradores", 0],
  ["relatos_graves_pct", "% dos relatos eram urgentes", 1],
];

function renderizar(d) {
  const b = document.getElementById("f-bairro").value;
  const top = d.ranking_bairros.slice(0, 15);
  if (b && !top.some((r) => r.bairro === b)) {
    const sel = d.ranking_bairros.find((r) => r.bairro === b);
    if (sel) top.push(sel);
  }
  document.getElementById("kpis").innerHTML = KPIS.map(([k, rotulo, casas, dest]) =>
    `<div class="cartao kpi${dest ? " destaque" : ""}"><div class="valor">${num(d.kpis[k], casas)}</div><div class="rotulo">${rotulo}</div></div>`).join("");
  document.getElementById("recomendacao").textContent = d.recomendacao;

  desenhar("g-mensal", {
    data: {
      labels: d.mensal.map((m) => m.mes),
      datasets: [
        { type: "line", label: "Alagamentos", data: d.mensal.map((m) => m.alagamentos), borderColor: cor("emergencia"),
          backgroundColor: cor("emergencia"), yAxisID: "y2", tension: .3, pointRadius: 2 },
        { type: "bar", label: "Chuva (mm)", data: d.mensal.map((m) => m.chuva_mm), backgroundColor: cor("chuva"), borderRadius: 4, yAxisID: "y" },
      ],
    },
    options: { scales: { x: { grid: { display: false } }, y: { title: { display: true, text: "mm" } },
      y2: { position: "right", beginAtZero: true, grid: { drawOnChartArea: false }, ticks: { precision: 0 } } } },
  });

  desenhar("g-bairros", {
    type: "bar",
    data: {
      labels: top.map((r) => r.bairro),
      datasets: [{ label: "Alagamentos por 100 mm", data: top.map((r) => r.indice_vulnerabilidade), borderRadius: 6,
        backgroundColor: top.map((r) => (b && r.bairro === b ? cor("alerta") : cor("brand"))) }],
    },
    options: { indexAxis: "y", plugins: { legend: { display: false } }, scales: { y: { grid: { display: false }, ticks: { autoSkip: false, font: { size: 11 } } } } },
  });

  desenhar("g-diario", {
    data: {
      labels: d.diario.map((x) => x.data),
      datasets: [
        { type: "line", label: "Tendência (7 dias)", data: d.diario.map((x) => x.media_movel_7d), borderColor: cor("accent"), pointRadius: 0, borderWidth: 2 },
        { type: "bar", label: "Chuva média do dia (mm)", data: d.diario.map((x) => x.chuva_mm), backgroundColor: cor("chuva") },
      ],
    },
    options: { scales: { x: { ticks: { maxTicksLimit: 8 }, grid: { display: false } } } },
  });

  desenhar("g-relatos", {
    type: "bar",
    data: {
      labels: d.relatos_categoria.map((r) => NOMES_CAT[r.categoria]),
      datasets: [
        { label: "Urgente", data: d.relatos_categoria.map((r) => r.alta), backgroundColor: cor("emergencia"), borderRadius: 4 },
        { label: "Média", data: d.relatos_categoria.map((r) => r.media), backgroundColor: cor("atencao"), borderRadius: 4 },
        { label: "Baixa", data: d.relatos_categoria.map((r) => r.baixa), backgroundColor: cor("muted"), borderRadius: 4 },
      ],
    },
    options: { scales: { x: { stacked: true, grid: { display: false } }, y: { stacked: true } } },
  });

  document.getElementById("t-ranking").innerHTML = `
    <thead><tr><th>#</th><th>Distrito</th><th>Região</th><th>Chuva (mm)</th><th>Alagamentos</th><th>Horas acima do limite</th><th>Famílias afetadas</th><th>Índice</th></tr></thead>
    <tbody>${d.ranking_bairros.map((r, i) => `<tr><td>${i + 1}</td><td><b>${esc(r.bairro)}</b></td><td>${esc(NOME_REGIAO[r.regiao])}</td><td>${num(r.chuva_mm)}</td><td>${r.alagamentos}</td>
      <td>${r.horas_criticas}</td><td>${r.familias_afetadas}</td><td>${num(r.indice_vulnerabilidade, 2)}</td></tr>`).join("")}</tbody>`;
}

async function carregar() {
  const p = new URLSearchParams();
  const b = document.getElementById("f-bairro").value;
  const rg = document.getElementById("f-regiao").value;
  const i = document.getElementById("f-inicio").value;
  const f = document.getElementById("f-fim").value;
  if (b) p.set("bairro", b);
  if (rg) p.set("regiao", rg);
  if (i) p.set("inicio", i);
  if (f) p.set("fim", f);
  const d = await api(`/api/dashboard?${p}`);
  const fi = document.getElementById("f-inicio"), ff = document.getElementById("f-fim");
  fi.min = ff.min = d.filtros.disponivel.inicio;
  fi.max = ff.max = d.filtros.disponivel.fim;
  ultimo = d;
  renderizar(d);
}

async function carregarIA() {
  try {
    const m = (await api("/api/ia/metricas")).risco_alagamento;
    const ia = m.ia, re = m.regra_atual_80pct_cota;
    const linha = (rotulo, a, d, sufixo = "", menorMelhor = false) => {
      const melhor = menorMelhor ? d < a : d > a;
      return `<tr><td>${rotulo}</td><td>${num(a, 1)}${sufixo}</td><td class="${melhor ? "melhor" : ""}">${num(d, 1)}${sufixo}</td></tr>`;
    };
    document.getElementById("t-ia").innerHTML = `
      <thead><tr><th>O que medimos (${ia.eventos} alagamentos)</th><th>Hoje: régua 80%</th><th>Com a IA</th></tr></thead>
      <tbody>
        ${linha("Alagamentos avisados com pelo menos 1 h de antecedência", re.eventos_avisados_1h_antes_pct, ia.eventos_avisados_1h_antes_pct, "%")}
        ${linha("Tempo médio entre o aviso e a água chegar", re.antecedencia_media_min, ia.antecedencia_media_min, " min")}
        ${linha("Alarmes falsos por mês (menos é melhor)", re.falsos_alarmes_por_mes, ia.falsos_alarmes_por_mes, "", true)}
        ${linha("Quando o alarme toca, quantas vezes está certo", re.precisao * 100, ia.precisao * 100, "%")}
      </tbody>`;
  } catch { document.getElementById("t-ia").innerHTML = "<tr><td>Métricas da IA indisponíveis.</td></tr>"; }
}

document.getElementById("filtros").addEventListener("submit", (e) => { e.preventDefault(); carregar().catch((er) => alert(er.message)); });
document.getElementById("limpar").addEventListener("click", () => { document.getElementById("filtros").reset(); carregar(); });
document.addEventListener("temamudou", () => { if (ultimo) renderizar(ultimo); });
carregar();
carregarIA();
