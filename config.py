# -*- coding: utf-8 -*-
"""Application configuration loaded from environment variables."""

import os


def _normalize_provider(value: str) -> str:
    provider = (value or "gemini").strip().lower()
    if provider not in {"gemini", "openai", "minimax"}:
        return "gemini"
    return provider


PROVIDER = _normalize_provider(
    os.getenv("AI_PROVIDER")
    or os.getenv("LLM_PROVIDER")
    or os.getenv("API_PROVIDER")
    or "gemini"
)

if PROVIDER == "openai":
    DEFAULT_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    API_KEY = os.getenv("OPENAI_API_KEY", "")
elif PROVIDER == "minimax":
    DEFAULT_MODEL = os.getenv("MINIMAX_MODEL", "abab6.5s-chat")
    API_KEY = os.getenv("MINIMAX_API_KEY", "")
else:
    DEFAULT_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
    API_KEY = os.getenv("GEMINI_API_KEY", "")

API_CONFIG = {
    "provider": PROVIDER,
    "api_key": API_KEY,
    "model": os.getenv("LLM_MODEL", DEFAULT_MODEL),
}
