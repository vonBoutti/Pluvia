# Alerta Cheia: CitizenTech de previsão de alagamentos

**Global Solution 2026/2 · FIAP · Engenharia de Software (4ESOA)**

Estações IoT medem chuva e nível dos córregos. Uma IA prevê o transbordamento nas
próximas 3 horas, e um agente de automação avisa a população por SMS e orienta a Defesa
Civil. O cidadão também relata problemas em texto livre, que a IA classifica e encaminha
em milissegundos. Um dashboard mostra ao gestor onde investir em prevenção.

> No teste com 1 ano de dados nunca vistos pelo modelo, a IA avisou **81% dos alagamentos com 1 h ou mais de
> antecedência** (régua atual: 56%), com **75 min** de antecedência média (régua: 36 min) e **1,6 falso alarme/mês**
> (régua: 4,5).

- **Vídeo pitch:** `<COLE AQUI O LINK PÚBLICO>`
- **PDF de entregáveis:** [`docs/Alerta_Cheia_Entregaveis.pdf`](docs/Alerta_Cheia_Entregaveis.pdf)
- **Integrantes:** ver [`integrantes.txt`](integrantes.txt)
- **ODS:** 11 (cidades resilientes), 13 (clima), 9 (infraestrutura), 10 (desigualdades)

## Estrutura (organizada por área)

| Pasta | Área | Conteúdo |
|---|---|---|
| `ia/` | 1 · IA e automação | `treinar.py` (modelos + métricas), `risco.py`, `triagem.py`, `automacao.py` (agente R1–R6) |
| `bigdata/` | 2 · Big Data | `gerar_dados.py` (bronze), `pipeline.py` (silver/gold), `analitico.py` (medidas), `medidas_dax.md` |
| `iot/`, `app/`, `frontend/` | 3 · MVP e IoT | sketch ESP32 + `diagram.json` (Wokwi), `simulador.py`, API FastAPI, 5 telas web |
| `tests/`, `.github/`, `Dockerfile` | 4 · DevOps | 14 testes, CI/CD, Docker, compose |
| `docs/` | Documentação | PDF, arquitetura, plano de testes, roteiro do pitch, prints e evidências |

## Como executar

Pré-requisito: **Python 3.11+** (testado em 3.12 e 3.14). Rode todos os comandos na raiz do projeto.

```bash
pip install -r requirements-dev.txt
```

```bash
cp .env.example .env
```

```bash
python -m scripts.preparar
```
Gera os dados (bronze/silver/gold), treina os dois modelos e grava as métricas em `ia/modelos/metricas.json`. Leva cerca de 30 s.

```bash
uvicorn app.main:app --env-file .env
```
Depois abra http://localhost:8000 (as 5 telas) ou http://localhost:8000/docs (documentação da API).

Em outro terminal, simule as estações IoT (cada ciclo representa 1 hora):

```bash
python -m iot.simulador --cenario tempestade --bairro "Jardim Pantanal"
```

Outros cenários: `--cenario calmo` e `--cenario replay` (reproduz o maior alagamento do histórico).

**Login da Defesa Civil (demo):** usuário e senha definidos em `.env` (`ADMIN_USER` / `ADMIN_PASSWORD`). Troque antes de usar fora da demonstração.

### Testes e lint

```bash
pytest
```

```bash
ruff check .
```

### Docker

```bash
docker compose up --build
```

API + simulador de tempestade:

```bash
docker compose --profile demo up --build
```

### IoT no Wokwi
1. Em https://wokwi.com, crie um projeto **ESP32**.
2. Cole `iot/estacao_alerta_cheia/estacao_alerta_cheia.ino` e `diagram.json`, e adicione a biblioteca *DHT sensor library for ESPx*.
3. Ajuste `API_URL` para o IP da sua máquina (exige o Wokwi Private Gateway) ou apenas observe o alarme local: mova o slider de distância do HC-SR04 (menor distância = córrego mais cheio) e clique no botão verde para simular chuva.

### Prints das telas (opcional)
Com a API rodando, execute `node scripts/capturar_telas.mjs` (Node 22+ e Chrome) para gerar `docs/prints/`.

## Principais endpoints

| Método | Rota | Acesso |
|---|---|---|
| POST | `/api/leituras` | estação IoT (`X-API-Key`) |
| GET | `/api/bairros`, `/api/bairros/{bairro}/historico`, `/api/alertas` | público |
| POST | `/api/relatos` (com triagem por IA), `/api/inscricoes` | público (rate limit, LGPD) |
| POST | `/api/auth/login` | retorna JWT |
| GET/PATCH | `/api/relatos`, `/api/relatos/{id}`; POST `/api/admin/reset` | Defesa Civil (JWT) |
| GET | `/api/dashboard?bairro=&inicio=&fim=`, `/api/ia/metricas` | público |
| GET | `/api/health`, `/api/metricas`, `/metrics` (Prometheus) | monitoramento |

## Observações
- Os dados são **sintéticos**, gerados com semente fixa (reprodutíveis). Os nomes de bairros servem só de cenário.
- O envio de SMS é simulado: o sistema registra quantos inscritos receberiam cada alerta.
- Projeto original do grupo. Bibliotecas usadas: FastAPI, pandas, scikit-learn, PyJWT, Chart.js, DHTesp.
