"""
agents/fast_path.py
-------------------
Tier 1 — Fast-Path de Alta Performance e Baixa Latência.
Intercepta interações de alta frequência e determinísticas (saudações, agradecimentos,
confirmações e FAQ estático), gerando respostas imediatas em < 15ms com custo zero de tokens.
Identifica o agente emissor formalmente como 'knowledge' (Agente de Conhecimento / Assistente Virtual).
"""

import re
from typing import Optional, Dict, Any

# Padrões normalizados de Saudações
_GREETING_PATTERNS = [
    r"^(oi|ola|olá|oie|opa|e\s*a[íi]|eae|fala\s*a[íi]|hello|hi|hey)(\s+getnet|\s+assistente|\s+bot)?$",
    r"^(bom\s+dia|boa\s+tarde|boa\s+noite)(\s+getnet|\s+assistente|\s+pessoal)?$",
    r"^(ol[áa]|oi),?\s+(tudo\s+bem|como\s+vai|como\s+est[áa]|tudo\s+bom)\??$",
]

# Padrões normalizados de Agradecimentos e Despedidas
_THANKS_PATTERNS = [
    r"^(obrigado|obrigada|muito\s+obrigado|muito\s+obrigada|valeu|vlw|tks|thanks)(\s+getnet|\s+pela\s+ajuda)?$",
    r"^(tchau|at[ée]\s+mais|at[ée]\s+logo|at[ée]\s+breve|falou|abra[çc]o|bom\s+trabalho)$",
    r"^(obrigad[ao],?\s+tchau|valeu,?\s+at[ée]\s+mais)$",
]

# Padrões normalizados de Confirmação Simples
_CONFIRMATION_PATTERNS = [
    r"^(ok|beleza|blz|entendi|compreendi|perfeito|show|show\s+de\s+bola|certo|combinado|entendido)$",
    r"^(tudo\s+certo|t[áa]\s+bom|ta\s+bom|tudo\s+bem)$",
]

# Padrões de FAQ Rápido (Canais de Atendimento)
_CHANNELS_PATTERNS = [
    r"(qual\s+[ée]\s+o\s+)?(telefone|n[úu]mero|contato|whatsapp|sac|ouvidoria|0800)\s+(da\s+|do\s+|na\s+|de\s+)?getnet",
    r"(como\s+ligar|como\s+falar\s+no\s+telefone)\s+(da\s+|na\s+|com\s+a\s+|para\s+a\s+|pra\s+)?getnet",
]


def check_fast_path(message: str) -> Optional[Dict[str, Any]]:
    """
    Avalia a mensagem do usuário contra os padrões do Tier 1 (Fast-Path).
    Se houver correspondência, retorna o payload estruturado de resposta imediata.
    Caso contrário, retorna None para seguir o fluxo padrão de IA.
    """
    if not message or not isinstance(message, str):
        return None

    cleaned = message.strip().lower()
    # Remove pontuação leve no início e final para correspondência exata
    cleaned_norm = re.sub(r"^[^\w\s]+|[^\w\s\?]+$", "", cleaned).strip()

    # 1. Saudações e Boas-Vindas
    for pattern in _GREETING_PATTERNS:
        if re.search(pattern, cleaned_norm, re.IGNORECASE):
            return {
                "agent": "knowledge",
                "category": "Saudação / Apresentação",
                "response": (
                    "Olá! Sou o assistente virtual da Getnet. 😊\n\n"
                    "Como posso ajudar o seu negócio hoje?\n"
                    "- 💳 **Maquininhas e Taxas:** catálogo, Get Smart, Get Clássica, taxas no débito e crédito\n"
                    "- 📊 **Vendas e Extrato:** conferência de liquidação financeira e previsão de depósitos\n"
                    "- 🔧 **Suporte Técnico:** conectividade Wi-Fi/4G, troca de bobina e procedimentos operacionais\n"
                    "- 🧾 **Transações:** consulta por ID e motivo de vendas recusadas"
                )
            }

    # 2. Agradecimentos e Despedidas
    for pattern in _THANKS_PATTERNS:
        if re.search(pattern, cleaned_norm, re.IGNORECASE):
            return {
                "agent": "knowledge",
                "category": "Agradecimento / Encerramento",
                "response": (
                    "Por nada! A Getnet agradece o seu contato. 🤝\n\n"
                    "Se precisar de mais alguma informação sobre suas maquininhas, taxas ou extratos, "
                    "estou sempre por aqui à disposição. Boas vendas e ótimos negócios!"
                )
            }

    # 3. Confirmações Simples
    for pattern in _CONFIRMATION_PATTERNS:
        if re.search(pattern, cleaned_norm, re.IGNORECASE):
            return {
                "agent": "knowledge",
                "category": "Confirmação",
                "response": (
                    "Combinado! Se surgir qualquer outra dúvida técnica ou comercial sobre o seu negócio, "
                    "é só me chamar por aqui. Tenha um excelente dia!"
                )
            }

    # 4. Canais Oficiais de Contato (FAQ Imediato)
    for pattern in _CHANNELS_PATTERNS:
        if re.search(pattern, cleaned_norm, re.IGNORECASE):
            return {
                "agent": "knowledge",
                "category": "Canais de Atendimento",
                "response": (
                    "📞 **Canais Oficiais de Atendimento Getnet:**\n\n"
                    "- **Central de Atendimento (Capitais e Regiões Metropolitanas):** 4002-4000\n"
                    "- **Demais Localidades:** 0800-648-8000\n"
                    "- **SAC Getnet (Reclamações e Cancelamentos):** 0800-771-0572 (24 horas)\n"
                    "- **Ouvidoria Getnet:** 0800-646-3404 (dias úteis das 9h às 18h)\n"
                    "- **WhatsApp Oficial Getnet:** (51) 99808-4000\n\n"
                    "---\n"
                    "📌 **Fontes consultadas:**\n"
                    "- 🌐 URL: https://site.getnet.com.br/get-ajuda/"
                )
            }

    return None
