"""Central configuration: env vars, model selection, LLM/embedding factories.

Every value has a safe local-first default so the app runs against the
Ollama models already pulled on this machine. Nothing here hardcodes a
secret -- API keys are read from the environment only.
"""

from __future__ import annotations

import os

from dotenv import load_dotenv

load_dotenv()


def _env(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    return int(raw) if raw else default


def _env_float(name: str, default: float) -> float:
    raw = os.environ.get(name)
    return float(raw) if raw else default


# --- Ollama (local models) ---------------------------------------------
OLLAMA_BASE_URL = _env("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = _env("OLLAMA_MODEL", "qwen3.5:2b")
EMBED_MODEL = _env("EMBED_MODEL", "nomic-embed-text-v2-moe")

# --- OpenAI-compatible GPT endpoint (user's own env vars) ---------------
OPENAI_API_KEY = _env("OPENAI_API_KEY")
OPENAI_BASE_URL = _env("OPENAI_BASE_URL")
OPENAI_MODEL = _env("OPENAI_MODEL", "gpt-4o-mini")

# --- Agnes AI (OpenAI-compatible, https://apihub.agnes-ai.com/v1) -------
AGNES_API_KEY = _env("AGNES_API_KEY")
AGNES_BASE_URL = _env("AGNES_BASE_URL", "https://apihub.agnes-ai.com/v1")
AGNES_MODEL = _env("AGNES_MODEL", "agnes-2.5-flash")

# Which provider handles "complex" reasoning (multi-hop, verification,
# comparison, synthesis): "openai" (default) or "agnes".
COMPLEX_LLM_PROVIDER = _env("COMPLEX_LLM_PROVIDER", "openai").lower()

# --- ArcadeDB -------------------------------------------------------------
ARCADEDB_HOST = _env("ARCADEDB_HOST", "localhost")
ARCADEDB_PORT = _env_int("ARCADEDB_PORT", 2480)
ARCADEDB_DATABASE = _env("ARCADEDB_DATABASE", "docintel")
ARCADEDB_USER = _env("ARCADEDB_USER", "root")
ARCADEDB_PASSWORD = _env("ARCADEDB_PASSWORD", "playwithdata")

# --- Chunking / retrieval tuning -----------------------------------------
CHUNK_SIZE = _env_int("CHUNK_SIZE", 900)
CHUNK_OVERLAP = _env_int("CHUNK_OVERLAP", 150)
TOP_K_VECTOR = _env_int("TOP_K_VECTOR", 8)
TOP_K_FINAL = _env_int("TOP_K_FINAL", 6)
MAX_HOPS = _env_int("MAX_HOPS", 2)
LLM_TEMPERATURE = _env_float("LLM_TEMPERATURE", 0.1)
LOCAL_MAX_TOKENS = _env_int("LOCAL_MAX_TOKENS", 768)


def get_llm(role: str = "local"):
    """Return a chat model for the given role.

    role="local"   -> Ollama model: entity extraction, routing, simple answers.
    role="complex" -> GPT (OpenAI-compatible) or Agnes: multi-hop, verification,
                       comparison, synthesis. Selected by COMPLEX_LLM_PROVIDER.
    """
    if role == "local":
        from langchain_ollama import ChatOllama

        return ChatOllama(
            model=OLLAMA_MODEL,
            base_url=OLLAMA_BASE_URL,
            temperature=LLM_TEMPERATURE,
            num_predict=LOCAL_MAX_TOKENS,
            reasoning=False,
        )

    if role == "complex":
        from langchain_openai import ChatOpenAI

        if COMPLEX_LLM_PROVIDER == "agnes":
            if not AGNES_API_KEY:
                raise RuntimeError("AGNES_API_KEY is not set but COMPLEX_LLM_PROVIDER=agnes")
            return ChatOpenAI(
                model=AGNES_MODEL,
                base_url=AGNES_BASE_URL,
                api_key=AGNES_API_KEY,
                temperature=LLM_TEMPERATURE,
            )

        if not OPENAI_API_KEY:
            raise RuntimeError("OPENAI_API_KEY is not set but COMPLEX_LLM_PROVIDER=openai")
        return ChatOpenAI(
            model=OPENAI_MODEL,
            base_url=OPENAI_BASE_URL or None,
            api_key=OPENAI_API_KEY,
            temperature=LLM_TEMPERATURE,
        )

    raise ValueError(f"Unknown LLM role: {role!r}")
