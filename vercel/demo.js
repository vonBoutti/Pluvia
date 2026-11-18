// Modo demonstração do Pluvia.
// Usado só na versão do Vercel (vercel/montar.py): sem a API em Python, este arquivo responde
// no lugar dela, dentro do navegador, usando os MESMOS modelos de IA treinados no projeto
// (exportados por `python -m scripts.exportar_demo` para frontend/demo/*.json).
// Leituras, alertas, relatos e cadastros ficam guardados só neste navegador (localStorage).
"use strict";

const Demo = (() => {
  const CHAVE = "pluvia-demo-v1";
  const ORDEM = { normal: 0, atencao: 1, alerta: 2, emergencia: 3 };
  const NIVEL_BASE = 60;
  const PESOS = [0.15, 0.45, 0.45, 0.25];       // mesmo hidrograma do simulador em Python
  const PERFIL = [0, 0, 4, 12, 18, 16, 8, 3, 0, 0, 0, 0, 0, 0];
  const LOGIN = { usuario: "defesacivil", senha: "demo-DefesaCivil-2026" };
  const r1 = (x) => Math.round(x * 10) / 10;
  const r2 = (x) => Math.round(x * 100) / 100;
  const r3 = (x) => Math.round(x * 1000) / 1000;
  const agora = () => new Date().toISOString().slice(0, 19);

  // ------------------------------------------------------------ dados ----
  const cache = {};
  const carregar = (nome) => (cache[nome] ||= fetch(`demo/${nome}.json`).then((r) => r.json()));

  function erro(status, detail) {
    const e = new Error(detail);
    e.status = status;
    throw e;
  }

  // --------------------------------------------------- estado local ----
  let estado = null;
  function salvar() {
    try { localStorage.setItem(CHAVE, JSON.stringify(estado)); } catch { /* sem storage: fica só na memória */ }
  }
  async function obterEstado() {
    if (estado) return estado;
    try { estado = JSON.parse(localStorage.getItem(CHAVE)); } catch { estado = null; }
    if (!estado || !estado.leituras) {
      estado = { seq: 0, inicio: Date.now(), req: 0, leituras: {}, alertas: [], relatos: [], inscricoes: [] };
      await semear();
    }
    return estado;
  }
  const novoId = () => ++estado.seq;

  async function semear() {
    const cat = await carregar("catalogo");
    const base = new Date();
    base.setMinutes(0, 0, 0);
    estado.leituras = {};
    for (const b of cat) {
      estado.leituras[b.bairro] = [];
      for (let h = 24; h >= 1; h--) {
        estado.leituras[b.bairro].push({
          id: novoId(), estacao: b.estacao, bairro: b.bairro,
          ts: new Date(base - h * 3600e3).toISOString().slice(0, 19),
          chuva_mm: 0, nivel_cm: NIVEL_BASE + (h % 3), temp_c: 22, probabilidade: 0, nivel_risco: "normal",
        });
      }
    }
    salvar();
  }

  // ------------------------------------------------ IA: risco (RF) ----
  function montarFeatures(hist, cota) {
    const atual = hist[hist.length - 1];
    const chuvas = hist.map((h) => h.chuva_mm || 0);
    const soma = (a) => a.reduce((s, x) => s + x, 0);
    const anterior = hist.length > 1 ? hist[hist.length - 2].nivel_cm : atual.nivel_cm;
    return {
      chuva_mm: atual.chuva_mm || 0, chuva_3h: r1(soma(chuvas.slice(-3))), chuva_24h: r1(soma(chuvas.slice(-24))),
      nivel_cm: atual.nivel_cm, delta_nivel_1h: r1(atual.nivel_cm - anterior), nivel_pct_cota: r3(atual.nivel_cm / cota),
    };
  }
  async function probabilidadeRF(feat) {
    const m = await carregar("risco");
    const x = m.features.map((f) => feat[f]);
    let soma = 0;
    for (const a of m.arvores) {
      let n = 0;
      while (a.l[n] !== -1) n = x[a.f[n]] <= a.t[n] ? a.l[n] : a.r[n];
      soma += a.p[n];
    }
    return soma / m.arvores.length;
  }
  async function prever(feat) {
    const m = await carregar("risco");
    let p;
    if (feat.nivel_pct_cota >= 1) p = 1;                                   // já transbordou
    else if (!(feat.chuva_24h > 0 || feat.nivel_pct_cota >= 0.5)) p = 0;  // tempo seco e córrego baixo
    else p = await probabilidadeRF(feat);
    const niveis = [[0.75, "emergencia", "Emergência"], [m.limiar, "alerta", "Alerta"],
      [r3(m.limiar / 3), "atencao", "Atenção"], [0, "normal", "Normal"]];
    const [, nivel, rotulo] = niveis.find(([lim]) => p >= lim);
    return { probabilidade: r3(p), nivel, rotulo };
  }

  // ------------------------------------------- IA: triagem de relatos ----
  const normalizar = (t) => String(t).toLowerCase().trim().normalize("NFKD").replace(/[̀-ͯ]/g, "");
  function analisar(texto, vet) {
    const [nmin, nmax] = vet.ngram;
    const grams = [];
    if (vet.analyzer === "word") {
      const tok = (texto.match(/[\p{L}\p{N}_]+/gu) || []).filter((w) => w.length >= 2);
      for (let n = nmin; n <= nmax; n++) for (let i = 0; i + n <= tok.length; i++) grams.push(tok.slice(i, i + n).join(" "));
    } else { // char_wb, igual ao scikit-learn
      for (let w of texto.replace(/\s\s+/g, " ").split(/\s+/).filter(Boolean)) {
        w = ` ${w} `;
        for (let n = nmin; n <= nmax; n++) {
          let off = 0;
          grams.push(w.slice(off, off + n));
          while (off + n < w.length) { off++; grams.push(w.slice(off, off + n)); }
          if (off === 0) break;
        }
      }
    }
    return grams;
  }
  function vetor(texto, modelo) {
    const x = new Map();
    let offset = 0;
    for (const vet of modelo.vetorizadores) {
      vet._idx ||= new Map(vet.termos.map((t, i) => [t, i]));
      const cont = new Map();
      for (const g of analisar(texto, vet)) {
        const i = vet._idx.get(g);
        if (i !== undefined) cont.set(i, (cont.get(i) || 0) + 1);
      }
      let norma = 0;
      const parte = [];
      for (const [i, c] of cont) { const v = (1 + Math.log(c)) * vet.idf[i]; parte.push([i, v]); norma += v * v; }
      norma = Math.sqrt(norma) || 1;
      for (const [i, v] of parte) x.set(offset + i, v / norma);
      offset += vet.termos.length;
    }
    return x;
  }
  function proba(texto, modelo) {
    const x = vetor(texto, modelo);
    const z = modelo.intercept.slice();
    for (const [j, v] of x) modelo.coef[j].forEach((c, k) => { z[k] += v * c; });
    const mx = Math.max(...z);
    const e = z.map((v) => Math.exp(v - mx));
    const s = e.reduce((a, b) => a + b, 0);
    return e.map((v) => v / s);
  }
  async function triar(texto) {
    const m = await carregar("triagem");
    const norm = normalizar(texto);
    const pc = proba(norm, m.categoria);
    const ic = pc.indexOf(Math.max(...pc));
    const categoria = m.categoria.classes[ic];
    const ps = proba(norm, m.severidade);
    const sevModelo = m.severidade.classes[ps.indexOf(Math.max(...ps))];
    const urgente = new RegExp(m.urgencia.join("|")).test(norm);
    const severidade = urgente ? "alta" : sevModelo;
    return {
      categoria, confianca: r2(pc[ic]), severidade, regra_urgencia_aplicada: severidade !== sevModelo,
      orgao_responsavel: m.orgao[categoria], prazo_atendimento: m.prazo[severidade], revisao_humana: pc[ic] < 0.6,
    };
  }

  // ------------------------------------------------ agente (R1–R6) ----
  async function decidir(bairro, risco, ativo, graves) {
    const ag = await carregar("agente");
    let nivel = risco.nivel;
    let motivo = `modelo: p=${risco.probabilidade.toFixed(2)}`;
    if (graves >= 2 && ORDEM[nivel] < ORDEM.alerta) { nivel = "alerta"; motivo += `; R4: ${graves} relatos graves na última hora`; }
    if (ORDEM[nivel] >= ORDEM.alerta) {
      if (ativo && ORDEM[ativo] >= ORDEM[nivel]) return { acao: "manter", nivel: ativo, motivo: `${motivo}; R2: alerta já ativo` };
      return { acao: "criar", nivel, mensagem: ag.mensagens[nivel].replace("{bairro}", bairro).slice(0, 160),
        acao_defesa_civil: ag.acoes[nivel], motivo: motivo + (ativo ? "; R3: escalonamento" : "; R1") };
    }
    if (ativo && nivel === "normal") return { acao: "encerrar", nivel, motivo: `${motivo}; R5: risco normalizado` };
    return { acao: "nenhuma", nivel, motivo };
  }
  async function executarAgente(bairro, risco) {
    const ativoReg = [...estado.alertas].reverse().find((a) => a.bairro === bairro && a.ativo);
    const umaHora = Date.now() - 3600e3;
    const graves = estado.relatos.filter((r) => r.bairro === bairro && r.categoria === "alagamento"
      && r.severidade === "alta" && new Date(r.criado_em).getTime() >= umaHora).length;
    const d = await decidir(bairro, risco, ativoReg ? ativoReg.nivel : null, graves);
    const encerrar = () => estado.alertas.forEach((a) => { if (a.bairro === bairro && a.ativo) { a.ativo = 0; a.encerrado_em = agora(); } });
    if (d.acao === "criar") {
      encerrar();
      const dest = estado.inscricoes.filter((i) => i.bairro === bairro).length;
      const id = novoId();
      estado.alertas.push({ id, bairro, nivel: d.nivel, mensagem: d.mensagem, acao_defesa_civil: d.acao_defesa_civil,
        motivo: d.motivo, probabilidade: risco.probabilidade, criado_em: agora(), encerrado_em: null, ativo: 1, destinatarios: dest });
      d.alerta_id = id;
      d.sms_enviados_simulados = dest;
    } else if (d.acao === "encerrar") encerrar();
    return d;
  }

  // ------------------------------------------- dashboard (camada gold) ----
  const diaIdx = (g, s) => {
    if (!/^\d{4}-\d{2}-\d{2}$/.test(s)) erro(422, "Datas inválidas (use AAAA-MM-DD)");
    return Math.round((Date.parse(`${s}T00:00:00Z`) - Date.parse(`${g.inicio}T00:00:00Z`)) / 864e5);
  };
  const dataDe = (g, i) => new Date(Date.parse(`${g.inicio}T00:00:00Z`) + i * 864e5).toISOString().slice(0, 10);

  async function painel(p) {
    const [g, cat] = [await carregar("gold"), await carregar("catalogo")];
    const regioes = ["Centro", "Norte", "Sul", "Leste", "Oeste"];
    if (p.regiao && !regioes.includes(p.regiao)) erro(404, "Região não encontrada (Centro, Norte, Sul, Leste ou Oeste)");
    const infoB = Object.fromEntries(cat.map((c) => [c.bairro, c]));
    if (p.bairro && !infoB[p.bairro]) erro(404, "Bairro não encontrado");
    const d0 = p.inicio ? Math.max(0, diaIdx(g, p.inicio)) : 0;
    const d1 = p.fim ? Math.min(g.dias - 1, diaIdx(g, p.fim)) : g.dias - 1;
    const naRegiao = g.bairros.map((b, i) => i).filter((i) => !p.regiao || infoB[g.bairros[i]].regiao === p.regiao);
    const sel = naRegiao.filter((i) => !p.bairro || g.bairros[i] === p.bairro);
    const selSet = new Set(sel);
    const noPeriodo = (d) => d >= d0 && d <= d1;
    const ev = g.eventos.filter(([, d]) => noPeriodo(d));
    const rl = g.relatos.filter(([d, b]) => noPeriodo(d) && selSet.has(b));

    // KPIs
    let chuva = 0;
    for (const b of sel) for (let d = d0; d <= d1; d++) chuva += g.chuva[b][d];
    let alag = 0, horas = 0, fam = 0;
    const afetados = new Set();
    for (const [b, , a, h, f] of ev) if (selSet.has(b)) { alag += a; horas += h; fam += f; if (a > 0) afetados.add(b); }
    let fortes = 0;
    for (let d = d0; d <= d1; d++) if (sel.some((b) => g.chmax[b][d] >= 20)) fortes++;
    const totRel = rl.reduce((s, r) => s + r[4], 0);
    const altaRel = rl.filter((r) => g.severidades[r[3]] === "alta").reduce((s, r) => s + r[4], 0);
    const indice = (a, c) => (c ? r2(a / c * 100) : 0);
    const kpis = {
      chuva_acumulada_mm: r1(chuva), alagamentos: alag, horas_criticas: horas, familias_afetadas: fam,
      indice_vulnerabilidade: indice(alag, chuva), dias_chuva_forte: fortes, relatos: totRel,
      relatos_graves_pct: totRel ? r1(altaRel / totRel * 100) : 0,
      populacao_em_bairros_afetados: [...afetados].reduce((s, b) => s + infoB[g.bairros[b]].populacao, 0),
    };

    // séries
    const meses = new Map();
    const diario = [];
    for (let d = d0; d <= d1; d++) {
      const mes = dataDe(g, d).slice(0, 7);
      if (!meses.has(mes)) meses.set(mes, { mes, chuva_mm: 0, alagamentos: 0, horas_criticas: 0 });
      let s = 0;
      for (const b of sel) s += g.chuva[b][d];
      meses.get(mes).chuva_mm += s;
      diario.push({ data: dataDe(g, d), media: sel.length ? s / sel.length : 0 });
    }
    for (const [b, d, a, h] of ev) if (selSet.has(b)) { const m = meses.get(dataDe(g, d).slice(0, 7)); m.alagamentos += a; m.horas_criticas += h; }
    const mensal = [...meses.values()].map((m) => ({ ...m, chuva_mm: r1(m.chuva_mm) }));
    const serieDiaria = diario.map((x, i) => {
      const jan = diario.slice(Math.max(0, i - 6), i + 1);
      return { data: x.data, chuva_mm: r1(x.media), media_movel_7d: r1(jan.reduce((s, y) => s + y.media, 0) / jan.length) };
    });

    // ranking (na região, ignorando o filtro de distrito)
    const porB = new Map(naRegiao.map((b) => [b, { chuva: 0, alagamentos: 0, horas_criticas: 0, familias_afetadas: 0 }]));
    for (const b of naRegiao) for (let d = d0; d <= d1; d++) porB.get(b).chuva += g.chuva[b][d];
    for (const [b, , a, h, f] of ev) if (porB.has(b)) { const x = porB.get(b); x.alagamentos += a; x.horas_criticas += h; x.familias_afetadas += f; }
    const ranking = [...porB.entries()]
      .map(([b, x]) => ({ bairro: g.bairros[b], chuva_mm: r1(x.chuva), alagamentos: x.alagamentos, horas_criticas: x.horas_criticas,
        familias_afetadas: x.familias_afetadas, indice_vulnerabilidade: indice(x.alagamentos, x.chuva), regiao: infoB[g.bairros[b]].regiao }))
      .sort((a, b) => (a.bairro < b.bairro ? -1 : 1))
      .sort((a, b) => b.indice_vulnerabilidade - a.indice_vulnerabilidade || b.alagamentos - a.alagamentos);

    // relatos por categoria
    const pc = new Map();
    for (const [, , c, s, q] of rl) {
      const nome = g.categorias[c];
      if (!pc.has(nome)) pc.set(nome, { categoria: nome, baixa: 0, media: 0, alta: 0, total: 0 });
      pc.get(nome)[g.severidades[s]] += q;
      pc.get(nome).total += q;
    }
    const relatosCat = [...pc.values()].sort((a, b) => b.total - a.total);

    const alvo = p.bairro ? ranking.filter((x) => x.bairro === p.bairro) : ranking;
    const crit = alvo.filter((x) => x.alagamentos > 0);
    const recomendacao = !crit.length
      ? "Nenhum alagamento no período filtrado. Manter rotina de limpeza preventiva."
      : `Priorizar ${crit[0].bairro}: ${crit[0].alagamentos} alagamentos e ${crit[0].horas_criticas} h acima da cota `
        + `(índice ${Number.isInteger(crit[0].indice_vulnerabilidade) ? crit[0].indice_vulnerabilidade.toFixed(1) : crit[0].indice_vulnerabilidade} por 100 mm). Sugestão: limpeza de bueiros antes do verão, `
        + "cadastro de moradores no alerta por SMS e estudo de piscinão/jardim de chuva.";

    return {
      filtros: { bairro: p.bairro || null, regiao: p.regiao || null, inicio: p.inicio || null, fim: p.fim || null,
        disponivel: { inicio: g.inicio, fim: dataDe(g, g.dias - 1) } },
      kpis, mensal, diario: serieDiaria, ranking_bairros: ranking, relatos_categoria: relatosCat, recomendacao,
    };
  }

  // --------------------------------------------------------- rotas ----
  async function hashTexto(t) {
    try {
      const buf = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(`pluvia-demo:${t}`));
      return [...new Uint8Array(buf)].map((b) => b.toString(16).padStart(2, "0")).join("");
    } catch { return `h${t.length}${t.slice(-2)}`; }
  }
  const exigirLogin = (op) => { if (!op.auth || sessionStorage.getItem("token") !== "demo-token") erro(401, "Token ausente"); };

  async function receberLeitura(l) {
    const cat = await carregar("catalogo");
    const info = cat.find((c) => c.estacao === String(l.estacao || "").toUpperCase());
    if (!info) erro(422, "estação não cadastrada");
    const lista = estado.leituras[info.bairro];
    const feat = montarFeatures([...lista.slice(-23), { chuva_mm: l.chuva_mm, nivel_cm: l.nivel_cm }], info.cota_cm);
    const risco = await prever(feat);
    lista.push({ id: novoId(), estacao: info.estacao, bairro: info.bairro, ts: agora(), chuva_mm: l.chuva_mm,
      nivel_cm: l.nivel_cm, temp_c: l.temp_c ?? null, probabilidade: risco.probabilidade, nivel_risco: risco.nivel });
    if (lista.length > 48) lista.splice(0, lista.length - 48);
    const agente = await executarAgente(info.bairro, risco);
    salvar();
    return { bairro: info.bairro, features: feat, risco, agente };
  }

  async function api(caminho, op = {}) {
    await obterEstado();
    estado.req++;
    const url = new URL(caminho, location.origin);
    const rota = decodeURIComponent(url.pathname);
    const q = Object.fromEntries(url.searchParams);
    const metodo = (op.method || "GET").toUpperCase();
    const corpo = op.body ? JSON.parse(op.body) : {};
    const cat = await carregar("catalogo");
    const infoB = Object.fromEntries(cat.map((c) => [c.bairro, c]));

    if (metodo === "GET" && rota === "/api/catalogo") return cat.map(({ sensibilidade, ...c }) => c);
    if (metodo === "GET" && rota === "/api/health") return { status: "ok", versao: "1.0.0-demo", modelos: true };
    if (metodo === "GET" && rota === "/api/ia/metricas") return carregar("metricas");
    if (metodo === "GET" && rota === "/api/dashboard") return painel(q);

    if (metodo === "GET" && rota === "/api/bairros") {
      return cat.map((c) => {
        const ult = estado.leituras[c.bairro].at(-1) || null;
        const al = [...estado.alertas].reverse().find((a) => a.bairro === c.bairro && a.ativo);
        return { bairro: c.bairro, regiao: c.regiao, estacao: c.estacao, cota_cm: c.cota_cm, ultima_leitura: ult,
          nivel_pct_cota: ult ? r1(ult.nivel_cm / c.cota_cm * 100) : null,
          risco: ult ? { nivel: ult.nivel_risco, probabilidade: ult.probabilidade } : null,
          alerta_ativo: al ? { bairro: al.bairro, nivel: al.nivel, mensagem: al.mensagem, criado_em: al.criado_em } : null };
      });
    }
    const mHist = rota.match(/^\/api\/bairros\/(.+)\/historico$/);
    if (metodo === "GET" && mHist) {
      const b = mHist[1];
      if (!infoB[b]) erro(404, "Bairro não encontrado");
      const lim = Math.min(200, Math.max(1, Number(q.limite || 24)));
      return { bairro: b, cota_cm: infoB[b].cota_cm, leituras: estado.leituras[b].slice(-lim)
        .map(({ ts, chuva_mm, nivel_cm, probabilidade, nivel_risco }) => ({ ts, chuva_mm, nivel_cm, probabilidade, nivel_risco })) };
    }
    if (metodo === "POST" && rota === "/api/leituras") return receberLeitura(corpo);
    if (metodo === "GET" && rota === "/api/alertas") {
      const lista = [...estado.alertas].reverse().filter((a) => q.ativos !== "true" || a.ativo);
      return lista.slice(0, Number(q.limite || 30));
    }
    if (metodo === "POST" && (rota === "/api/relatos" || rota === "/api/ia/triagem")) {
      if (!infoB[corpo.bairro]) erro(422, "bairro não atendido");
      const texto = String(corpo.texto || "").split(/\s+/).filter(Boolean).join(" ");
      if (texto.length < 10 || texto.length > 500) erro(422, "O texto precisa ter entre 10 e 500 caracteres");
      if (/[<>]/.test(texto)) erro(422, "texto contém caracteres não permitidos");
      const t0 = performance.now();
      const tri = await triar(texto);
      const ms = r1(performance.now() - t0);
      if (rota === "/api/ia/triagem") return tri;
      const id = novoId();
      estado.relatos.push({ id, bairro: corpo.bairro, texto, categoria: tri.categoria, severidade: tri.severidade,
        confianca: tri.confianca, orgao: tri.orgao_responsavel, prazo: tri.prazo_atendimento,
        revisao_humana: tri.revisao_humana ? 1 : 0, regra_urgencia: tri.regra_urgencia_aplicada ? 1 : 0,
        status: "aberto", criado_em: agora() });
      let agente = null;
      if (tri.categoria === "alagamento" && tri.severidade === "alta") {
        const ult = estado.leituras[corpo.bairro].at(-1);
        agente = await executarAgente(corpo.bairro, ult ? { nivel: ult.nivel_risco, probabilidade: ult.probabilidade } : { nivel: "normal", probabilidade: 0 });
      }
      salvar();
      return { id, triagem: tri, tempo_triagem_ms: ms, agente };
    }
    if (metodo === "POST" && rota === "/api/inscricoes") {
      if (!infoB[corpo.bairro]) erro(422, "bairro não atendido");
      const tel = String(corpo.telefone || "");
      if (!/^[\d\s()+-]{10,20}$/.test(tel)) erro(422, "Telefone inválido: use DDD + número");
      if (!corpo.aceite_lgpd) erro(422, "é preciso aceitar o uso do telefone apenas para alertas");
      const dig = tel.replace(/\D/g, "");
      const mascara = dig.length >= 10 ? `(${dig.slice(0, 2)}) *****-${dig.slice(-4)}` : "****";
      const h = await hashTexto(dig);
      if (!estado.inscricoes.some((i) => i.bairro === corpo.bairro && i.contato_hash === h)) {
        estado.inscricoes.push({ id: novoId(), bairro: corpo.bairro, contato_hash: h, contato_mascarado: mascara, criado_em: agora() });
        salvar();
      }
      return { bairro: corpo.bairro, telefone: mascara,
        mensagem: "Inscrição confirmada. Você receberá alertas por SMS. Seu número é guardado de forma protegida." };
    }
    if (metodo === "POST" && rota === "/api/auth/login") {
      if (corpo.usuario !== LOGIN.usuario || corpo.senha !== LOGIN.senha) erro(401, "Usuário ou senha inválidos");
      return { access_token: "demo-token", token_type: "bearer", expira_em_min: 60 };
    }
    if (metodo === "GET" && rota === "/api/relatos") {
      exigirLogin(op);
      const ord = { alta: 0, media: 1, baixa: 2 };
      return estado.relatos.filter((r) => !q.status || r.status === q.status)
        .sort((a, b) => ord[a.severidade] - ord[b.severidade] || b.id - a.id).slice(0, 200);
    }
    const mRel = rota.match(/^\/api\/relatos\/(\d+)$/);
    if (metodo === "PATCH" && mRel) {
      exigirLogin(op);
      if (!["aberto", "em_atendimento", "resolvido"].includes(corpo.status)) erro(422, "status inválido");
      const r = estado.relatos.find((x) => x.id === Number(mRel[1]));
      if (!r) erro(404, "Relato não encontrado");
      r.status = corpo.status;
      salvar();
      return { id: r.id, status: r.status, atualizado_por: LOGIN.usuario };
    }
    if (metodo === "POST" && rota === "/api/admin/reset") { exigirLogin(op); await reiniciar(); return { ok: true }; }
    if (metodo === "GET" && rota === "/api/metricas") {
      return { uptime_s: Math.round((Date.now() - estado.inicio) / 1000), requisicoes_total: estado.req, latencia_media_ms: 0,
        por_status: {}, por_rota: {}, negocio: {
          leituras: Object.values(estado.leituras).reduce((s, l) => s + l.length, 0),
          alertas_ativos: estado.alertas.filter((a) => a.ativo).length, relatos: estado.relatos.length } };
    }
    erro(404, "Rota não disponível no modo demonstração");
  }

  async function reiniciar() {
    await obterEstado();
    estado.alertas = [];
    await semear();
  }

  // ------------------------------------------ temporal simulado ----
  let rodando = null;
  const gauss = () => Math.sqrt(-2 * Math.log(1 - Math.random())) * Math.cos(2 * Math.PI * Math.random());
  async function temporal(alvo, aoPasso) {
    if (rodando) return;
    const cat = await carregar("catalogo");
    const regiao = cat.find((c) => c.bairro === alvo).regiao;
    const estacoes = cat.filter((c) => c.regiao === regiao).map((c) => ({
      c, nivel: NIVEL_BASE + (Math.random() * 4 - 2), chuvas: [],
      fator: c.bairro === alvo ? 1 : 0.2 + Math.random() * 0.25, ruido: c.bairro !== alvo,
    }));
    let h = 0;
    rodando = setInterval(async () => {
      if (h >= PERFIL.length) { clearInterval(rodando); rodando = null; aoPasso?.(null); return; }
      for (const e of estacoes) {
        const chuva = r1(PERFIL[h] * e.fator * (e.ruido ? 0.9 + Math.random() * 0.2 : 1));
        e.chuvas.push(chuva);
        const esc = PESOS.reduce((s, w, k) => s + (k < e.chuvas.length ? w * e.chuvas[e.chuvas.length - 1 - k] : 0), 0);
        const base = NIVEL_BASE + gauss() * 1.5;
        e.nivel = Math.max(20, base + (e.nivel - base) * 0.78 + e.c.sensibilidade * esc);
        await receberLeitura({ estacao: e.c.estacao, chuva_mm: chuva, nivel_cm: r1(e.nivel), temp_c: r1(23 - 0.15 * chuva) });
      }
      h++;
      aoPasso?.({ hora: h, total: PERFIL.length, regiao });
    }, 2500);
  }

  // ------------------------------------------------ faixa na tela ----
  function mostrarFaixa() {
    const topo = document.getElementById("topo");
    if (!topo || document.getElementById("faixa-demo")) return;
    const pagina = location.pathname.split("/").pop() || "index.html";
    const div = document.createElement("div");
    div.id = "faixa-demo";
    div.className = "faixa-demo";
    div.innerHTML = `<div class="dentro"><span><b>Modo demonstração</b> · roda no seu navegador com os modelos de IA reais do Pluvia; dados simulados.</span>
      ${pagina === "admin.html" ? '<span>Login de demonstração: <b>defesacivil</b> / <b>demo-DefesaCivil-2026</b></span>' : ""}
      ${pagina === "index.html" ? '<span class="acoes-demo"><button type="button" id="demo-temporal">▶ Simular temporal</button><button type="button" id="demo-reset">Reiniciar</button><span id="demo-status" aria-live="polite"></span></span>' : ""}</div>`;
    topo.after(div);
    const btn = document.getElementById("demo-temporal");
    if (!btn) return;
    const status = document.getElementById("demo-status");
    btn.addEventListener("click", () => {
      const alvo = document.getElementById("meu-bairro")?.value || "Jardim Helena";
      btn.disabled = true;
      status.textContent = `Temporal começando em ${alvo}…`;
      temporal(alvo, (p) => {
        if (!p) { btn.disabled = false; status.textContent = "Temporal terminou."; return; }
        status.textContent = `Hora ${p.hora} de ${p.total} · Zona ${p.regiao}`;
      });
    });
    document.getElementById("demo-reset").addEventListener("click", async () => {
      if (rodando) { clearInterval(rodando); rodando = null; btn.disabled = false; }
      await reiniciar();
      status.textContent = "Cenário reiniciado.";
    });
  }

  return { api, mostrarFaixa, triar, prever, probabilidadeRF, painel };
})();

// Na versão do Vercel não existe API: o modo demonstração está sempre ligado.
const _emDemo = Promise.resolve(true);
function emDemo() { return _emDemo; }
if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", Demo.mostrarFaixa);
else Demo.mostrarFaixa();
