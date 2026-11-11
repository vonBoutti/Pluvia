montarTopo("entenda.html");

// ícones declarados no HTML com data-ic (inseridos antes do texto)
document.querySelectorAll("[data-ic]").forEach((el) => el.insertAdjacentHTML("afterbegin", icone(el.dataset.ic)));

document.getElementById("ir-cores").addEventListener("click", () =>
  document.getElementById("cores").scrollIntoView({ behavior: "smooth" }));

// revelar elementos ao rolar
const obs = new IntersectionObserver((itens) => itens.forEach((i) => {
  if (i.isIntersecting) { i.target.classList.add("visivel"); obs.unobserve(i.target); }
}), { threshold: 0.12 });
document.querySelectorAll(".revelar").forEach((el, i) => {
  el.style.transitionDelay = `${(i % 4) * 70}ms`;
  obs.observe(el);
});

// ---------- simulador ilustrativo ----------
const mm = document.getElementById("sim-mm");
const horas = document.getElementById("sim-h");
const secao = document.getElementById("sim");
const RESULTADO = {
  normal: "Tudo tranquilo: o córrego dá conta dessa chuva.",
  atencao: "Chuva forte. O córrego sobe, mas ainda tem espaço. Fique atento.",
  alerta: "O córrego está enchendo rápido. Você receberia um SMS de ALERTA agora.",
  emergencia: "O córrego vai transbordar! SMS de EMERGÊNCIA: vá para um lugar alto.",
};
let gotas = -1;

function chover(qtd) {
  if (qtd === gotas || window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
  gotas = qtd;
  document.getElementById("sim-chuva").innerHTML = Array.from({ length: qtd }, () =>
    `<i style="left:${(Math.random() * 110).toFixed(1)}%;animation-duration:${(0.55 + Math.random() * 0.5).toFixed(2)}s;animation-delay:-${(Math.random() * 2).toFixed(2)}s"></i>`).join("");
}

function simular() {
  const chuva = Number(mm.value);
  const h = Number(horas.value);
  // conta simplificada: nível base 60 cm em um córrego com limite de 180 cm
  const cm = 60 + chuva * (1.4 + h * 1.25);
  const pct = Math.round(cm / 180 * 100);
  const nivel = pct >= 95 ? "emergencia" : pct >= 68 ? "alerta" : chuva >= 10 ? "atencao" : "normal";
  document.getElementById("sim-mm-v").textContent = `${chuva} mm`;
  document.getElementById("sim-h-v").textContent = `${h} h`;
  document.getElementById("sim-pct").textContent = `${pct}%`;
  document.getElementById("sim-agua").style.height = `${Math.min(100, pct * 0.88)}%`;
  secao.classList.remove("nv-normal", "nv-atencao", "nv-alerta", "nv-emergencia");
  secao.classList.add(`nv-${nivel}`);
  document.getElementById("sim-res").innerHTML = `${selo(nivel)}<p>${RESULTADO[nivel]}</p>`;
  document.getElementById("sim-desc").setAttribute("aria-label", `Córrego simulado em ${pct}% do limite: ${ROTULOS[nivel]}`);
  chover(Math.min(40, Math.round(chuva * 1.5)));
}
pausarForaDaTela(document.querySelector(".hero"));
pausarForaDaTela(secao);
mm.addEventListener("input", simular);
horas.addEventListener("input", simular);
simular();
