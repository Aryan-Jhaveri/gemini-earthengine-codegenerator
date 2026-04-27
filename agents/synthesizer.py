"""
Synthesizer Agent - Methodology Report with Citations

Compiles research findings into a structured methodology report with inline citations.
References sources as [1], [2], etc. for proper academic-style citation.
Now uses the unified llm.stream_completion() abstraction (anthropic/claude-haiku-4-5).
"""

from typing import Optional, Dict, Any

from .memory import shared_memory, AgentType
from .llm import stream_completion


SYSTEM_PROMPT = """You are a research synthesizer for geospatial analysis.

Create clear, well-structured methodology reports with proper citations.
Use [1], [2] etc. for inline citations referencing the provided sources.

Report Structure:
1. **Overview** - What the analysis accomplishes
2. **Data Sources** - Satellite datasets used (cite sources)
3. **Methodology** - Step-by-step processing approach (cite sources)
4. **Expected Outputs** - What the user will see
5. **References** - Numbered list of all sources cited

Use academic writing style with clear sections and proper citations."""


class SynthesizerAgent:
    """
    Synthesizer Agent for methodology report generation.

    Uses anthropic/claude-haiku-4-5 via llm.stream_completion().
    """

    def _stream_thought(self, content: str) -> None:
        shared_memory.add_thought(AgentType.SYNTHESIZER, content)

    async def synthesize(
        self,
        research_context: Dict[str, Any],
        code_context: Optional[Dict[str, Any]] = None,
        sources: list = None,
    ) -> Dict[str, Any]:
        """
        Create methodology report with inline citations.

        Args:
            research_context: Research findings including sources and queries
            code_context:     Optional generated code context
            sources:          Explicitly passed validated sources from orchestrator

        Returns:
            Dict with methodology report and metadata
        """
        self._stream_thought("📝 Synthesizing methodology report with citations...")

        validated_sources = sources if sources else research_context.get("sources", [])
        search_queries = research_context.get("search_queries", [])
        research_text = research_context.get("research", "")
        datasets = research_context.get("datasets", [])

        if validated_sources:
            source_list = "\n".join([
                f"[{i+1}] {s.get('title', 'Unknown Source')}: {s.get('uri', '')}"
                for i, s in enumerate(validated_sources)
            ])
            self._stream_thought(f"📚 Including {len(validated_sources)} validated sources for citation")
        else:
            source_list = (
                "⚠️ NO EXTERNAL SOURCES AVAILABLE — "
                "Do not include a References section or create fake citations"
            )
            self._stream_thought("⚠️ No validated sources available — citations will be omitted")

        prompt = f"""Create a comprehensive methodology report for this geospatial analysis.

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

Use clear, professional language with proper inline citations throughout."""

        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ]

        methodology = ""
        thought_count = 0
        input_tokens = 0
        output_tokens = 0

        self._stream_thought("💭 Organizing methodology structure...")

        try:
            async for event in stream_completion(
                "synthesizer",
                messages,
                thinking=True,
                thinking_budget=1024,
            ):
                kind = event["kind"]
                if kind == "thought":
                    thought_count += 1
                    self._stream_thought(f"💭 [{thought_count}] {event['content']}")
                elif kind == "text":
                    methodology += event["content"]
                elif kind == "usage":
                    input_tokens = event["content"].get("input_tokens", 0)
                    output_tokens = event["content"].get("output_tokens", 0)

            if thought_count > 0:
                self._stream_thought(f"✅ Completed {thought_count} thinking steps")

            if input_tokens or output_tokens:
                self._stream_thought(
                    f"📊 Token Analysis — Input: {input_tokens} / Output: {output_tokens}"
                )

            self._stream_thought(
                f"✅ Methodology report complete ({len(methodology)} chars)"
            )

            shared_memory.set_research_context("methodology_report", {
                "report": methodology,
                "sources": validated_sources,
                "search_queries": search_queries,
                "datasets": datasets,
            })

            return {
                "methodology": methodology,
                "sources": validated_sources,
                "search_queries": search_queries,
                "datasets": datasets,
                "citation_count": len(validated_sources),
            }

        except Exception as e:
            error_msg = f"Synthesis error: {e}"
            self._stream_thought(error_msg)
            return {
                "methodology": f"Error generating report: {error_msg}",
                "sources": validated_sources,
                "error": error_msg,
            }


# Singleton instance
synthesizer_agent = SynthesizerAgent()
