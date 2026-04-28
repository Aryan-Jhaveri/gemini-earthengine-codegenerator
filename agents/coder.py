"""
Coder Agent — generates Earth Engine JavaScript via LiteLLM (Claude by default).

Uses extended thinking and native function-calling for the get_dataset_schema tool.
Override the model with MODEL_CODER env-var (e.g. mulerouter/qwen3-coder).
"""

import json
import re
from typing import Optional

from .memory import shared_memory, AgentType
from .llm import stream_completion
from .tools.stac_tools import get_dataset_schema, LITELLM_GET_DATASET_SCHEMA, STAC_TOOL_DISPATCH


SYSTEM_PROMPT = """You are an expert Google Earth Engine JavaScript programmer.

Your task is to generate complete, copy-paste ready Earth Engine scripts.

CRITICAL REQUIREMENTS:
1. **Visualizations**: You MUST define `visParams` with min, max, and specific color palettes.
2. **Legends**: Add a legend using `ui.Panel` and `ui.Label` to explain the colors.
3. **Date Filtering**: Use specific date ranges.
4. **Best Practices**: Add comments explaining every major step.
5. **Geometry**: If no geometry is provided, create a `point` or `bounds` geometry.
6. **Source Citations**: Cite sources in code comments using [1], [2], etc.
7. **Dataset Verification**: Always call get_dataset_schema before referencing band names.

Output format:
- Return ONLY the JavaScript code
- No markdown fences, just raw code
- Code should be immediately runnable in the Earth Engine Code Editor"""

TOOLS = [LITELLM_GET_DATASET_SCHEMA]


class CoderAgent:
    """Coder Agent — Claude via LiteLLM with EE STAC function-calling."""

    def _stream_thought(self, content: str) -> None:
        shared_memory.add_thought(AgentType.CODER, content)

    def _stream_chunk(self, content: str) -> None:
        shared_memory.add_stream_update(AgentType.CODER, content)

    async def generate_script(
        self,
        task: str,
        research_context: Optional[dict] = None,
        use_thinking: bool = True,
    ) -> dict:
        """Generate an Earth Engine script with native tool-use loop."""
        self._stream_thought(f"Starting code generation: {task}")

        sources_text = ""
        if research_context:
            sources = research_context.get("sources", [])
            if sources:
                lines = [
                    f"[{i+1}] {s.get('title', 'Unknown')}: {s.get('uri', '')}"
                    for i, s in enumerate(sources[:5])
                ]
                sources_text = (
                    "\n\nResearch Sources (cite in code comments as [1], [2] …):\n"
                    + "\n".join(lines)
                )
                self._stream_thought(f"📚 Including {len(lines)} sources for citation")

        research_body = (
            research_context.get("research", "No research provided")
            if research_context
            else "None"
        )

        validation_note = ""
        if research_context and "_validation_errors" in research_context:
            errs = research_context["_validation_errors"]
            validation_note = (
                "\n\n⚠️ Fix these validation errors from your previous attempt:\n"
                + "\n".join(f"- {e}" for e in errs)
            )

        user_msg = (
            f"Task: {task}\n\n"
            f"Research Context:\n{research_body}"
            f"{sources_text}"
            f"{validation_note}\n\n"
            "Use get_dataset_schema to verify band names before writing code.\n"
            "Return ONLY the JavaScript code — no explanations, no markdown fences."
        )

        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_msg},
        ]

        self._stream_thought("💭 Thinking and generating code...")

        full_code = ""
        thought_count = 0
        input_tokens = 0
        output_tokens = 0

        # Agentic tool-use loop — max 6 rounds
        for _round in range(6):
            pending_tcs: dict[str, dict] = {}  # tc_id → {name, args}
            last_tc_id: str = ""
            current_text = ""

            async for event in stream_completion(
                "coder",
                messages,
                tools=TOOLS,
                thinking=use_thinking,
                thinking_budget=2048,
            ):
                kind = event["kind"]

                if kind == "thought":
                    thought_count += 1
                    self._stream_thought(f"💭 [{thought_count}] {event['content']}")

                elif kind == "text":
                    current_text += event["content"]
                    self._stream_chunk(event["content"])

                elif kind == "tool_call":
                    tc_id = event.get("id") or ""
                    name = event.get("name") or ""
                    args_chunk = event.get("content") or ""

                    if tc_id and tc_id not in pending_tcs:
                        pending_tcs[tc_id] = {"name": name, "args": args_chunk}
                        last_tc_id = tc_id
                    elif tc_id in pending_tcs:
                        if name:
                            pending_tcs[tc_id]["name"] = name
                        pending_tcs[tc_id]["args"] += args_chunk
                        last_tc_id = tc_id
                    elif last_tc_id:
                        # Continuation chunk without id — append to last
                        pending_tcs[last_tc_id]["args"] += args_chunk

                elif kind == "usage":
                    input_tokens += event["content"].get("input_tokens", 0)
                    output_tokens += event["content"].get("output_tokens", 0)

            full_code = current_text

            if not pending_tcs:
                break  # Final text round — done

            # Log and execute each tool call
            tool_calls_block = []
            for tc_id, tc in pending_tcs.items():
                name = tc["name"]
                args_raw = tc["args"]
                shared_memory.add_tool_call(
                    AgentType.CODER,
                    name,
                    f"args: {args_raw[:120]}",
                )
                tool_calls_block.append({
                    "id": tc_id,
                    "type": "function",
                    "function": {"name": name, "arguments": args_raw},
                })

            messages.append({"role": "assistant", "content": None, "tool_calls": tool_calls_block})

            tool_results = []
            for tc_id, tc in pending_tcs.items():
                fn = STAC_TOOL_DISPATCH.get(tc["name"])
                if fn is None:
                    result_str = json.dumps({"error": f"Unknown tool: {tc['name']}"})
                else:
                    try:
                        args = json.loads(tc["args"]) if tc["args"].strip() else {}
                        result = fn(**args)
                        result_str = json.dumps(result)
                    except Exception as exc:
                        result_str = json.dumps({"error": str(exc)})

                tool_results.append({
                    "role": "tool",
                    "tool_call_id": tc_id,
                    "content": result_str,
                })

            messages.extend(tool_results)

        if thought_count:
            self._stream_thought(f"✅ Completed {thought_count} thinking steps")
        if input_tokens or output_tokens:
            self._stream_thought(
                f"📊 Token Analysis — Input: {input_tokens}, Output: {output_tokens}"
            )

        code = self._clean_code(full_code)
        self._stream_thought("Code generation complete!")

        shared_memory.add_script(code=code, description=task, datasets=[])

        return {
            "code": code,
            "description": task,
            "datasets_used": [],
            "token_usage": {"input": input_tokens, "output": output_tokens},
        }

    async def refine_script(self, original_code: str, refinement_request: str) -> str:
        """Refine an existing script based on user feedback."""
        self._stream_thought(f"Refining script: {refinement_request}")

        user_msg = (
            f"Original Earth Engine Script:\n```javascript\n{original_code}\n```\n\n"
            f"Refinement Request: {refinement_request}\n\n"
            "Return ONLY the updated JavaScript code."
        )
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_msg},
        ]

        refined = ""
        async for event in stream_completion("coder", messages):
            if event["kind"] == "text":
                refined += event["content"]

        refined_code = self._clean_code(refined)
        shared_memory.add_script(
            code=refined_code,
            description=f"Refined: {refinement_request}",
            datasets=[],
        )
        self._stream_thought("Script refined!")
        return refined_code

    def _clean_code(self, code: str) -> str:
        code = re.sub(r"^```(?:javascript|js)?\n?", "", code, flags=re.MULTILINE)
        code = re.sub(r"\n?```$", "", code, flags=re.MULTILINE)
        return code.strip()


# Singleton
coder_agent = CoderAgent()
