"""
core/llm_factory.py
-------------------
Fábrica centralizada para criação e reutilização de instâncias de LLM (ChatOpenAI).
Segue os princípios de Clean Architecture:
- Centraliza configurações de modelo e credenciais.
- Evita instanciamento duplicado e disperso pelo código.
- Facilita testes unitários através de cache e desacoplamento.
"""

from functools import lru_cache
from typing import Optional
from langchain_openai import ChatOpenAI
from backend.core.config import settings


@lru_cache(maxsize=16)
def get_agent_llm(temperature: float = 0.0, model: Optional[str] = None) -> ChatOpenAI:
    """
    Retorna uma instância única em cache do ChatOpenAI configurada com as credenciais do sistema.
    """
    return ChatOpenAI(
        model=model or settings.AGENT_MODEL,
        temperature=temperature,
        api_key=settings.OPENAI_API_KEY,
    )
