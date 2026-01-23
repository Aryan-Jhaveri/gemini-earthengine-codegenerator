"""
Synthesizer Agent - Methodology Report with Citations

Compiles research findings into a structured methodology report with inline citations.
References sources as [1], [2], etc. for proper academic-style citation.
"""

from google import genai
from google.genai import types
from typing import Optional, Dict, Any
import os

from .memory import shared_memory, AgentType


class SynthesizerAgent:
    """
    Synthesizer Agent for methodology report generation.
    
    Capabilities:
    - Compile research findings with inline citations
    - Generate structured methodology sections
    - Reference sources as [1], [2], etc.
    - Create professional-looking reports
    """
    
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("GOOGLE_API_KEY")
        self.model_name = "gemini-3-pro-preview"
        
        self.system_prompt = """You are a research synthesizer for geospatial analysis.

Create clear, well-structured methodology reports with proper citations.
Use [1], [2] etc. for inline citations referencing the provided sources.

Report Structure:
1. **Overview** - What the analysis accomplishes
2. **Data Sources** - Satellite datasets used (cite sources)
3. **Methodology** - Step-by-step processing approach (cite sources)
4. **Expected Outputs** - What the user will see
5. **References** - Numbered list of all sources cited

Use academic writing style with clear sections and proper citations."""

    def _stream_thought(self, content: str) -> None:
        """Stream a thought to shared memory."""
        shared_memory.add_thought(AgentType.SYNTHESIZER, content)
    
    async def synthesize(
        self, 
        research_context: Dict[str, Any], 
        code_context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Create methodology report with inline citations.
        
        Args:
            research_context: Research findings including sources and queries
            code_context: Optional generated code context
        
        Returns:
            Dict with methodology report and metadata
        """
        self._stream_thought("📝 Synthesizing methodology report with citations...")
        
        # Extract components from research context
        sources = research_context.get("sources", [])
        search_queries = research_context.get("search_queries", [])
        research_text = research_context.get("research", "")
        datasets = research_context.get("datasets", [])
        
        # Format sources for citation reference
        if sources:
            source_list = "\n".join([
                f"[{i+1}] {s.get('title', 'Unknown Source')}: {s.get('uri', '')}"
                for i, s in enumerate(sources)
            ])
            self._stream_thought(f"📚 Including {len(sources)} sources for citation")
        else:
            source_list = "No external sources available"
            self._stream_thought("⚠️ No sources available for citation")
        
        # Build comprehensive prompt
        prompt = f"""
Create a comprehensive methodology report for this geospatial analysis.

Research Findings:
{research_text}

Datasets Identified:
{[ds.get('name', ds.get('id', 'Unknown')) for ds in datasets] if datasets else 'None'}

Available Sources for Citation (use [1], [2], etc. for inline citations):
{source_list}

Generated Code Summary:
{code_context.get('description', 'N/A') if code_context else 'Not yet generated'}

Create a structured report with these sections:

## 1. Overview
Brief summary of what this analysis does and its objectives.

## 2. Data Sources
List the satellite datasets being used, with:
- Dataset name and resolution
- Temporal coverage
- Key bands/indicators being analyzed
Cite sources where relevant using [1], [2], etc.

## 3. Methodology
Step-by-step explanation of the analysis approach:
- Data preprocessing steps
- Algorithms and indices used
- Processing workflow
Cite methodological sources using [1], [2], etc.

## 4. Expected Outputs
Description of:
- Visualizations that will be generated
- Map layers and their interpretation
- Analysis results format

## 5. References
Numbered list of all sources cited above:
[1] First source
[2] Second source
etc.

Use clear, professional language with proper inline citations throughout.
"""
        
        try:
            client = genai.Client(api_key=self.api_key)
            
            # Config with Thinking Mode
            config = types.GenerateContentConfig(
                system_instruction=self.system_prompt,
                thinking_config=types.ThinkingConfig(
                    include_thoughts=True,
                    thinking_budget=1024
                )
            )
            
            self._stream_thought("💭 Organizing methodology structure...")
            
            # Use sync streaming wrapped in thread to not block event loop
            import asyncio
            
            def run_streaming():
                """Run sync streaming in a thread."""
                thought_count = 0
                methodology = ""
                
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
                                        methodology += part.text
                    elif chunk.text:
                        methodology += chunk.text
                
                return methodology, thought_count
            
            # Run in thread to avoid blocking event loop
            methodology, thought_count = await asyncio.to_thread(run_streaming)
            
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
            
            # Log preview
            preview = methodology[:300] + "..." if len(methodology) > 300 else methodology
            self._stream_thought(f"✅ Methodology report complete ({len(methodology)} chars)")
            
            # Store in research context
            shared_memory.set_research_context("methodology_report", {
                "report": methodology,
                "sources": sources,
                "search_queries": search_queries,
                "datasets": datasets
            })
            
            return {
                "methodology": methodology,
                "sources": sources,
                "search_queries": search_queries,
                "datasets": datasets,
                "citation_count": len(sources)
            }
            
        except Exception as e:
            error_msg = f"Synthesis error: {str(e)}"
            self._stream_thought(error_msg)
            return {
                "methodology": f"Error generating report: {error_msg}",
                "sources": sources,
                "error": error_msg
            }


# Singleton instance
synthesizer_agent = SynthesizerAgent()
