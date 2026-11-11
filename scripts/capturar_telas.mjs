// Captura prints das telas para o PDF de entregáveis (Chrome headless + DevTools Protocol).
// Uso: node scripts/capturar_telas.mjs   (com a API rodando em localhost:8000)
// Requer Node 22+ (WebSocket nativo) e Google Chrome instalado.
import { spawn } from "node:child_process";
import { mkdirSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

const CHROME = process.env.CHROME_PATH || "C:/Program Files/Google/Chrome/Application/chrome.exe";
const BASE = process.env.BASE_URL || "http://localhost:8000";
const SAIDA = "docs/prints";
const USUARIO = process.env.ADMIN_USER || "defesacivil";
const SENHA = process.env.ADMIN_PASSWORD || "demo-DefesaCivil-2026";
mkdirSync(SAIDA, { recursive: true });

const porta = 9333;
const chrome = spawn(CHROME, ["--headless=new", `--remote-debugging-port=${porta}`, "--no-first-run",
  `--user-data-dir=${join(tmpdir(), "alerta-cheia-chrome")}`, "--hide-scrollbars", "about:blank"], { stdio: "ignore" });
const espera = (ms) => new Promise((r) => setTimeout(r, ms));

async function alvo() {
  for (let i = 0; i < 40; i++) {
    try {
      const lista = await (await fetch(`http://127.0.0.1:${porta}/json`)).json();
      const pg = lista.find((t) => t.type === "page");
      if (pg) return pg.webSocketDebuggerUrl;
    } catch { /* ainda subindo */ }
    await espera(250);
  }
  throw new Error("Chrome não respondeu");
}

const ws = new WebSocket(await alvo());
await new Promise((r) => ws.addEventListener("open", r));
let seq = 0;
const pendentes = new Map();
ws.addEventListener("message", (ev) => {
  const m = JSON.parse(ev.data);
  if (m.id && pendentes.has(m.id)) { pendentes.get(m.id)(m); pendentes.delete(m.id); }
});
const cdp = (method, params = {}) => new Promise((res) => { const id = ++seq; pendentes.set(id, res); ws.send(JSON.stringify({ id, method, params })); });
const js = async (expr) => (await cdp("Runtime.evaluate", { expression: expr, awaitPromise: true, returnByValue: true })).result?.result?.value;

async function print(nome, url, { largura = 1280, altura = 900, antes = null, paginaInteira = true, movel = false, escuro = false } = {}) {
  await cdp("Emulation.setEmulatedMedia", { features: [{ name: "prefers-color-scheme", value: escuro ? "dark" : "light" }] });
  await cdp("Emulation.setDeviceMetricsOverride", { width: largura, height: altura, deviceScaleFactor: 1, mobile: movel });
  await cdp("Page.navigate", { url: BASE + url });
  await espera(2500);
  if (antes) { await js(antes); await espera(1800); }
  let clip;
  if (paginaInteira) {
    // captura além da janela SEM redimensionar (seções de tela cheia mantêm a altura real)
    await js("document.querySelectorAll('.revelar').forEach(e => e.classList.add('visivel'))");
    await espera(900);
    const h = await js("Math.min(document.documentElement.scrollHeight, 6000)");
    clip = { x: 0, y: 0, width: largura, height: h, scale: 1 };
  }
  const r = await cdp("Page.captureScreenshot", { format: "png", ...(clip ? { clip, captureBeyondViewport: true } : {}) });
  writeFileSync(join(SAIDA, `${nome}.png`), Buffer.from(r.result.data, "base64"));
  console.log("ok", nome);
}

await cdp("Page.enable");
await cdp("Runtime.enable");
await print("01_painel_risco", "/index.html", { paginaInteira: false, antes: "document.getElementById('meu-bairro').value='Jardim Pantanal';document.getElementById('meu-bairro').dispatchEvent(new Event('change'))" });
await print("01b_painel_completo", "/index.html");
await print("12_entenda", "/entenda.html");
await print("02_relatar_triagem", "/relatar.html", {
  paginaInteira: false, altura: 760,
  antes: `document.getElementById('bairro').value='Jardim Pantanal';
          document.getElementById('texto').value='Socorro, a água do córrego invadiu as casas da rua Bom Jesus e tem uma senhora ilhada';
          document.getElementById('form').requestSubmit();`,
});
await print("03_alertas", "/alertas.html", { paginaInteira: false, altura: 820 });
await print("04_dashboard", "/dashboard.html");
await print("05_dashboard_filtro_bairro", "/dashboard.html", {
  paginaInteira: false, altura: 980,
  antes: `document.getElementById('f-bairro').value='Jardim Pantanal';
          document.getElementById('f-inicio').value='2025-11-01'; document.getElementById('f-fim').value='2026-03-31';
          document.getElementById('filtros').requestSubmit();`,
});
await print("06_defesa_civil", "/admin.html", {
  antes: `fetch('/api/auth/login',{method:'POST',headers:{'Content-Type':'application/json'},
          body:JSON.stringify({usuario:${JSON.stringify(USUARIO)},senha:${JSON.stringify(SENHA)}})})
          .then(r=>r.json()).then(d=>{sessionStorage.setItem('token',d.access_token);location.reload();})`,
});
await print("07_mobile_painel", "/index.html", { largura: 390, altura: 844, paginaInteira: false, movel: true });
await print("15_mobile_entenda", "/entenda.html", { largura: 390, altura: 844, paginaInteira: false, movel: true });
await print("08_swagger_api", "/docs", { paginaInteira: false, altura: 900 });
await print("09_painel_escuro", "/index.html", { escuro: true, paginaInteira: false });
await print("13_entenda_escuro", "/entenda.html", { escuro: true });
await print("14_entenda_simulador", "/entenda.html", { escuro: false, paginaInteira: false, altura: 900,
  antes: "const r=document.getElementById('sim-mm');r.value=22;r.dispatchEvent(new Event('input'));const h=document.getElementById('sim-h');h.value=3;h.dispatchEvent(new Event('input'));document.querySelectorAll('.revelar').forEach(e=>e.classList.add('visivel'));document.getElementById('sim').scrollIntoView()" });
await print("10_dashboard_escuro", "/dashboard.html", { escuro: true, paginaInteira: false, altura: 1100 });
await print("11_relatar_escuro", "/relatar.html", { escuro: true, paginaInteira: false, altura: 760 });

ws.close();
chrome.kill();
process.exit(0);
