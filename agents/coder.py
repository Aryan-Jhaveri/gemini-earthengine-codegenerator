"""
Coder Agent

Uses Gemini Thinking Mode to generate Earth Engine scripts.
Has access to EE tools for real-time schema verification.
Can ask Researcher agent questions when needed.
"""

import google.generativeai as genai
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
        genai.configure(api_key=self.api_key)
        
        # Model with Thinking capability
        self.model_name = "gemini-2.5-pro-preview-06-05"
        
        self.system_prompt = """You are an expert Google Earth Engine JavaScript programmer.

Your task is to generate complete, copy-paste ready Earth Engine scripts.

Rules:
1. Always use exact band names from the schema provided
2. Include cloud masking for optical imagery
3. Add clear comments explaining each step
4. Use proper date filtering
5. Always add Map.addLayer() to visualize results
6. Set appropriate visualization parameters
7. Export results to Drive when appropriate

Output format:
- Return ONLY the JavaScript code
- Code should be immediately runnable in Earth Engine Code Editor
- Include all necessary variable definitions
- No markdown code blocks, just raw code"""

    def _stream_thought(self, content: str) -> None:
        """Stream a thought to shared memory."""
        shared_memory.add_thought(AgentType.CODER, content)
    
    def _get_ee_context(self, dataset_ids: list[str]) -> dict:
        """Get schema and preview for datasets."""
        context = {}
        
        for dataset_id in dataset_ids:
            self._stream_thought(f"Verifying schema for {dataset_id}")
            schema = get_band_schema(dataset_id)
            if "error" not in schema:
                context[dataset_id] = schema
                self._stream_thought(f"Bands available: {schema.get('band_names', [])}")
        
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
        
        prompt = f"""
Task: {task}

Research Context:
{research_context.get('research', 'No additional research provided') if research_context else 'None'}

Available Datasets and Schemas:
{schema_info}

Generate a complete Earth Engine JavaScript script that:
1. Uses the correct band names from the schemas above
2. Implements the requested analysis
3. Is ready to copy-paste into the Code Editor
4. Includes visualization with Map.addLayer()

Return ONLY the JavaScript code, no explanations.
"""
        
        self._stream_thought("Generating code with Thinking Mode...")
        
        try:
            model = genai.GenerativeModel(
                model_name=self.model_name,
                system_instruction=self.system_prompt
            )
            
            if use_thinking:
                # Use thinking config for step-by-step reasoning
                generation_config = genai.GenerationConfig(
                    temperature=0.7,
                    top_p=0.95,
                )
                
                # Generate with thinking
                response = model.generate_content(
                    prompt,
                    generation_config=generation_config
                )
            else:
                response = model.generate_content(prompt)
            
            code = response.text
            
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
                "schemas": ee_context
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
        
        model = genai.GenerativeModel(
            model_name=self.model_name,
            system_instruction=self.system_prompt
        )
        
        response = model.generate_content(prompt)
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
