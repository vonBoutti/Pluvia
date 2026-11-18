"""Monta a versão de demonstração do Pluvia para o Vercel, sem alterar o app principal.

1. Copia frontend/ para vercel/site/.
2. Na CÓPIA, liga o modo demonstração (js/demo.js + css/demo.css): sem a API em Python,
   as telas são atendidas no navegador, com os mesmos modelos de IA do projeto.
3. Exporta modelos e dados para vercel/site/demo/*.json.

Uso, na raiz do projeto (depois de `python -m scripts.preparar`):
    python vercel/montar.py
"""
from __future__ import annotations

import shutil
import sys
from pathlib import Path

AQUI = Path(__file__).resolve().parent
RAIZ = AQUI.parent
SITE = AQUI / "site"
sys.path.insert(0, str(RAIZ))
sys.path.insert(0, str(AQUI))

GANCHO_ANTES = "async function api(caminho, opcoes = {}) {\n"
GANCHO = (GANCHO_ANTES
          + "  // versão Vercel: sem API, o modo demonstração responde no navegador (js/demo.js)\n"
          + "  if (typeof emDemo === \"function\" && await emDemo()) return Demo.api(caminho, opcoes);\n")


def main() -> None:
    shutil.rmtree(SITE, ignore_errors=True)
    shutil.copytree(RAIZ / "frontend", SITE)
    shutil.copy2(AQUI / "demo.js", SITE / "js" / "demo.js")
    shutil.copy2(AQUI / "demo.css", SITE / "css" / "demo.css")

    comum = SITE / "js" / "comum.js"
    texto = comum.read_text(encoding="utf-8")
    if GANCHO_ANTES not in texto:
        raise SystemExit("comum.js mudou: não achei a função api() para ligar o modo demonstração")
    comum.write_text(texto.replace(GANCHO_ANTES, GANCHO, 1), encoding="utf-8")

    for pagina in SITE.glob("*.html"):
        html = pagina.read_text(encoding="utf-8")
        html = html.replace('<script defer src="js/comum.js"></script>',
                            '<script defer src="js/comum.js"></script>\n  <script defer src="js/demo.js"></script>', 1)
        html = html.replace('<link rel="stylesheet" href="css/estilo.css">',
                            '<link rel="stylesheet" href="css/estilo.css">\n  <link rel="stylesheet" href="css/demo.css">', 1)
        pagina.write_text(html, encoding="utf-8")
        print(f"  {pagina.name}: modo demonstração ligado")

    import exportar_demo
    exportar_demo.main()
    print(f"Pronto: {SITE}")


if __name__ == "__main__":
    main()
