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
| `iot/`, `app/`, `frontend/` | 3 · MVP e IoT | sketch ESP32 + `diagram.json` (Wokwi), `simulador.py`, API FastAPI, 6 telas web |
| `tests/`, `.github/`, `Dockerfile` | 4 · DevOps | 14 testes, CI/CD, Docker, compose |
| `docs/` | Documentação | PDF, arquitetura, plano de testes, roteiro do pitch, prints e evidências |

## Ferramentas que usamos (e para quê)

Uma explicação sem jargão de cada peça do projeto e do papel dela.

### O "cérebro": linguagem e servidor
- **Python**: a linguagem em que escrevemos quase tudo, do tratamento dos dados à IA e ao servidor. Escolhemos por ser a mais usada em ciência de dados e por ser fácil de ler.
- **FastAPI**: monta o "balcão de atendimento" do sistema (a API). É por ele que os sensores entregam as medições e que as telas pedem informações. De quebra, gera sozinho uma página de documentação em `/docs`, onde dá para testar tudo.
- **Uvicorn**: o programa que mantém a API ligada e respondendo, como um porteiro sempre de plantão.
- **Pydantic**: confere tudo o que chega antes de aceitar. Se um sensor manda "999 cm" ou alguém tenta enviar um código malicioso no relato, ele barra.
- **SQLite**: o banco de dados. Guarda leituras, alertas, relatos e inscrições num único arquivo, sem precisar instalar servidor de banco.

### A inteligência: dados e IA
- **pandas** e **NumPy**: as "planilhas turbinadas" do Python. Usamos para limpar mais de 100 mil leituras (tirar repetidas, corrigir valores impossíveis, preencher buracos) e calcular os indicadores.
- **scikit-learn**: a biblioteca de IA. Com ela treinamos dois modelos:
  - um que olha chuva e nível da água e diz **qual a chance de o córrego transbordar nas próximas 3 horas**;
  - outro que **lê o relato do morador** e entende se é alagamento, bueiro, árvore caída etc., e o quão urgente é.
- **joblib**: salva os modelos treinados em arquivo, para a API carregá-los sem precisar treinar de novo a cada vez.

### O que a pessoa vê: telas
- **HTML, CSS e JavaScript**: as seis telas do site. Sem framework pesado, para abrir rápido até em celular simples e internet fraca.
  - A tela principal ocupa a tela inteira e mostra só o essencial: um "copo" com a água do córrego subindo em tempo real, uma frase grande dizendo o que está acontecendo e três ações do que fazer. A cor de fundo muda conforme o risco, e cai chuva animada quando está chovendo.
  - A página **Entenda** explica cada número e cada cor sem jargão. Tem um simulador em que a pessoa "faz chover" e vê o córrego encher.
  - Modo claro e escuro (segue o celular ou o botão ☀/☾), botão para aumentar a fonte, alto contraste e animações que se desligam para quem prefere menos movimento.
- **Chart.js**: desenha os gráficos (nível do córrego, chuva por mês, ranking de bairros) de forma interativa.

### No campo: sensores
- **ESP32**: a plaquinha de baixo custo que fica na ponte do córrego e manda os dados pelo Wi-Fi.
- **Wokwi**: simulador online de eletrônica. Permite montar e testar a estação com os sensores sem comprar nada.
- **Sensores**: o **ultrassônico HC-SR04** mede a altura da água, o **pluviômetro** conta a chuva e o **DHT22** mede a temperatura. **LEDs e um buzzer** fazem o alarme local, que funciona mesmo se a internet cair.
- **Simulador em Python** (`iot/simulador.py`): faz o papel das 6 estações para demonstrar o sistema, inclusive com uma tempestade "de mentira".

### Bastidores: qualidade, segurança e entrega
- **Git**: guarda o histórico de todas as mudanças no código, como um "controle de versões" de um documento.
- **GitHub Actions**: um robô que, a cada mudança enviada ao GitHub, confere o código, roda os testes, monta o sistema e publica a nova versão, sem ninguém precisar fazer isso à mão.
- **Docker** e **Docker Compose**: empacotam o sistema inteiro numa "caixa" que roda igual em qualquer computador ou servidor. Um comando e está no ar.
- **pytest**: roda os 14 testes automáticos que verificam se tudo continua funcionando (login, alertas, IA, proteção de dados...).
- **Ruff**: um "corretor ortográfico" do código, que também aponta práticas inseguras.
- **PyJWT**: cria o "crachá digital" (token) que a Defesa Civil recebe ao fazer login e que expira em 1 hora.
- **Prometheus (formato de métricas)**: o endereço `/metrics` mostra a saúde do sistema (quantas requisições, tempo de resposta, alertas ativos) num formato que ferramentas de monitoramento como o Grafana entendem.

### Para análise extra
- **Power BI (DAX)**: não é obrigatório para rodar, mas deixamos as fórmulas prontas em `bigdata/medidas_dax.md`, para quem quiser montar o mesmo painel no Power BI.
- **Google Chrome (modo sem janela)** + **Node.js**: usados só para tirar os prints das telas e gerar o PDF de entrega automaticamente.

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
Depois abra http://localhost:8000 (as 6 telas: comece pela "Risco agora" e pela "Entenda") ou http://localhost:8000/docs (documentação da API).

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
