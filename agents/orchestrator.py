"""
Agent Orchestrator — coordinates the Planner → Researcher → Coder → Synthesizer pipeline.
"""

from typing import Optional

from .memory import shared_memory
from .chat_agent import chat_agent
from .researcher import researcher_agent
from .coder import coder_agent
from .planner import planner_agent
from .synthesizer import synthesizer_agent


class AgentOrchestrator:
    def __init__(self):
        self.chat = chat_agent
        self.researcher = researcher_agent
        self.coder = coder_agent
        self.planner = planner_agent
        self.synthesizer = synthesizer_agent
    
    async def process_user_message(self, message: str) -> dict:
        """Main entry point for user messages. Routes through Chat Agent."""
        return await self.chat.process_message(message)

    async def run_full_analysis(self, query: str, use_deep_research: bool = False, context_urls: list = None) -> dict:
        """
        Run a complete analysis pipeline with all agents.
        
        Args:
            query: Analysis query
            use_deep_research: Whether to use Deep Research mode
            context_urls: Optional list of URLs to read as research context
        
        Returns:
            Complete analysis results including methodology report
        """
        # Step 0: Plan the mission (decompose into tasks)
        tasks = await self.planner.plan(query)
        
        # Step 1: Research methodology and datasets (with optional URL context)
        research_result = await self.researcher.research(
            query, 
            use_deep_research,
            context_urls=context_urls
        )
        
        # Get accumulated research context for downstream agents
        research_summary = shared_memory.get_research_summary()

        # Step 2: Generate code (with full research context passed explicitly)
        code_result = await self.coder.generate_script(
            query,
            research_result
        )

        # Step 3: Synthesize methodology report with validated sources
        methodology = await self.synthesizer.synthesize(
            research_result, 
            code_result,
            sources=research_summary.get("sources", [])
        )
        
        return {
            "tasks": tasks,
            "research": research_result,
            "code": code_result,
            "methodology": methodology,
            "sources": research_summary.get("sources", []),
            "search_queries": research_summary.get("search_queries", []),
            "context": shared_memory.get_full_context()
        }


# Singleton
orchestrator = AgentOrchestrator()
