// Aplica o tema salvo antes da página desenhar (evita "piscar" claro -> escuro).
(function () {
  try {
    const t = localStorage.getItem("tema");
    if (t === "light" || t === "dark") document.documentElement.setAttribute("data-theme", t);
  } catch { /* sem storage: segue o sistema */ }
})();
