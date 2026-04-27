"""
Unified LLM abstraction layer.

Every agent calls stream_completion(role, messages, ...) and receives normalised
{kind, content} events regardless of the underlying provider.

Normalised event kinds:
  "text"        — regular output token
  "thought"     — Gemini thought part (part.thought==True) or Anthropic thinking block
  "tool_call"   — function call request {id, name, arguments}
  "tool_result" — function call response (emitted by callers, not this layer)
  "usage"       — token counts {input_tokens, output_tokens}

Supported providers (via models.py prefix):
  gemini/*       — Google Gemini via LiteLLM  (thinking via extra_body)
  anthropic/*    — Anthropic Claude via LiteLLM (extended thinking via extra_body)
  mulerouter/*   — MuleRouter Qwen via LiteLLM openai-compat shim

Researcher stays on the native google-genai SDK (grounding is not available through
LiteLLM's Gemini path) — use raw_client("researcher") for that.
"""

import os
from typing import AsyncIterator, Optional, Any

import litellm
litellm.set_verbose = False  # suppress noisy litellm logs

from .models import get_model, is_mulerouter, is_gemini, is_anthropic


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

async def stream_completion(
    role: str,
    messages: list[dict],
    *,
    tools: Optional[list] = None,
    thinking: bool = False,
    thinking_budget: int = 1024,
    extra: Optional[dict] = None,
) -> AsyncIterator[dict]:
    """
    Async generator that yields normalised {kind, content} events.

    Args:
        role:            Agent role name (see agents/models.py for valid values)
        messages:        OpenAI-format message list
        tools:           Optional list of tool schemas (OpenAI function-calling format)
        thinking:        Enable extended thinking (Anthropic) / Gemini thinking mode
        thinking_budget: Token budget for thinking
        extra:           Extra kwargs forwarded verbatim to litellm.acompletion()
    """
    model = get_model(role)
    kwargs = _build_kwargs(
        model, messages,
        tools=tools,
        thinking=thinking,
        thinking_budget=thinking_budget,
    )
    if extra:
        kwargs.update(extra)

    response = await litellm.acompletion(**kwargs)
    async for chunk in response:
        for event in _normalise(chunk):
            yield event


def raw_client(role: str) -> Any:
    """
    Return the underlying SDK client for features LiteLLM hasn't caught up to
    (e.g. Gemini google_search grounding, which the Researcher still needs).

    Usage:
        client = raw_client("researcher")   # returns google.genai.Client
        client = raw_client("coder")        # returns anthropic.Anthropic
    """
    model = get_model(role)
    if is_gemini(model):
        from google import genai as _genai
        return _genai.Client(api_key=os.environ["GOOGLE_API_KEY"])
    if is_anthropic(model):
        import anthropic
        return anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    raise ValueError(f"raw_client not implemented for model {model!r}")


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _build_kwargs(
    model: str,
    messages: list[dict],
    *,
    tools: Optional[list],
    thinking: bool,
    thinking_budget: int,
) -> dict:
    """Build the litellm.acompletion() kwargs dict for the given model."""
    kwargs: dict = {
        "model": _resolve_litellm_model(model),
        "messages": messages,
        "stream": True,
    }

    if tools:
        kwargs["tools"] = tools

    if thinking:
        if is_anthropic(model):
            # Anthropic extended thinking — passed via extra_body so LiteLLM
            # forwards it as-is to the Anthropic API.
            kwargs.setdefault("extra_body", {})["thinking"] = {
                "type": "enabled",
                "budget_tokens": thinking_budget,
            }
        elif is_gemini(model):
            # Gemini thinking config — also forwarded via extra_body.
            kwargs.setdefault("extra_body", {})["thinking_config"] = {
                "include_thoughts": True,
                "thinking_budget": thinking_budget,
            }

    if is_mulerouter(model):
        kwargs["api_base"] = _mulerouter_base(model)
        kwargs["api_key"] = os.environ.get("MULEROUTER_API_KEY", "")

    if is_anthropic(model):
        api_key = os.environ.get("ANTHROPIC_API_KEY", "")
        if api_key:
            kwargs["api_key"] = api_key

    if is_gemini(model):
        api_key = os.environ.get("GOOGLE_API_KEY", "")
        if api_key:
            kwargs["api_key"] = api_key

    return kwargs


def _resolve_litellm_model(model: str) -> str:
    """
    Map our internal model strings to LiteLLM model identifiers.

    - gemini/*       → gemini/* (LiteLLM supports this prefix natively)
    - anthropic/*    → anthropic/* (LiteLLM supports this prefix natively)
    - mulerouter/*   → openai/<model-name>  (use LiteLLM's openai-compat path)
    """
    if is_mulerouter(model):
        # Strip the "mulerouter/" prefix; LiteLLM treats it as openai-compat
        return "openai/" + model[len("mulerouter/"):]
    return model


def _mulerouter_base(model: str) -> str:
    """Return the MuleRouter API base URL for the given model string."""
    base = os.environ.get("MULEROUTER_BASE_URL", "https://api.mulerouter.ai")
    # Strip trailing slash for safety
    return base.rstrip("/")


def _normalise(chunk) -> list[dict]:
    """
    Map a single LiteLLM streaming chunk to a list of normalised events.

    LiteLLM StreamingChoices have:
      chunk.choices[0].delta.content       — text token
      chunk.choices[0].delta.thinking      — Anthropic thinking token (LiteLLM 1.50+)
      chunk.choices[0].delta.tool_calls    — list of ChoiceDeltaToolCall
      chunk.usage                          — ModelResponse (final chunk only)
    """
    events: list[dict] = []

    # Usage (appears on the final chunk when stream_options={"include_usage": True}
    # or sometimes on chunk.usage directly).
    usage = getattr(chunk, "usage", None)
    if usage and (getattr(usage, "prompt_tokens", None) or getattr(usage, "total_tokens", None)):
        events.append({
            "kind": "usage",
            "content": {
                "input_tokens": getattr(usage, "prompt_tokens", 0),
                "output_tokens": getattr(usage, "completion_tokens", 0),
            },
        })

    choices = getattr(chunk, "choices", None) or []
    for choice in choices:
        delta = getattr(choice, "delta", None)
        if delta is None:
            continue

        # --- Anthropic thinking block ---
        thinking = getattr(delta, "thinking", None)
        if thinking:
            events.append({"kind": "thought", "content": thinking})

        # --- Regular text ---
        text = getattr(delta, "content", None)
        if text:
            events.append({"kind": "text", "content": text})

        # --- Tool calls ---
        tool_calls = getattr(delta, "tool_calls", None) or []
        for tc in tool_calls:
            if tc is None:
                continue
            fn = getattr(tc, "function", None)
            if fn is None:
                continue
            name = getattr(fn, "name", None) or ""
            args = getattr(fn, "arguments", None) or ""
            if name or args:
                events.append({
                    "kind": "tool_call",
                    "id": getattr(tc, "id", None) or "",
                    "name": name,
                    "content": args,
                })

    return events
