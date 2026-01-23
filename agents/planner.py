"""
Planner Agent - Task Decomposition

Breaks down user missions into structured sub-tasks for parallel/sequential execution.
Streams task breakdown to UI for transparency.
"""

from google import genai
from google.genai import types
from typing import Optional
import os
import json

from .memory import shared_memory, AgentType


class PlannerAgent:
    """
    Planner Agent for task decomposition.
    
    Capabilities:
    - Break down missions into parallel/sequential sub-tasks
    - Identify dependencies between tasks
    - Stream task breakdown to UI
    """
    
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("GOOGLE_API_KEY")
        self.model_name = "gemini-3-pro-preview"
        
        self.system_prompt = """You are a task planning agent for geospatial analysis missions.

Break down user missions into clear, actionable sub-tasks:
1. Research methodology (parallel with dataset discovery)
2. Dataset discovery (parallel with methodology research)
3. Code generation (depends on 1 & 2)
4. Synthesis/reporting (depends on 3)

Return structured JSON with task dependencies and parallel execution flags."""

    def _stream_thought(self, content: str) -> None:
        """Stream a thought to shared memory."""
        shared_memory.add_thought(AgentType.PLANNER, content)
    
    async def plan(self, mission: str) -> list[dict]:
        """
        Decompose mission into structured sub-tasks.
        
        Args:
            mission: User's geospatial analysis mission
        
        Returns:
            List of task dictionaries with dependencies
        """
        self._stream_thought(f"📋 Planning mission: {mission[:80]}...")
        
        prompt = f"""
Break down this geospatial analysis mission into sub-tasks:

Mission: {mission}

Return a JSON array of tasks in this exact format:
[
  {{"task": "research_methodology", "description": "Research best practices and methodologies", "parallel": true}},
  {{"task": "find_datasets", "description": "Identify Earth Engine datasets", "parallel": true}},
  {{"task": "generate_code", "description": "Generate Earth Engine JavaScript", "depends_on": ["research_methodology", "find_datasets"]}},
  {{"task": "synthesize_report", "description": "Create methodology report with citations", "depends_on": ["generate_code"]}}
]

Keep descriptions concise (under 80 characters).
"""
        
        try:
            client = genai.Client(api_key=self.api_key)
            
            # Config with Thinking Mode
            config = types.GenerateContentConfig(
                system_instruction=self.system_prompt,
                response_mime_type="application/json",
                thinking_config=types.ThinkingConfig(
                    include_thoughts=True,
                    thinking_budget=1024
                )
            )
            
            self._stream_thought("💭 Analyzing mission requirements...")
            
            # Use sync streaming wrapped in thread to not block event loop
            import asyncio
            
            def run_streaming():
                """Run sync streaming in a thread."""
                thought_count = 0
                json_result = ""
                
                response_stream = client.models.generate_content_stream(
                    model=self.model_name,
                    contents=prompt,
                    config=config
                )
                
                for chunk in response_stream:
                    if hasattr(chunk, 'candidates') and chunk.candidates:
                        for candidate in chunk.candidates:
                            if hasattr(candidate, 'content') and candidate.content:
                                for part in candidate.content.parts:
                                    if hasattr(part, 'thought') and part.thought:
                                        thought_count += 1
                                        thought_preview = part.text[:150] + "..." if len(part.text) > 150 else part.text
                                        self._stream_thought(f"💭 [{thought_count}] {thought_preview}")
                                    elif hasattr(part, 'text') and part.text:
                                        json_result += part.text
                    elif chunk.text:
                        json_result += chunk.text
                
                return json_result, thought_count
            
            # Run in thread to avoid blocking event loop
            json_result, thought_count = await asyncio.to_thread(run_streaming)
            
            if thought_count > 0:
                self._stream_thought(f"✅ Completed {thought_count} thinking steps")
            
            # Token counting
            try:
                count_resp = client.models.count_tokens(
                    model=self.model_name,
                    contents=prompt
                )
                self._stream_thought(f"📊 Token Analysis - Input Token Count: {count_resp.total_tokens}")
            except Exception as tok_err:
                print(f"Token count error: {tok_err}")
            
            tasks = json.loads(json_result)
            
            # Stream individual tasks
            for i, task in enumerate(tasks):
                parallel_text = "🔄 parallel" if task.get("parallel", False) else "⏭️ sequential"
                deps_text = f" (after: {', '.join(task.get('depends_on', []))})" if task.get("depends_on") else ""
                
                self._stream_thought(
                    f"📌 [{i+1}] {task['task']}: {task['description'][:60]}... {parallel_text}{deps_text}"
                )
            
            self._stream_thought(f"✅ Created {len(tasks)} tasks")
            
            return tasks
            
        except Exception as e:
            error_msg = f"Planning error: {str(e)}"
            self._stream_thought(error_msg)
            return []


# Singleton instance
planner_agent = PlannerAgent()
