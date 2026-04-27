"""
Model registry for all agents.

Maps role names to LiteLLM model strings. Override any role via env var:
  MODEL_CODER=mulerouter/qwen3-coder  # route Coder through MuleRouter Qwen
  MODEL_RESEARCHER=gemini/gemini-2.5-pro  # locked — Researcher needs grounding

MuleRouter is the entry point for Qwen credits. Researcher must stay on Gemini
because google_search grounding is only available through the Gemini SDK path.
"""

import os

MODELS: dict[str, str] = {
    "supervisor": "gemini/gemini-2.5-flash",
    "researcher": "gemini/gemini-2.5-pro",   # locked: needs google_search grounding
    "coder": "anthropic/claude-sonnet-4-5",
    "validator": "gemini/gemini-2.5-flash",
    "synthesizer": "anthropic/claude-haiku-4-5",
    "chat": "gemini/gemini-2.5-flash",
}


def get_model(role: str) -> str:
    """Return model string for role, respecting env-var overrides."""
    env_key = f"MODEL_{role.upper()}"
    override = os.environ.get(env_key)
    if override:
        return override
    if role not in MODELS:
        raise ValueError(f"Unknown agent role: {role!r}. Valid roles: {list(MODELS)}")
    return MODELS[role]


def is_mulerouter(model: str) -> bool:
    return model.startswith("mulerouter/")


def is_gemini(model: str) -> bool:
    return model.startswith("gemini/")


def is_anthropic(model: str) -> bool:
    return model.startswith("anthropic/")
