# Plano de testes — Pluvia

Execução automatizada: `pytest` (local) e GitHub Actions a cada push (`.github/workflows/ci.yml`).
Ambiente de teste isolado: banco SQLite temporário e credenciais próprias (`tests/conftest.py`).

| ID | Área | Caso de teste | Entrada | Resultado esperado |
|---|---|---|---|---|
| CT-01 | DevOps | Saúde da API | `GET /api/health` | 200, `status=ok`, modelos carregados |
| CT-02 | Segurança | Login com senha errada | usuário válido + senha errada | 401 |
| CT-03 | Segurança | Rota protegida exige JWT | `GET /api/relatos` sem token, com token falso, com token válido | 401, 401, 200 |
| CT-04 | Segurança/IoT | Leitura sem chave do dispositivo | `POST /api/leituras` sem `X-API-Key` / chave errada | 401 |
| CT-05 | Segurança | Validação de entrada do sensor | nível 999 cm, chuva negativa, estação inexistente | 422 nos três |
| CT-06 | Fluxo completo | Tempestade gera alerta **antes** do transbordamento | 8 leituras do simulador (pico 18 mm/h) | alerta criado com nível < 180 cm (cota); alerta ativo listado |
| CT-07 | IA | Triagem de relato grave | "A água invadiu as casas e tem uma família ilhada…" | categoria `alagamento`, severidade `alta`, órgão Defesa Civil |
| CT-08 | Segurança | Rejeitar HTML/script e bairro inválido | `<script>…`, bairro inexistente | 422 |
| CT-09 | Segurança | Rate limit de relatos | 6 envios no mesmo minuto | 5×201 e 1×429 |
| CT-10 | LGPD | Telefone nunca salvo em claro | inscrição `(11) 97777-4321` | resposta mascarada; banco sem o número; sem aceite → 422 |
| CT-11 | Big Data | Limpeza bronze → silver | duplicata, sensor com defeito, estação desconhecida | 1 duplicata e 1 desconhecida removidas, valor inválido interpolado |
| CT-12 | IA/Automação | Regras R1–R6 do agente | combinações de risco/alerta ativo/relatos | criar, manter, escalar, R4, encerrar, SMS ≤ 160 caracteres |
| CT-13 | Big Data | Filtros do dashboard | bairro + período; bairro inexistente | KPIs menores que o total; meses no intervalo; 404 |
| CT-14 | Segurança/DevOps | Cabeçalhos de segurança e métricas | `GET /index.html`, `GET /metrics` | CSP e X-Frame-Options presentes; métricas Prometheus |

## Evidências
- `docs/evidencias/pytest.txt` — saída da execução (14/14 aprovados)
- `docs/evidencias/simulador_tempestade.txt` — fluxo ponta a ponta com a API real
- `docs/evidencias/docker_build.log` e `docker_run.txt` — build e execução do container
- PDF de entregáveis, seção DevOps — prints
