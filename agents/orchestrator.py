"""
Agent Orchestrator

Coordinates autonomous agent collaboration.
Manages back-and-forth communication between agents.
"""

import asyncio
from typing import Optional

from .memory import shared_memory, AgentType, MessageType
from .chat_agent import chat_agent
from .researcher import researcher_agent
from .coder import coder_agent
from .planner import planner_agent
from .synthesizer import synthesizer_agent


class AgentOrchestrator:
    """
    Coordinates multi-agent collaboration.
    
    Handles:
    - Autonomous agent back-and-forth
    - Pending question resolution
    - Task completion tracking
    """
    
    def __init__(self):
        self.chat = chat_agent
        self.researcher = researcher_agent
        self.coder = coder_agent
        self.planner = planner_agent
        self.synthesizer = synthesizer_agent
        self._running = False
    
    async def process_user_message(self, message: str) -> dict:
        """
        Main entry point for user messages.
        Routes through Chat Agent and manages agent collaboration.
        
        Args:
            message: User message
        
        Returns:
            Response dict
        """
        # Process through Chat Agent
        response = await self.chat.process_message(message)
        
        # Check for any pending inter-agent questions and resolve them
        await self._resolve_pending_questions()
        
        return response
    
    async def _resolve_pending_questions(self, max_rounds: int = 3) -> None:
        """
        Resolve any pending questions between agents.
        Allows autonomous back-and-forth.
        """
        for _ in range(max_rounds):
            # Check Researcher for pending questions
            researcher_questions = self.researcher.check_pending_questions()
            for q in researcher_questions:
                await self.researcher.answer_question(q.content, q.from_agent)
            
            # Check if Coder has any pending questions
            coder_questions = shared_memory.get_pending_questions(AgentType.CODER)
            # Coder questions would be answered by Researcher
            
            # If no pending questions, we're done
            if not researcher_questions and not coder_questions:
                break
            
            await asyncio.sleep(0.1)  # Brief pause between rounds
    
    async def run_full_analysis(self, query: str, use_deep_research: bool = False) -> dict:
        """
        Run a complete analysis pipeline with all agents.
        
        Args:
            query: Analysis query
            use_deep_research: Whether to use Deep Research mode
        
        Returns:
            Complete analysis results including methodology report
        """
        # Step 0: Plan the mission (decompose into tasks)
        tasks = await self.planner.plan(query)
        
        # Step 1: Research methodology and datasets
        research_result = await self.researcher.research(query, use_deep_research)
        
        # Resolve any questions from research phase
        await self._resolve_pending_questions()
        
        # Step 2: Generate code
        code_result = await self.coder.generate_script(query, research_result)
        
        # Resolve any questions from coding phase
        await self._resolve_pending_questions()
        
        # Step 3: Synthesize methodology report with citations
        methodology = await self.synthesizer.synthesize(research_result, code_result)
        
        return {
            "tasks": tasks,
            "research": research_result,
            "code": code_result,
            "methodology": methodology,
            "context": shared_memory.get_full_context()
        }


# Singleton
orchestrator = AgentOrchestrator()
