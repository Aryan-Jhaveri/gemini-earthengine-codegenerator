"""
Chat Agent

User-facing agent with full memory access.
Delegates to Researcher/Coder for analysis tasks.
Refines scripts when user asks.
Answers questions using stored context.

Now uses llm.stream_completion("chat", ...) — gemini/gemini-2.5-flash.
"""

from typing import Optional

from .memory import shared_memory, AgentType, MessageType
from .llm import stream_completion


SYSTEM_PROMPT = """You are a helpful Geospatial Analysis Assistant for Google Earth Engine.

Your role:
1. Understand user requests for geospatial analysis
2. Decide whether to delegate to Researcher or Coder agents
3. Answer questions using context from all agents
4. Help refine generated scripts when asked

When responding:
- Be concise and helpful
- Reference previous research or code when relevant
- Suggest improvements or alternatives when appropriate

You have access to:
- All thoughts from Researcher and Coder agents
- Research findings and methodologies
- Generated Earth Engine scripts
- Full conversation history

For new analysis tasks, delegate to the specialized agents.
For questions about existing work, use the stored context."""


class ChatAgent:
    """
    Chat Agent — User Interface Layer.

    Routes messages to the orchestrator's full pipeline or handles simple
    queries directly using gemini/gemini-2.5-flash via LiteLLM.
    """

    def _stream_thought(self, content: str) -> None:
        shared_memory.add_thought(AgentType.CHAT, content)

    def _classify_intent(self, message: str) -> str:
        """
        Classify user intent to determine routing.

        Returns one of:
          "new_analysis"  — needs Researcher + Coder
          "refine_script" — modify existing script
          "question"      — answer from context
          "general"       — general conversation
        """
        msg = message.lower()

        analysis_keywords = [
            "analyze", "show me", "detect", "find", "calculate",
            "create a map", "generate", "visualize", "monitor",
            "ndvi", "deforestation", "flood", "fire", "change detection",
        ]
        refine_keywords = [
            "change the", "modify", "update", "fix", "adjust",
            "add", "remove", "instead", "rather than", "make it",
        ]

        if any(kw in msg for kw in refine_keywords) and shared_memory.get_latest_script():
            return "refine_script"

        if "objective" in msg and "latitude" in msg:
            return "new_analysis"
        if "research objective:" in msg:
            return "new_analysis"
        if any(kw in msg for kw in analysis_keywords):
            return "new_analysis"
        if "?" in message or msg.startswith(("what", "how", "why", "which", "can you explain")):
            return "question"
        return "general"

    async def process_message(self, message: str) -> dict:
        """Process a user message and route appropriately."""
        self._stream_thought(f"Processing user message: {message[:50]}...")
        shared_memory.add_conversation_turn("user", message)

        intent = self._classify_intent(message)
        self._stream_thought(f"Classified intent: {intent}")

        if intent == "new_analysis":
            return await self._handle_new_analysis(message)
        if intent == "refine_script":
            return await self._handle_refinement(message)
        if intent == "question":
            return await self._handle_question(message)
        return await self._handle_general(message)

    async def _handle_new_analysis(self, message: str) -> dict:
        """Delegate to full agent pipeline for new analysis."""
        self._stream_thought("This is a new analysis request, delegating to agents...")
        from .orchestrator import orchestrator

        self._stream_thought("Running full analysis pipeline with all agents...")
        full_result = await orchestrator.run_full_analysis(message)

        research_result = full_result.get("research", {})
        code_result = full_result.get("code", {})
        methodology = full_result.get("methodology", {})

        if "error" in code_result:
            return {"type": "error", "content": f"I encountered an error: {code_result['error']}"}

        methodology_text = methodology.get("methodology") if methodology else None
        research_text = methodology_text or research_result.get("research", "No methodology available.")

        response_text = (
            f"{research_text}\n\n---\n**Analysis Summary**\n\n"
            "I've generated an Earth Engine script for your analysis based on the methodology above.\n\n"
            f"**Datasets used:** {', '.join(code_result.get('datasets_used', [])[:3])}\n\n"
            "You can copy the script from the 'Generated Code' tab and paste it into the "
            "[Earth Engine Code Editor](https://code.earthengine.google.com)."
        )

        shared_memory.add_conversation_turn("assistant", response_text)

        return {
            "type": "analysis_complete",
            "content": response_text,
            "code": code_result["code"],
            "datasets": code_result.get("datasets_used", []),
            "methodology": methodology,
        }

    async def _handle_refinement(self, message: str) -> dict:
        """Refine the existing script."""
        self._stream_thought("User wants to refine the script...")
        current_script = shared_memory.get_latest_script()
        if not current_script:
            return {"type": "error", "content": "No script to refine. Please request an analysis first."}

        from .coder import coder_agent
        refined_code = await coder_agent.refine_script(current_script.code, message)
        response_text = "I've updated the script based on your request."
        shared_memory.add_conversation_turn("assistant", response_text)
        return {"type": "refinement_complete", "content": response_text, "code": refined_code}

    async def _handle_question(self, message: str) -> dict:
        """Answer a question using stored context."""
        self._stream_thought("Answering question from context...")
        context = shared_memory.get_full_context()

        context_summary = (
            f"Recent Research: {context.get('research_context', {}).get('latest_research', {}).get('query', 'None')}\n"
            f"Recent Scripts Generated: {len(context.get('code_outputs', []))}\n"
            f"Agent Messages: {len(context.get('agent_messages', []))}"
        )

        prompt = (
            f"User Question: {message}\n\nAvailable Context:\n{context_summary}\n\n"
            f"Full Research Context:\n{context.get('research_context', {})}\n\n"
            f"Recent Code Outputs:\n{[s.get('description', '') for s in context.get('code_outputs', [])[-3:]]}\n\n"
            "Provide a helpful answer based on this context."
        )

        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ]

        answer = ""
        async for event in stream_completion("chat", messages):
            if event["kind"] == "text":
                answer += event["content"]

        shared_memory.add_conversation_turn("assistant", answer)
        return {"type": "question_answered", "content": answer}

    async def _handle_general(self, message: str) -> dict:
        """Handle general conversation."""
        self._stream_thought("General conversation...")
        history = shared_memory.conversation_history[-5:]
        history_text = "\n".join([f"{h['role']}: {h['content']}" for h in history])

        prompt = f"Recent Conversation:\n{history_text}\n\nUser: {message}\n\nRespond helpfully."
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ]

        answer = ""
        async for event in stream_completion("chat", messages):
            if event["kind"] == "text":
                answer += event["content"]

        shared_memory.add_conversation_turn("assistant", answer)
        return {"type": "general", "content": answer}


# Singleton instance
chat_agent = ChatAgent()
