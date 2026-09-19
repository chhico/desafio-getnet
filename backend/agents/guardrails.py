"""
agents/guardrails.py
--------------------
Módulo de Guardrails de Segurança, Integridade e Uso Responsável.
Atende ao requisito do edital de detecção e tratamento de requisições:
- Inseguras (Prompt Injection, Jailbreak, Código Malicioso, SQL Injection)
- Sensíveis ou Não Suportadas (Fraude, Evasão de Regras, Crimes)
- Ofensivas ou Abusivas (Discurso de ódio, assédio, toxicidade)
"""

import re
import logging
from typing import Tuple
from langchain_core.messages import AIMessage, HumanMessage
from backend.agents.state import SupportState

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Padrões de Detecção Determinística (Fast-Path Guardrails)
# ---------------------------------------------------------------------------

_PROMPT_INJECTION_PATTERNS = [
    r"ignore\s+(all\s+|suas\s+|todas\s+as\s+)?(previous\s+|anteriores\s+)?instructions",
    r"ignore\s+(suas\s+|as\s+)?(regras|diretrizes|instruções)",
    r"esque[çc]a\s+(todas\s+as\s+|suas\s+)?(regras|instruções|diretrizes)",
    r"desconsidere\s+(suas\s+|as\s+)?(regras|instruções|diretrizes)",
    r"revele\s+(o\s+|seu\s+)?(prompt|system\s+prompt|instruções\s+iniciais)",
    r"mostre\s+(o\s+|seu\s+)?(prompt|system\s+prompt|instruções\s+de\s+sistema)",
    r"(what\s+is|show\s+me)\s+(your\s+)?(system\s+prompt|initial\s+prompt)",
    r"act\s+as\s+(dan|unrestricted|jailbreak|root)",
    r"finja\s+que\s+voc[êe]\s+[ée]\s+(um\s+hacker|o\s+presidente|desprovido\s+de\s+regras)",
    r"voc[êe]\s+agora\s+[ée]\s+(livre|um\s+modelo\s+sem\s+regras|dan)",
    r"bypass\s+(safety|guardrails|security)",
]

_CODE_INJECTION_PATTERNS = [
    r"<\s*script[^>]*>",
    r"javascript\s*:",
    r"onload\s*=",
    r"onerror\s*=",
    r"(union\s+select|drop\s+table|alter\s+table|delete\s+from\s+\w+)",
    r"'\s*or\s+'?1'?\s*=\s*'?1'?",
    r"'\s*or\s+1\s*=\s*1",
    r";\s*--",
    r"exec\s*\(\s*xp_",
]

_ILLICIT_INTENTS_PATTERNS = [
    r"(como\s+clonar|clonagem\s+de)\s+(cart[ãa]o|maquininha)",
    r"(como\s+fraudar|fraude\s+na|burlar)\s+(maquininha|pagamento|getnet|taxa)",
    r"(lavar\s+dinheiro|lavagem\s+de\s+dinheiro)",
    r"(como\s+roubar|desviar)\s+(dinheiro|dados\s+de\s+cart[ãa]o)",
    r"(como\s+criar|gerar)\s+(malware|ransomware|trojan|vírus)",
]

_OFFENSIVE_PATTERNS = [
    r"\b(vai\s+se\s+fuder|vá\s+se\s+foder|filho\s+da\s+puta|arrombado|seu\s+merda)\b",
]


def check_input_safety(text: str) -> Tuple[bool, str]:
    """
    Inspeciona o texto recebido em busca de violações de segurança e políticas.
    Retorna (is_safe, violation_reason).
    """
    if not text or not isinstance(text, str):
        return True, ""

    text_lower = text.lower().strip()

    # 1. Checagem de Prompt Injection / Jailbreak
    for pattern in _PROMPT_INJECTION_PATTERNS:
        if re.search(pattern, text_lower, re.IGNORECASE):
            return False, "Tentativa de injeção de prompt ou violação de instruções (Prompt Injection / Jailbreak)."

    # 2. Checagem de Injeção de Código / SQL / XSS
    for pattern in _CODE_INJECTION_PATTERNS:
        if re.search(pattern, text_lower, re.IGNORECASE):
            return False, "Tentativa de injeção de código executável ou SQL Injection."

    # 3. Checagem de Intenções Ilícitas ou Fraude
    for pattern in _ILLICIT_INTENTS_PATTERNS:
        if re.search(pattern, text_lower, re.IGNORECASE):
            return False, "Solicitação com finalidade ilícita, fraude ou violação contratual/legal."

    # 4. Checagem de Conteúdo Ofensivo / Abusivo
    for pattern in _OFFENSIVE_PATTERNS:
        if re.search(pattern, text_lower, re.IGNORECASE):
            return False, "Mensagem contendo linguagem ofensiva, abusiva ou assédio."

    return True, ""


def guardrail_node(state: SupportState) -> dict:
    """
    Nó de Guardrail executado na entrada do Grafo.
    Valida a última mensagem do usuário antes que ela alcance os agentes.
    """
    messages = state.get("messages", [])
    last_user_message = ""
    for m in reversed(messages):
        if isinstance(m, HumanMessage) or (hasattr(m, "type") and m.type == "human"):
            last_user_message = m.content.strip()
            break

    is_safe, reason = check_input_safety(last_user_message)

    if not is_safe:
        logger.warning(f"🛡️ Guardrail acionado! Motivo: {reason} | Texto: '{last_user_message[:80]}'")
        
        msg_bloqueio = AIMessage(
            content=(
                "🛡️ **Solicitação não suportada ou bloqueada por segurança**\n\n"
                "Identificamos que sua mensagem contém termos, instruções ou tentativas de comando "
                "incompatíveis com as políticas de segurança, privacidade e uso ético da Getnet.\n\n"
                "Por motivos de conformidade e segurança da informação, esta solicitação não pôde ser atendida.\n\n"
                "Por favor, reformule sua pergunta com foco em informações comerciais, suporte a maquininhas, "
                "taxas ou serviços oficiais da Getnet."
            ),
            name="guardrail_block",
        )

        return {
            "messages": [msg_bloqueio],
            "is_safe": False,
            "guardrail_reason": reason,
            "next_agent": "guardrail_block",
            "category": "Segurança / Guardrail",
            "routing_reason": f"Bloqueio preventivo de segurança: {reason}",
        }

    return {
        "is_safe": True,
        "guardrail_reason": None,
    }


def route_after_guardrail(state: SupportState) -> str:
    """
    Aresta condicional após o Guardrail:
    - Se a mensagem for segura -> segue para o Agente Roteador ('orchestrator')
    - Se a mensagem for bloqueada -> encerra o fluxo imediatamente ('guardrail_block')
    """
    if state.get("is_safe") is False:
        return "guardrail_block"
    return "orchestrator"
