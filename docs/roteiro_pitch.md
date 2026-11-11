# Roteiro do vídeo pitch (até 3 minutos)

Regra do enunciado: mostrar o protótipo funcionando, sem vídeo de slides ou leitura de tela.
Grave a tela com a API rodando (`uvicorn ...`) e o simulador em um terminal ao lado.

**Preparação:** Defesa Civil → "Reiniciar cenário"; cadastrar um telefone em "Receber alertas" para o
Jardim Pantanal; deixar o Painel de risco aberto; terminal pronto com
`python -m iot.simulador --cenario tempestade --intervalo 4`.

| Tempo | Bloco | O que falar | O que aparece na tela |
|---|---|---|---|
| 0:00–0:30 | O problema | "Dona Maria mora no Jardim Pantanal, na beira do córrego. Todo verão a água entra na casa dela, e o aviso chega quando a rua já está alagada. Na Grande São Paulo, os alagamentos param a cidade e colocam famílias em risco todo ano." | Painel de risco com os 6 bairros em "Normal". |
| 0:30–0:50 | A solução | "O Alerta Cheia coloca sensores baratos nos córregos e usa IA para avisar a população **até 2 horas antes** do transbordamento, por SMS, que funciona em qualquer celular." | Tela "Receber alertas" com o cadastro e a mensagem de LGPD. |
| 0:50–2:10 | Demonstração | 1) "Começa o temporal" (rodar o simulador). 2) "O córrego está em 64% da cota, a régua de hoje ainda não alarmaria, mas a IA já vê o padrão e emite ALERTA." 3) Abrir o card do bairro e mostrar o gráfico de nível + cota. 4) Relatar: "água entrando nas casas, idoso ilhado", e mostrar a triagem em milissegundos com urgência alta e o órgão certo. 5) Defesa Civil: fila por urgência e as regras do agente. 6) Dashboard: filtrar Jardim Pantanal e mostrar a recomendação e a tabela "antes x depois". 7) Mostrar o ESP32 no Wokwi (LED vermelho e buzzer: alarme local mesmo sem internet). | Painel, relato, admin, dashboard, Wokwi. |
| 2:10–2:40 | Impacto | "No teste com 1 ano de dados que o modelo nunca viu, avisamos 81% dos alagamentos com pelo menos 1 hora de antecedência, contra 56% da régua atual, e com 1/3 dos falsos alarmes. Atende os ODS 11, 13, 9 e 10: cidades resilientes, adaptação ao clima, infraestrutura e redução de desigualdade, porque quem mais sofre com enchente é a periferia." | Tabela "Desempenho da IA: antes x depois". |
| 2:40–3:00 | Fechamento | "Cada estação custa menos de R$ 300 e a solução roda em um container. O Alerta Cheia transforma minutos em segurança. A próxima enchente pode chegar com aviso." | Painel com o alerta ativo. |

Dicas: fale com o cidadão no centro da história, mostre números e não ultrapasse 3:00.
Publique como "não listado" no YouTube e teste o link em aba anônima.
