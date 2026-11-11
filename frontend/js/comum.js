// Funções compartilhadas por todas as telas.
const BAIRROS = ["Jardim Pantanal", "Vila Itaim", "Aricanduva", "Lapa de Baixo", "Ipiranga", "Pompeia"];
const ROTULOS = { normal: "Normal", atencao: "Atenção", alerta: "Alerta", emergencia: "Emergência" };

// Ícones (traço, herdam a cor do texto)
const ICONES = {
  gota: '<path d="M12 2.7s6.3 7 6.3 11.3a6.3 6.3 0 0 1-12.6 0C5.7 9.7 12 2.7 12 2.7z"/>',
  mapa: '<path d="M9 4 3 6v14l6-2 6 2 6-2V4l-6 2-6-2z"/><path d="M9 4v14M15 6v14"/>',
  mensagem: '<path d="M21 12a8 8 0 0 1-11.6 7.1L4 20l1-4.6A8 8 0 1 1 21 12z"/>',
  sino: '<path d="M6 8a6 6 0 1 1 12 0c0 7 3 8 3 8H3s3-1 3-8"/><path d="M10.3 20a1.9 1.9 0 0 0 3.4 0"/>',
  grafico: '<path d="M3 3v18h18"/><path d="M7 15l4-4 3 3 5-6"/>',
  escudo: '<path d="M12 3 4 6v6c0 5 3.5 8 8 9 4.5-1 8-4 8-9V6l-8-3z"/>',
  sol: '<circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/>',
  lua: '<path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z"/>',
  contraste: '<circle cx="12" cy="12" r="9"/><path d="M12 3v18a9 9 0 0 0 0-18z" fill="currentColor"/>',
  chuva: '<path d="M16 13V11a4 4 0 0 0-8 0v2"/><path d="M20 16.6A5 5 0 0 0 18 7h-1.3A8 8 0 1 0 4 15.3"/><path d="M8 19v2M12 17v2M16 19v2"/>',
  ok: '<path d="M20 6 9 17l-5-5"/>',
  seta: '<path d="M6 9l6 6 6-6"/>',
  sensor: '<rect x="4" y="4" width="16" height="16" rx="2"/><path d="M9 9h6v6H9zM9 2v2M15 2v2M9 20v2M15 20v2M2 9h2M2 15h2M20 9h2M20 15h2"/>',
  cerebro: '<path d="M9.5 2A2.5 2.5 0 0 1 12 4.5v15a2.5 2.5 0 0 1-4.96.44 2.5 2.5 0 0 1-2.96-3.08 3 3 0 0 1-.34-5.58 2.5 2.5 0 0 1 1.32-4.24A2.5 2.5 0 0 1 9.5 2z"/><path d="M14.5 2A2.5 2.5 0 0 0 12 4.5v15a2.5 2.5 0 0 0 4.96.44 2.5 2.5 0 0 0 2.96-3.08 3 3 0 0 0 .34-5.58 2.5 2.5 0 0 0-1.32-4.24A2.5 2.5 0 0 0 14.5 2z"/>',
  celular: '<rect x="6" y="2" width="12" height="20" rx="2"/><path d="M11 18h2"/>',
  aviso: '<path d="M10.3 3.9 1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0z"/><path d="M12 9v4M12 17h.01"/>',
  lampada: '<path d="M9 18h6M10 22h4"/><path d="M12 2a7 7 0 0 0-4 12.7V17h8v-2.3A7 7 0 0 0 12 2z"/>',
  telefone: '<path d="M22 16.9v3a2 2 0 0 1-2.2 2 19.8 19.8 0 0 1-8.6-3.1 19.5 19.5 0 0 1-6-6A19.8 19.8 0 0 1 2.1 4.2 2 2 0 0 1 4.1 2h3a2 2 0 0 1 2 1.7c.1.9.4 1.8.7 2.7a2 2 0 0 1-.5 2.1L8 9.8a16 16 0 0 0 6 6l1.3-1.3a2 2 0 0 1 2.1-.4c.9.3 1.8.6 2.7.7a2 2 0 0 1 1.7 2z"/>',
};
function icone(nome, extra = "") {
  return `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" ${extra}>${ICONES[nome]}</svg>`;
}

async function api(caminho, opcoes = {}) {
  const headers = { "Content-Type": "application/json", ...(opcoes.headers || {}) };
  const token = sessionStorage.getItem("token");
  if (token && opcoes.auth) headers.Authorization = `Bearer ${token}`;
  const resp = await fetch(caminho, { ...opcoes, headers });
  const corpo = await resp.json().catch(() => ({}));
  if (!resp.ok) {
    let msg = corpo.detail || `Erro ${resp.status}`;
    if (Array.isArray(msg)) msg = msg.map((e) => e.msg.replace("Value error, ", "")).join("; ");
    const erro = new Error(msg);
    erro.status = resp.status;
    throw erro;
  }
  return corpo;
}

function esc(texto) {
  const d = document.createElement("div");
  d.textContent = texto == null ? "" : String(texto);
  return d.innerHTML;
}

function selo(nivel) {
  return `<span class="selo n-${nivel}">${ROTULOS[nivel] || nivel}</span>`;
}

function fmtData(iso) {
  if (!iso) return "-";
  return new Date(iso).toLocaleString("pt-BR", { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" });
}

function num(n, casas = 0) {
  return Number(n).toLocaleString("pt-BR", { maximumFractionDigits: casas, minimumFractionDigits: casas });
}

function preencherBairros(select, comTodos = false) {
  select.innerHTML = (comTodos ? '<option value="">Todos os bairros</option>' : "") +
    BAIRROS.map((b) => `<option>${b}</option>`).join("");
}

// Lê uma cor do tema atual (para os gráficos acompanharem claro/escuro)
function cor(nome) {
  return getComputedStyle(document.body).getPropertyValue(`--${nome}`).trim();
}

function configurarGraficos() {
  if (!window.Chart) return;
  Chart.defaults.color = cor("muted");
  Chart.defaults.borderColor = cor("line");
  Chart.defaults.font.family = getComputedStyle(document.body).fontFamily;
  Chart.defaults.plugins.legend.labels.usePointStyle = true;
  Chart.defaults.plugins.legend.labels.boxWidth = 8;
  Chart.defaults.plugins.tooltip.backgroundColor = cor("text");
  Chart.defaults.plugins.tooltip.titleColor = cor("surface");
  Chart.defaults.plugins.tooltip.bodyColor = cor("surface");
  Chart.defaults.plugins.tooltip.padding = 10;
  Chart.defaults.plugins.tooltip.cornerRadius = 8;
}

function temaEscuro() {
  const t = document.documentElement.getAttribute("data-theme");
  if (t) return t === "dark";
  return window.matchMedia("(prefers-color-scheme: dark)").matches;
}

// Cabeçalho, tema e acessibilidade em todas as páginas
function montarTopo(atual) {
  const paginas = [
    ["index.html", "Risco agora", "mapa"], ["entenda.html", "Entenda", "lampada"], ["relatar.html", "Relatar", "mensagem"],
    ["alertas.html", "Alertas por SMS", "sino"], ["dashboard.html", "Indicadores", "grafico"],
    ["admin.html", "Defesa Civil", "escudo"],
  ];
  document.getElementById("topo").innerHTML = `
    <a class="pular" href="#conteudo">Pular para o conteúdo</a>
    <div class="barra">
      <a class="marca" href="index.html" aria-label="Alerta Cheia - início">
        <span class="logo">${icone("gota")}</span>
        <span>Alerta Cheia<small>Aviso de enchente antes da água chegar</small></span>
      </a>
      <nav class="menu" aria-label="Principal">
        ${paginas.map(([h, t, i]) => `<a href="${h}" ${h === atual ? 'aria-current="page"' : ""}>${icone(i)}${t}</a>`).join("")}
      </nav>
      <div class="acess">
        <button type="button" class="icone-btn" id="btn-tema" aria-label="Alternar tema claro/escuro"></button>
        <button type="button" class="icone-btn" id="btn-fonte" aria-pressed="false" aria-label="Aumentar fonte" title="Aumentar fonte">A+</button>
        <button type="button" class="icone-btn" id="btn-contraste" aria-pressed="false" aria-label="Alto contraste" title="Alto contraste">${icone("contraste")}</button>
      </div>
    </div>`;

  const ler = (k) => { try { return localStorage.getItem(k); } catch { return null; } };
  const salvar = (k, v) => { try { localStorage.setItem(k, v); } catch { /* sem storage */ } };

  const btnTema = document.getElementById("btn-tema");
  const pintarBotaoTema = () => {
    const escuro = temaEscuro();
    btnTema.innerHTML = icone(escuro ? "sol" : "lua");
    btnTema.title = escuro ? "Usar tema claro" : "Usar tema escuro";
  };
  pintarBotaoTema();
  btnTema.addEventListener("click", () => {
    const novo = temaEscuro() ? "light" : "dark";
    document.documentElement.setAttribute("data-theme", novo);
    salvar("tema", novo);
    pintarBotaoTema();
    configurarGraficos();
    document.dispatchEvent(new Event("temamudou"));
  });
  window.matchMedia("(prefers-color-scheme: dark)").addEventListener("change", () => {
    if (!document.documentElement.getAttribute("data-theme")) {
      pintarBotaoTema(); configurarGraficos(); document.dispatchEvent(new Event("temamudou"));
    }
  });

  [["btn-fonte", "fonte-grande"], ["btn-contraste", "alto-contraste"]].forEach(([id, cls]) => {
    const b = document.getElementById(id);
    const aplicar = (on) => { document.body.classList.toggle(cls, on); b.setAttribute("aria-pressed", on); };
    aplicar(ler(cls) === "1");
    b.addEventListener("click", () => {
      const on = !document.body.classList.contains(cls);
      aplicar(on); salvar(cls, on ? "1" : "0");
      configurarGraficos(); document.dispatchEvent(new Event("temamudou"));
    });
  });
  configurarGraficos();
}
