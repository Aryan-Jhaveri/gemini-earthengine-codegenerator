"""
Supervisor Agent — routes user intent to the correct execution path.

Replaces the Planner as the first step in the pipeline. The Planner remains
available during the transition period but the Supervisor is now the primary
routing mechanism.

Intent categories:
  research_only  — user wants information/docs, no code
  code_only      — user has a script and wants it modified/explained
  full_pipeline  — standard analysis: Research → Coder → Synthesizer
  chat           — conversational, no pipeline needed

Uses gemini/gemini-2.5-flash via llm.stream_completion() for fast routing.
"""

import json
import re

from .memory import shared_memory, AgentType
from .llm import stream_completion


SYSTEM_PROMPT = """You are a routing supervisor for a geospatial analysis assistant.

Given a user message, classify the intent into exactly one of:
- full_pipeline: user wants a complete geospatial analysis (research + code + report)
- research_only: user wants information, documentation, or methodology (no code)
- code_only: user has code and wants it modified, explained, or debugged
- chat: general conversation, greetings, or questions about the system

Respond with ONLY a JSON object: {"intent": "<category>", "reason": "<one-line reason>"}"""


class SupervisorAgent:
    """
    Supervisor Agent — fast intent routing via gemini-2.5-flash.

    Streams its decision to the thought log so users can see the routing choice.
    """

    def _stream(self, content: str) -> None:
        shared_memory.add_thought(AgentType.PLANNER, f"📋 Supervisor: {content}")

    async def route(self, message: str) -> str:
        """
        Classify user intent and return one of:
          "full_pipeline" | "research_only" | "code_only" | "chat"

        Falls back to "full_pipeline" if classification fails.
        """
        self._stream(f"Routing intent for: {message[:80]}...")

        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": message},
        ]

        raw = ""
        try:
            async for event in stream_completion("supervisor", messages):
                if event["kind"] == "text":
                    raw += event["content"]

            # Extract JSON from response
            match = re.search(r'\{[^{}]*"intent"[^{}]*\}', raw, re.DOTALL)
            if match:
                result = json.loads(match.group())
                intent = result.get("intent", "full_pipeline")
                reason = result.get("reason", "")
                if intent not in ("full_pipeline", "research_only", "code_only", "chat"):
                    intent = "full_pipeline"
                self._stream(f"→ Routing to {intent} ({reason})")
                return intent

        except Exception as exc:
            self._stream(f"⚠️ Routing failed ({exc}), defaulting to full_pipeline")

        return "full_pipeline"


# Singleton
supervisor_agent = SupervisorAgent()
