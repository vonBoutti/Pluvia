"""Agente de alerta: regras de automação que transformam a previsão em ação.

Fluxo:  leitura IoT -> features -> modelo de risco -> ESTE AGENTE -> alerta + mensagem

Regras (documentadas no PDF, seção IA):
R1  nível "alerta" ou "emergencia"         -> cria alerta para o bairro
R2  já existe alerta ativo do mesmo nível   -> não duplica (evita spam ao cidadão)
R3  nível sobe                              -> novo alerta (escalonamento)
R4  2+ relatos de alagamento "alta" no
    bairro na última hora                   -> eleva para pelo menos "alerta" (sinal humano)
R5  risco volta a "normal"                  -> encerra alertas ativos do bairro
R6  mensagem em linguagem simples, <= 160 caracteres (SMS), com ação concreta e
    telefone da Defesa Civil (199)
"""
from __future__ import annotations

ORDEM = {"normal": 0, "atencao": 1, "alerta": 2, "emergencia": 3}

MENSAGENS = {
    "atencao": "ATENÇÃO {bairro}: chuva forte e córrego subindo. Evite áreas baixas e acompanhe os avisos. Defesa Civil 199",
    "alerta": "ALERTA {bairro}: risco de alagamento nas próximas 3h. Tire carros de áreas baixas e prepare documentos. Defesa Civil 199",
    "emergencia": "EMERGÊNCIA {bairro}: alagamento iminente. Vá para local alto agora. Não atravesse água corrente. Defesa Civil 199",
}

ACOES_DEFESA_CIVIL = {
    "atencao": "Monitorar estação e pontos críticos; equipe de sobreaviso.",
    "alerta": "Deslocar equipe ao bairro; acionar agentes comunitários; bloquear vias baixas.",
    "emergencia": "Acionar evacuação de áreas de risco e abrigos; Corpo de Bombeiros em prontidão.",
}


def decidir(bairro: str, risco: dict, alerta_ativo: str | None, relatos_graves_1h: int) -> dict:
    """Retorna a decisão do agente: {'acao': criar|manter|encerrar|nenhuma, ...}."""
    nivel = risco["nivel"]
    motivo = f"modelo: p={risco['probabilidade']:.2f}"

    if relatos_graves_1h >= 2 and ORDEM[nivel] < ORDEM["alerta"]:  # R4
        nivel = "alerta"
        motivo += f"; R4: {relatos_graves_1h} relatos graves na última hora"

    if ORDEM[nivel] >= ORDEM["alerta"]:  # R1
        if alerta_ativo and ORDEM[alerta_ativo] >= ORDEM[nivel]:  # R2
            return {"acao": "manter", "nivel": alerta_ativo, "motivo": motivo + "; R2: alerta já ativo"}
        return {  # R1/R3
            "acao": "criar",
            "nivel": nivel,
            "mensagem": MENSAGENS[nivel].format(bairro=bairro)[:160],
            "acao_defesa_civil": ACOES_DEFESA_CIVIL[nivel],
            "motivo": motivo + ("; R3: escalonamento" if alerta_ativo else "; R1"),
        }
    if alerta_ativo and nivel == "normal":  # R5
        return {"acao": "encerrar", "nivel": nivel, "motivo": motivo + "; R5: risco normalizado"}
    return {"acao": "nenhuma", "nivel": nivel, "motivo": motivo}
