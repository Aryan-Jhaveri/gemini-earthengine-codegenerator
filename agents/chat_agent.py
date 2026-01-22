"""
Chat Agent

User-facing agent with full memory access.
Delegates to Researcher/Coder for analysis tasks.
Refines scripts when user asks.
Answers questions using stored context.
"""

import google.generativeai as genai
from typing import Optional
import os

from .memory import shared_memory, AgentType, MessageType


class ChatAgent:
    """
    Chat Agent - User Interface Layer.
    
    Capabilities:
    - Natural language conversation
    - Full access to shared memory (all agent context)
    - Delegate to Researcher/Coder for new tasks
    - Refine scripts when asked
    - Answer questions about previous research/code
    """
    
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("GOOGLE_API_KEY")
        genai.configure(api_key=self.api_key)
        
        self.model_name = "gemini-1.5-pro"
        
        self.system_prompt = """You are a helpful Geospatial Analysis Assistant for Google Earth Engine.

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

    def _stream_thought(self, content: str) -> None:
        """Stream a thought to shared memory."""
        shared_memory.add_thought(AgentType.CHAT, content)
    
    def _classify_intent(self, message: str) -> str:
        """
        Classify user intent to determine routing.
        
        Returns:
            "new_analysis" - needs Researcher + Coder
            "refine_script" - modify existing script
            "question" - answer from context
            "general" - general conversation
        """
        message_lower = message.lower()
        
        # Keywords for new analysis
        analysis_keywords = [
            "analyze", "show me", "detect", "find", "calculate",
            "create a map", "generate", "visualize", "monitor",
            "ndvi", "deforestation", "flood", "fire", "change detection"
        ]
        
        # Keywords for refinement
        refine_keywords = [
            "change the", "modify", "update", "fix", "adjust",
            "add", "remove", "instead", "rather than", "make it"
        ]
        
        # Check for refinement first
        if any(kw in message_lower for kw in refine_keywords):
            if shared_memory.get_latest_script():
                return "refine_script"
        
        # Check for new analysis
        if any(kw in message_lower for kw in analysis_keywords):
            return "new_analysis"
        
        # Check if it's a question about existing work
        if "?" in message or message_lower.startswith(("what", "how", "why", "which", "can you explain")):
            return "question"
        
        return "general"
    
    async def process_message(self, message: str) -> dict:
        """
        Process a user message and route appropriately.
        
        Args:
            message: User message
        
        Returns:
            Response dict with type and content
        """
        self._stream_thought(f"Processing user message: {message[:50]}...")
        
        # Store in conversation history
        shared_memory.add_conversation_turn("user", message)
        
        # Classify intent
        intent = self._classify_intent(message)
        self._stream_thought(f"Classified intent: {intent}")
        
        if intent == "new_analysis":
            return await self._handle_new_analysis(message)
        elif intent == "refine_script":
            return await self._handle_refinement(message)
        elif intent == "question":
            return await self._handle_question(message)
        else:
            return await self._handle_general(message)
    
    async def _handle_new_analysis(self, message: str) -> dict:
        """Delegate to Researcher and Coder for new analysis."""
        self._stream_thought("This is a new analysis request, delegating to agents...")
        
        # Import agents
        from .researcher import researcher_agent
        from .coder import coder_agent
        
        # Step 1: Research
        self._stream_thought("Asking Researcher to gather context...")
        research_result = await researcher_agent.research(message)
        
        # Step 2: Generate code
        self._stream_thought("Asking Coder to generate script...")
        code_result = await coder_agent.generate_script(message, research_result)
        
        if "error" in code_result:
            response_text = f"I encountered an error: {code_result['error']}"
            return {"type": "error", "content": response_text}
        
        # Build response
        response_text = f"""I've generated an Earth Engine script for your analysis.

**Datasets used:** {', '.join(code_result.get('datasets_used', [])[:3])}

You can copy the script below and paste it into the [Earth Engine Code Editor](https://code.earthengine.google.com)."""
        
        shared_memory.add_conversation_turn("assistant", response_text)
        
        return {
            "type": "analysis_complete",
            "content": response_text,
            "code": code_result["code"],
            "datasets": code_result.get("datasets_used", [])
        }
    
    async def _handle_refinement(self, message: str) -> dict:
        """Refine the existing script."""
        self._stream_thought("User wants to refine the script...")
        
        current_script = shared_memory.get_latest_script()
        if not current_script:
            return {
                "type": "error",
                "content": "No script to refine. Please request an analysis first."
            }
        
        from .coder import coder_agent
        
        refined_code = coder_agent.refine_script(
            current_script.code,
            message
        )
        
        response_text = "I've updated the script based on your request."
        shared_memory.add_conversation_turn("assistant", response_text)
        
        return {
            "type": "refinement_complete",
            "content": response_text,
            "code": refined_code
        }
    
    async def _handle_question(self, message: str) -> dict:
        """Answer a question using stored context."""
        self._stream_thought("Answering question from context...")
        
        # Get full context
        context = shared_memory.get_full_context()
        
        # Build context summary
        context_summary = f"""
Recent Research: {context.get('research_context', {}).get('latest_research', {}).get('query', 'None')}

Recent Scripts Generated: {len(context.get('code_outputs', []))}

Agent Messages: {len(context.get('agent_messages', []))}
"""
        
        prompt = f"""
User Question: {message}

Available Context:
{context_summary}

Full Research Context:
{context.get('research_context', {})}

Recent Code Outputs:
{[s.get('description', '') for s in context.get('code_outputs', [])[-3:]]}

Provide a helpful answer based on this context.
"""
        
        model = genai.GenerativeModel(
            model_name=self.model_name,
            system_instruction=self.system_prompt
        )
        
        response = model.generate_content(prompt)
        answer = response.text
        
        shared_memory.add_conversation_turn("assistant", answer)
        
        return {
            "type": "question_answered",
            "content": answer
        }
    
    async def _handle_general(self, message: str) -> dict:
        """Handle general conversation."""
        self._stream_thought("General conversation...")
        
        model = genai.GenerativeModel(
            model_name=self.model_name,
            system_instruction=self.system_prompt
        )
        
        # Include recent conversation for context
        history = shared_memory.conversation_history[-5:]
        history_text = "\n".join([f"{h['role']}: {h['content']}" for h in history])
        
        prompt = f"""
Recent Conversation:
{history_text}

User: {message}

Respond helpfully.
"""
        
        response = model.generate_content(prompt)
        answer = response.text
        
        shared_memory.add_conversation_turn("assistant", answer)
        
        return {
            "type": "general",
            "content": answer
        }


# Singleton instance
chat_agent = ChatAgent()
