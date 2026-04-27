"""
Agent Orchestrator — coordinates the Planner → Researcher → Coder → Validator → Synthesizer pipeline.

The Coder/Validator pair runs in a retry loop (max 3 attempts): if the Validator
finds errors, the error summary is fed back to the Coder as a follow-up message.
"""

from typing import Optional

from .memory import shared_memory, AgentType
from .chat_agent import chat_agent
from .researcher import researcher_agent
from .coder import coder_agent
from .planner import planner_agent
from .synthesizer import synthesizer_agent
from .validator import validator_agent

MAX_RETRIES = 3


class AgentOrchestrator:
    def __init__(self):
        self.chat = chat_agent
        self.researcher = researcher_agent
        self.coder = coder_agent
        self.planner = planner_agent
        self.synthesizer = synthesizer_agent
        self.validator = validator_agent

    async def process_user_message(self, message: str) -> dict:
        """Main entry point for user messages. Routes through Chat Agent."""
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
            query:            Analysis query from the user
            use_deep_research: Use Deep Research mode for the Researcher
            context_urls:     Optional URL list for URL-context grounding

        Returns:
            Complete analysis results dict
        """
        # Step 0: Plan the mission
        tasks = await self.planner.plan(query)

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
            "tasks": tasks,
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
        Run the Coder then validate output; retry on validation failure.

        On each retry the error summary is appended to the research context so
        the Coder knows what to fix. Caps at max_retries attempts and returns
        the last result even if still invalid, including the final error list.
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
                break  # Coder itself failed — no point retrying without different context

            code = code_result.get("code", "")
            validation = await self.validator.validate(code)

            last_result = code_result
            last_errors = validation["errors"]

            if validation["valid"]:
                break  # Code passed validation

            if attempt < max_retries:
                error_summary = "; ".join(validation["errors"][:3])
                shared_memory.add_thought(
                    AgentType_from_import(),
                    f"🔄 Retry {attempt}/{max_retries} — fixing: {error_summary}",
                )
                # Feed errors back to the Coder via research context
                current_research = dict(research_result)
                current_research["_validation_errors"] = validation["errors"]
                current_research["research"] = (
                    research_result.get("research", "")
                    + f"\n\n⚠️ Previous code had these validation errors — fix them:\n"
                    + "\n".join(f"- {e}" for e in validation["errors"])
                )
            else:
                shared_memory.add_thought(
                    AgentType_from_import(),
                    f"⚠️ Exhausted {max_retries} retries — returning last result with errors noted",
                )

        if last_errors:
            last_result["_validation_errors"] = last_errors

        return last_result


# Singleton
orchestrator = AgentOrchestrator()
