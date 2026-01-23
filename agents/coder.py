"""
Coder Agent

Uses Gemini Thinking Mode to generate Earth Engine scripts.
Has access to EE tools for real-time schema verification.
Can ask Researcher agent questions when needed.
"""

from google import genai
from google.genai import types
from typing import Optional
import os
import re

from .memory import shared_memory, AgentType, MessageType
from .tools.ee_tools import browse_datasets, get_band_schema, preview_collection, get_dataset_docs


class CoderAgent:
    """
    Coder Agent with Thinking Mode and EE Tools.
    
    Capabilities:
    - Generate Earth Engine JavaScript code
    - Use Thinking Mode for step-by-step reasoning
    - Verify band names/schemas before coding
    - Ask Researcher for clarification when needed
    """
    
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("GOOGLE_API_KEY")
        # genai.configure(api_key=self.api_key)
        
        # Model with Thinking capability
        self.model_name = "gemini-3-pro-preview"
        
        self.system_prompt = """You are an expert Google Earth Engine JavaScript programmer.

Your task is to generate complete, copy-paste ready Earth Engine scripts.

CRITICAL REQUIREMENTS:
1. **Visualizations**: You MUST define `visParams` with min, max, and specific color palettes.
2. **Legends**: Add a legend to the map using `ui.Panel` and `ui.Label` to explain the colors.
3. **Date Filtering**: Use specific date ranges.
4. **Best Practices**: Add comments explaining every major step.
5. **Geometry**: If no geometry is provided, create a `point` or `bounds` geometry from the coordinates.
6. **Source Citations**: When using methodology from research, cite sources in code comments:
   // Methodology based on: [1] Source Title
   // Reference: [2] Another Source

Output format:
- Return ONLY the JavaScript code
- Include source citations in comments where relevant
- Code should be immediately runnable in Earth Engine Code Editor
- Include all necessary variable definitions
- No markdown code blocks, just raw code"""

    def _stream_thought(self, content: str) -> None:
        """Stream a completed thought to shared memory."""
        shared_memory.add_thought(AgentType.CODER, content)

    def _stream_chunk(self, content: str) -> None:
        """Stream a chunk of text to shared memory."""
        shared_memory.add_stream_update(AgentType.CODER, content)
    
    def _get_ee_context(self, dataset_ids: list[str]) -> dict:
        """Get schema and preview for datasets."""
        context = {}
        
        for dataset_id in dataset_ids:
            shared_memory.add_tool_call(AgentType.CODER, "get_band_schema", dataset_id)
            schema = get_band_schema(dataset_id)
            if "error" not in schema:
                context[dataset_id] = schema
                self._stream_thought(f"📊 Bands: {schema.get('band_names', [])}")
        
        return context
    
    async def ask_researcher(self, question: str) -> str:
        """
        Ask the Researcher agent a question.
        
        Args:
            question: Question to ask
        
        Returns:
            Answer from Researcher
        """
        self._stream_thought(f"Asking Researcher: {question}")
        
        # Record question
        shared_memory.add_agent_message(
            from_agent=AgentType.CODER,
            to_agent=AgentType.RESEARCHER,
            message_type=MessageType.QUESTION,
            content=question
        )
        
        # Import here to avoid circular import
        from .researcher import researcher_agent
        
        answer = await researcher_agent.answer_question(question, AgentType.CODER)
        
        self._stream_thought(f"Researcher answered: {answer[:100]}...")
        
        return answer
    
    async def generate_script(
        self,
        task: str,
        research_context: Optional[dict] = None,
        use_thinking: bool = True
    ) -> dict:
        """
        Generate an Earth Engine script.
        
        Args:
            task: Description of what the script should do
            research_context: Optional context from Researcher
            use_thinking: Whether to use Thinking Mode
        
        Returns:
            Dict with code and metadata
        """
        self._stream_thought(f"Starting code generation: {task}")
        
        # Get datasets from research context or discover them
        if research_context and "datasets" in research_context:
            datasets = research_context["datasets"]
            dataset_ids = [d["id"] for d in datasets]
        else:
            self._stream_thought("No research context, discovering datasets...")
            datasets = browse_datasets(task)
            dataset_ids = [d["id"] for d in datasets]
        
        # Verify schemas
        ee_context = self._get_ee_context(dataset_ids[:3])
        
        # Build the prompt with full context
        schema_info = "\n".join([
            f"Dataset: {ds_id}\nBands: {info.get('band_names', [])}"
            for ds_id, info in ee_context.items()
        ])
        
        # Build sources string for citation context
        sources_text = ""
        if research_context and "sources" in research_context:
            sources = research_context.get("sources", [])
            if sources:
                sources_text = "\n\nResearch Sources (cite these in code comments using [1], [2], etc.):\n" + "\n".join([
                    f"[{i+1}] {s.get('title', 'Unknown Source')}: {s.get('uri', '')}"
                    for i, s in enumerate(sources[:5])  # Top 5 sources
                ])
                self._stream_thought(f"📚 Including {len(sources[:5])} sources for citation")
        
        prompt = f"""
Task: {task}

Research Context:
{research_context.get('research', 'No additional research provided') if research_context else 'None'}
{sources_text}

Available Datasets and Schemas:
{schema_info}

Generate a complete Earth Engine JavaScript script that:
1. Uses the correct band names from the schemas above
2. Implements the requested analysis
3. Is ready to copy-paste into the Code Editor
4. Includes visualization with Map.addLayer()
5. Adds comments citing sources [1], [2] where methodology is referenced

Return ONLY the JavaScript code, no explanations.
"""
        
        self._stream_thought("Generating code with Thinking Mode...")
        
        try:
            client = genai.Client(api_key=self.api_key)
            
            prompt_content = prompt
            
            # Streaming generation
            # new SDK: client.models.generate_content_stream
            
            # Config with Thinking Mode enabled
            config = types.GenerateContentConfig(
                temperature=0.7,
                top_p=0.95,
                system_instruction=self.system_prompt,
                thinking_config=types.ThinkingConfig(
                    include_thoughts=True,
                    thinking_budget=2048
                )
            )

            # We'll collect the full code
            full_response_text = ""
            thought_count = 0
            
            # Using generate_content_stream
            response_stream = client.models.generate_content_stream(
                model=self.model_name,
                contents=prompt_content,
                config=config
            )

            # Initialize a thought bubble for the stream
            self._stream_thought("💭 Thinking Process Started...")

            for chunk in response_stream:
                # Check for thought parts (from Thinking Mode)
                if hasattr(chunk, 'candidates') and chunk.candidates:
                    for candidate in chunk.candidates:
                        if hasattr(candidate, 'content') and candidate.content:
                            for part in candidate.content.parts:
                                # Check if this is a thought part
                                if hasattr(part, 'thought') and part.thought:
                                    thought_count += 1
                                    self._stream_thought(f"💭 [{thought_count}] {part.text[:200]}..." if len(part.text) > 200 else f"💭 [{thought_count}] {part.text}")
                                elif hasattr(part, 'text') and part.text:
                                    text_chunk = part.text
                                    full_response_text += text_chunk
                                    self._stream_chunk(text_chunk)
                elif chunk.text:
                    # Fallback for simple text response
                    text_chunk = chunk.text
                    full_response_text += text_chunk
                    self._stream_chunk(text_chunk)
            
            if thought_count > 0:
                self._stream_thought(f"✅ Completed {thought_count} thinking steps")
            
            code = full_response_text
            
            # Get token usage if available (requires iterating to end)
            try:
                count_resp = client.models.count_tokens(
                    model=self.model_name,
                    contents=prompt_content
                )
                self._stream_thought(f"Token Analysis - Input Token Count: {count_resp.total_tokens}")
                
            except Exception as tok_err:
                print(f"Token count error: {tok_err}")

            # Clean up code (remove markdown if present)
            code = self._clean_code(code)
            
            self._stream_thought("Code generation complete!")
            
            # Store the script
            script = shared_memory.add_script(
                code=code,
                description=task,
                datasets=dataset_ids
            )
            
            return {
                "code": code,
                "description": task,
                "datasets_used": dataset_ids,
                "schemas": ee_context,
                "token_usage": count_resp.total_tokens if 'count_resp' in locals() else None
            }
            
        except Exception as e:
            error_msg = f"Code generation error: {str(e)}"
            self._stream_thought(error_msg)
            return {"error": error_msg}
    
    def _clean_code(self, code: str) -> str:
        """Remove markdown code blocks if present."""
        # Remove ```javascript ... ``` blocks
        code = re.sub(r'^```(?:javascript|js)?\n?', '', code, flags=re.MULTILINE)
        code = re.sub(r'\n?```$', '', code, flags=re.MULTILINE)
        return code.strip()
    
    def refine_script(self, original_code: str, refinement_request: str) -> str:
        """
        Refine an existing script based on user feedback.
        
        Args:
            original_code: The original script
            refinement_request: What to change
        
        Returns:
            Refined code
        """
        self._stream_thought(f"Refining script: {refinement_request}")
        
        prompt = f"""
Original Earth Engine Script:
```javascript
{original_code}
```

Refinement Request: {refinement_request}

Provide the updated script with the requested changes.
Return ONLY the JavaScript code.
"""
        
        client = genai.Client(api_key=self.api_key)
        
        response = client.models.generate_content(
            model=self.model_name,
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction=self.system_prompt
            )
        )
        refined_code = self._clean_code(response.text)
        
        # Update stored script
        shared_memory.add_script(
            code=refined_code,
            description=f"Refined: {refinement_request}",
            datasets=[]
        )
        
        self._stream_thought("Script refined!")
        
        return refined_code


# Singleton instance
coder_agent = CoderAgent()
