from __future__ import annotations
import os
from typing import Any, Dict
from langchain_core.language_models import BaseChatModel
from langchain_openai import ChatOpenAI  # trocável

def get_llm(model: str | None = None, temperature: float = 0.2) -> BaseChatModel:
    """
    Retorna um ChatModel do LangChain.
    Troca fácil de provedor: basta mudar a import/instanciação.
    """
    model = model or os.getenv("LLM_MODEL", "gpt-4o-mini")
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY não configurada.")
    return ChatOpenAI(model=model, temperature=temperature, timeout=60)
