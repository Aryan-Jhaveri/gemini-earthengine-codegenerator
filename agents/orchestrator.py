"""
Agent Orchestrator — Supervisor → Researcher → Coder ↔ Validator → Synthesizer.

The Supervisor routes intent; for full_pipeline and code_only intents the
Coder/Validator pair runs in a retry loop (max 3 attempts).
"""

from .memory import shared_memory, AgentType
from .chat_agent import chat_agent
from .researcher import researcher_agent
from .coder import coder_agent
from .synthesizer import synthesizer_agent
from .validator import validator_agent
from .supervisor import supervisor_agent

MAX_RETRIES = 3


class AgentOrchestrator:
    def __init__(self):
        self.chat = chat_agent
        self.researcher = researcher_agent
        self.coder = coder_agent
        self.synthesizer = synthesizer_agent
        self.validator = validator_agent
        self.supervisor = supervisor_agent

    async def process_user_message(self, message: str) -> dict:
        """
        Main entry point. The Supervisor classifies intent:
          - chat         → handled directly by Chat Agent (no pipeline)
          - full_pipeline / research_only / code_only → Chat Agent delegates to pipeline
        """
        intent = await self.supervisor.route(message)

        if intent == "chat":
            # Conversational response — skip Research/Coder/Synthesizer entirely
            return await self.chat._handle_general(message)

        # For all other intents, let the Chat Agent handle classification and delegation
        return await self.chat.process_message(message)

    async def run_full_analysis(
        self,
        query: str,
        use_deep_research: bool = False,
        context_urls: list = None,
    ) -> dict:
        """
        Run the full analysis pipeline:
          Planner → Researcher → Coder ↔ Validator (retry loop) → Synthesizer

        Args:
            query:             Analysis query from the user
            use_deep_research: Use Deep Research mode for the Researcher
            context_urls:      Optional URL list for URL-context grounding

        Returns:
            Complete analysis results dict
        """
        # Step 1: Research
        research_result = await self.researcher.research(
            query,
            use_deep_research,
            context_urls=context_urls,
        )
        research_summary = shared_memory.get_research_summary()

        # Step 2: Coder → Validator retry loop
        code_result = await self._run_coder_with_validation(query, research_result)

        # Step 3: Synthesize
        methodology = await self.synthesizer.synthesize(
            research_result,
            code_result,
            sources=research_summary.get("sources", []),
        )

        return {
            "research": research_result,
            "code": code_result,
            "methodology": methodology,
            "sources": research_summary.get("sources", []),
            "search_queries": research_summary.get("search_queries", []),
            "context": shared_memory.get_full_context(),
        }

    async def _run_coder_with_validation(
        self,
        query: str,
        research_result: dict,
        max_retries: int = MAX_RETRIES,
    ) -> dict:
        """
        Run the Coder then validate; retry on failure up to max_retries times.

        Validation errors are injected back into the research context so the Coder
        knows exactly what to fix on the next attempt.
        """
        current_research = research_result
        last_result: dict = {}
        last_errors: list[str] = []

        for attempt in range(1, max_retries + 1):
            shared_memory.add_thought(
                AgentType.PLANNER,
                f"💻 Coder attempt {attempt}/{max_retries}...",
            )

            code_result = await self.coder.generate_script(query, current_research)

            if "error" in code_result:
                last_result = code_result
                last_errors = [code_result["error"]]
                break  # Coder itself failed — retrying without new context is pointless

            code = code_result.get("code", "")
            validation = await self.validator.validate(code)

            last_result = code_result
            last_errors = validation["errors"]

            if validation["valid"]:
                break

            if attempt < max_retries:
                error_summary = "; ".join(validation["errors"][:3])
                shared_memory.add_thought(
                    AgentType.PLANNER,
                    f"🔄 Retry {attempt}/{max_retries} — fixing: {error_summary}",
                )
                current_research = dict(research_result)
                current_research["_validation_errors"] = validation["errors"]
                current_research["research"] = (
                    research_result.get("research", "")
                    + "\n\n⚠️ Previous code had validation errors — fix them:\n"
                    + "\n".join(f"- {e}" for e in validation["errors"])
                )
            else:
                shared_memory.add_thought(
                    AgentType.PLANNER,
                    f"⚠️ Exhausted {max_retries} retries — returning last result with errors noted",
                )

        if last_errors:
            last_result["_validation_errors"] = last_errors

        return last_result


# Singleton
orchestrator = AgentOrchestrator()
