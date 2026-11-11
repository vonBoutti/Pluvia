// Funções compartilhadas por todas as telas.
const BAIRROS = ["Jardim Pantanal", "Vila Itaim", "Aricanduva", "Lapa de Baixo", "Ipiranga", "Pompeia"];
const ROTULOS = { normal: "Normal", atencao: "Atenção", alerta: "Alerta", emergencia: "Emergência" };

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

// Cabeçalho e acessibilidade (fonte maior / alto contraste) em todas as páginas
function montarTopo(atual) {
  const paginas = [
    ["index.html", "Painel de risco"], ["relatar.html", "Relatar problema"], ["alertas.html", "Receber alertas"],
    ["dashboard.html", "Dados e indicadores"], ["admin.html", "Defesa Civil"],
  ];
  document.getElementById("topo").innerHTML = `
    <a class="pular" href="#conteudo">Pular para o conteúdo</a>
    <div class="barra">
      <a class="marca" href="index.html" aria-label="Alerta Cheia - início">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><path d="M12 2s6 7 6 11a6 6 0 0 1-12 0c0-4 6-11 6-11z"/><path d="M3 21c2 0 2-1 4.5-1s2.5 1 4.5 1 2-1 4.5-1 2.5 1 4.5 1"/></svg>
        Alerta Cheia
      </a>
      <nav class="menu" aria-label="Principal">
        ${paginas.map(([h, t]) => `<a href="${h}" ${h === atual ? 'aria-current="page"' : ""}>${t}</a>`).join("")}
      </nav>
      <div class="acess">
        <button type="button" id="btn-fonte" aria-pressed="false" title="Aumentar fonte">A+</button>
        <button type="button" id="btn-contraste" aria-pressed="false" title="Alto contraste">◐</button>
      </div>
    </div>`;
  const pref = (k) => { try { return localStorage.getItem(k) === "1"; } catch { return false; } };
  const salvar = (k, v) => { try { localStorage.setItem(k, v ? "1" : "0"); } catch { /* sem storage */ } };
  [["btn-fonte", "fonte-grande"], ["btn-contraste", "alto-contraste"]].forEach(([id, cls]) => {
    const b = document.getElementById(id);
    const aplicar = (on) => { document.body.classList.toggle(cls, on); b.setAttribute("aria-pressed", on); };
    aplicar(pref(cls));
    b.addEventListener("click", () => { const on = !document.body.classList.contains(cls); aplicar(on); salvar(cls, on); });
  });
}
