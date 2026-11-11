montarTopo("index.html");

const ORDEM = { emergencia: 0, alerta: 1, atencao: 2, normal: 3 };
const COR_VAR = { normal: "normal", atencao: "atencao", alerta: "alerta", emergencia: "emergencia" };

// Textos em linguagem simples para cada nível
const MENSAGENS = {
  normal: {
    titulo: "Pode ficar <em>tranquilo</em>",
    frase: (b) => `Não há risco de alagamento em <b>${b}</b> nas próximas 3 horas.`,
    fazer: [["ok", "Siga sua rotina normalmente"], ["sino", "Cadastre o celular para ser avisado se mudar"], ["lampada", "Ajude: mantenha os bueiros da rua sem lixo"]],
  },
  atencao: {
    titulo: "Fique <em>atento</em>",
    frase: (b) => `Está chovendo forte em <b>${b}</b>. Por enquanto, o córrego não deve transbordar.`,
    fazer: [["aviso", "Evite ruas que costumam alagar"], ["sino", "Acompanhe esta página e os avisos por SMS"], ["telefone", "Deixe o celular carregado"]],
  },
  alerta: {
    titulo: "Pode <em>alagar</em> em até 3 horas",
    frase: (b) => `O córrego de <b>${b}</b> está subindo rápido e pode transbordar.`,
    fazer: [["aviso", "Tire o carro de ruas baixas"], ["lampada", "Guarde documentos e remédios em lugar alto"], ["telefone", "Combine com a família onde se encontrar"]],
  },
  emergencia: {
    titulo: "Saia das <em>áreas baixas</em> agora",
    frase: (b) => `O córrego de <b>${b}</b> está transbordando ou prestes a transbordar.`,
    fazer: [["aviso", "Vá para um lugar alto: andar de cima, vizinho ou escola"], ["chuva", "Não atravesse água corrente, nem a pé nem de carro"], ["telefone", "Em perigo, ligue 193 (Bombeiros) ou 199 (Defesa Civil)"]],
  },
};

const sel = document.getElementById("meu-bairro");
preencherBairros(sel);
document.getElementById("ic-local").innerHTML = icone("mapa");
document.getElementById("cta-sms").innerHTML = `${icone("sino")} Avisar meu celular`;
document.getElementById("cta-relatar").innerHTML = `${icone("mensagem")} Relatar problema`;
document.getElementById("cta-entenda").innerHTML = `${icone("lampada")} Entenda o painel`;

let escolhido = null;
try { escolhido = localStorage.getItem("meu-bairro"); } catch { /* sem storage */ }
let dados = [];
let ultimoNivel = null;
let grafico = null;
let ultimoHistorico = null;
let gotasAtuais = -1;

sel.addEventListener("change", () => escolher(sel.value));

function escolher(bairro) {
  escolhido = bairro;
  try { localStorage.setItem("meu-bairro", bairro); } catch { /* sem storage */ }
  ultimoNivel = null;
  render(true);
  carregarHistorico();
}

function chuvaAnimada(mm) {
  const qtd = Math.min(90, Math.round(mm * 4));
  if (qtd === gotasAtuais || window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
  gotasAtuais = qtd;
  const box = document.getElementById("chuva");
  box.innerHTML = Array.from({ length: qtd }, () => {
    const dur = (0.55 + Math.random() * 0.5).toFixed(2);
    return `<i style="left:${(Math.random() * 110).toFixed(1)}%;animation-duration:${dur}s;animation-delay:-${(Math.random() * 2).toFixed(2)}s;opacity:${(0.3 + Math.random() * 0.5).toFixed(2)}"></i>`;
  }).join("");
}

function contarAte(el, alvo) {
  const ini = parseInt(el.dataset.v || "0", 10);
  el.dataset.v = alvo;
  const t0 = performance.now();
  const passo = (t) => {
    const p = Math.min(1, (t - t0) / 900);
    el.textContent = `${Math.round(ini + (alvo - ini) * (1 - Math.pow(1 - p, 3)))}%`;
    if (p < 1) requestAnimationFrame(passo);
  };
  requestAnimationFrame(passo);
}

function render(trocou = false) {
  if (!dados.length) return;
  const b = dados.find((x) => x.bairro === escolhido) || dados[0];
  escolhido = b.bairro;
  sel.value = b.bairro;
  const nivel = b.risco?.nivel ?? "normal";
  const prob = Math.round((b.risco?.probabilidade ?? 0) * 100);
  const pct = Math.round(b.nivel_pct_cota ?? 0);
  const ult = b.ultima_leitura;
  const m = MENSAGENS[nivel];

  document.body.className = document.body.className.replace(/\bnv-\S+/g, "").trim() + ` nv-${nivel}`;
  // copo: o tracejado (100% do limite) fica a 88% da altura
  document.getElementById("agua").style.height = `${Math.min(100, Math.max(4, pct * 0.88))}%`;
  contarAte(document.getElementById("pct"), pct);
  document.getElementById("copo-desc").setAttribute("aria-label",
    `Córrego de ${b.bairro} com ${ult ? num(ult.nivel_cm) : "?"} centímetros, ${pct}% do limite de ${b.cota_cm} centímetros.`);
  chuvaAnimada(ult ? ult.chuva_mm : 0);

  if (nivel !== ultimoNivel || trocou) {
    ultimoNivel = nivel;
    const h1 = document.getElementById("titulo");
    h1.innerHTML = m.titulo;
    h1.classList.remove("troca", "surgir"); void h1.offsetWidth; h1.classList.add("troca");
    document.getElementById("fazer").innerHTML = m.fazer.map(([ic, t]) => `<li><span class="ic">${icone(ic)}</span>${t}</li>`).join("");
  }
  document.getElementById("selo").innerHTML = selo(nivel);
  const hora = ult ? new Date(ult.ts).toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" }) : "-";
  document.getElementById("frase").innerHTML =
    `${m.frase(esc(b.bairro))}<br><span style="font-size:.92em">Chance de alagar nas próximas 3 h: <b>${prob}%</b> · Chuva agora: <b>${ult ? num(ult.chuva_mm, 1) : "-"} mm/h</b> · atualizado às ${hora}</span>`;

  const outros = [...dados].sort((a, c) => ORDEM[a.risco?.nivel ?? "normal"] - ORDEM[c.risco?.nivel ?? "normal"]);
  document.getElementById("chips").innerHTML = outros.map((o) => {
    const n = o.risco?.nivel ?? "normal";
    const p = Math.round(o.nivel_pct_cota ?? 0);
    return `<button type="button" class="chip" data-b="${esc(o.bairro)}" aria-current="${o.bairro === escolhido}"
              aria-label="${esc(o.bairro)}: ${ROTULOS[n]}, córrego em ${p}% do limite">
      <span class="nome"><span class="ponto" style="background:var(--${COR_VAR[n]})"></span>${esc(o.bairro)}</span>
      <span class="info">${ROTULOS[n]} · ${p}% do limite</span>
      <span class="mini"><span style="width:${Math.min(p, 100)}%;background:var(--${COR_VAR[n]})"></span></span>
    </button>`;
  }).join("");
  document.querySelectorAll(".chip").forEach((c) => c.addEventListener("click", () => escolher(c.dataset.b)));
  document.getElementById("ver-historico").innerHTML = `Ver as últimas 24 horas de ${esc(b.bairro)} ${icone("seta")}`;
}

async function atualizar() {
  try {
    dados = await api("/api/bairros");
    if (!escolhido) { // primeira visita: mostra o bairro com maior risco
      escolhido = [...dados].sort((a, c) => ORDEM[a.risco?.nivel ?? "normal"] - ORDEM[c.risco?.nivel ?? "normal"])[0].bairro;
    }
    render();
    if (!ultimoHistorico || ultimoHistorico.bairro !== escolhido) carregarHistorico();
  } catch (e) {
    document.getElementById("titulo").textContent = "Sem conexão";
    document.getElementById("frase").textContent = `Tentando de novo… (${e.message})`;
  }
}

function desenharGrafico(h) {
  if (!window.Chart) return;
  const n = h.leituras.length;
  const rotulos = h.leituras.map((_, i) => (i === n - 1 ? "agora" : `-${n - 1 - i}h`));
  if (grafico) grafico.destroy();
  grafico = new Chart(document.getElementById("grafico-nivel"), {
    data: {
      labels: rotulos,
      datasets: [
        { type: "line", label: "Altura da água (cm)", data: h.leituras.map((l) => l.nivel_cm), borderColor: cor("brand"),
          backgroundColor: cor("brand-soft"), fill: true, yAxisID: "y", tension: .35, pointRadius: 0, borderWidth: 2.5 },
        { type: "line", label: "Limite: transborda", data: h.leituras.map(() => h.cota_cm), borderColor: cor("emergencia"),
          borderDash: [6, 5], pointRadius: 0, borderWidth: 2, yAxisID: "y" },
        { type: "bar", label: "Chuva (mm/h)", data: h.leituras.map((l) => l.chuva_mm), backgroundColor: cor("chuva"), borderRadius: 4, yAxisID: "y2" },
      ],
    },
    options: { maintainAspectRatio: false, animation: false, interaction: { mode: "index", intersect: false },
      plugins: { legend: { position: "bottom" } },
      scales: { x: { grid: { display: false } }, y: { title: { display: true, text: "cm" }, beginAtZero: true },
        y2: { position: "right", title: { display: true, text: "mm" }, beginAtZero: true, grid: { drawOnChartArea: false } } } },
  });
}

async function carregarHistorico() {
  if (!escolhido) return;
  const h = await api(`/api/bairros/${encodeURIComponent(escolhido)}/historico?limite=24`);
  ultimoHistorico = h;
  const max = Math.max(...h.leituras.map((l) => l.nivel_cm));
  document.getElementById("det-titulo").textContent = `${h.bairro}: últimas ${h.leituras.length} horas`;
  document.getElementById("det-resumo").textContent =
    `A água chegou a ${num(max)} cm. O córrego transborda com ${h.cota_cm} cm (linha tracejada vermelha).`;
  desenharGrafico(h);
}

document.getElementById("ver-historico").addEventListener("click", () =>
  document.getElementById("detalhe").scrollIntoView({ behavior: "smooth" }));
document.addEventListener("temamudou", () => { if (ultimoHistorico) desenharGrafico(ultimoHistorico); });
atualizar();
setInterval(() => { atualizar(); if (escolhido) carregarHistorico().catch(() => {}); }, 4000);
