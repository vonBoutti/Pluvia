# Pluvia: versão de demonstração (Vercel)

Esta pasta publica o frontend do Pluvia como **site estático**, sem a API em Python. O app principal
(`frontend/` + `app/`) **não é alterado**: aqui fica uma cópia com o modo demonstração ligado.

Na versão de demonstração:
- As 6 telas funcionam por um link, sem servidor.
- A IA roda no navegador com os **mesmos modelos** treinados pelo projeto (floresta aleatória de risco e
  classificador de relatos), exportados para `site/demo/*.json`. Os resultados batem com os do Python.
- O dashboard usa os dados reais da camada gold (96 distritos, 2 anos).
- Na tela **Risco agora**, o botão **"Simular temporal"** faz chover no distrito escolhido e mostra a IA
  emitindo o alerta e o agente escalando para emergência.
- Relatos, cadastros e alertas ficam guardados só no navegador de quem está testando.
- Login da Defesa Civil (demonstração): `defesacivil` / `demo-DefesaCivil-2026`.

## Publicar no Vercel
1. Em vercel.com: **Add New → Project** e importe o repositório do projeto.
2. Em **Root Directory**, escolha `vercel`.
3. Clique em **Deploy**. O `vercel.json` já define tudo (site estático na pasta `site/`, sem build).

A cada push no GitHub o Vercel publica de novo.

## Atualizar o site
Depois de mudar o frontend ou re-treinar os modelos, na raiz do projeto:

```bash
python -m scripts.preparar
python vercel/montar.py
```

Depois faça commit de `vercel/site/`.

## Arquivos
| Arquivo | O que é |
|---|---|
| `montar.py` | Copia `frontend/` para `site/`, liga o modo demonstração na cópia e exporta os modelos |
| `demo.js` | Responde às rotas da API dentro do navegador (IA, agente, dashboard, relatos, alertas, login) |
| `demo.css` | Faixa "Modo demonstração" no topo das telas |
| `exportar_demo.py` | Exporta modelos e dados para `site/demo/*.json` |
| `vercel.json` | Configuração do Vercel e cabeçalhos de segurança |
| `site/` | Site gerado (é ele que vai para o ar) |
