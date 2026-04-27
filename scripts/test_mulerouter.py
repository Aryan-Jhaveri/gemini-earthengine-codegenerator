"""
Smoke test for MuleRouter Qwen integration.

Sends a single "hello" message and prints the response.
Requires MULEROUTER_API_KEY and MULEROUTER_BASE_URL in the environment.

Usage:
    python scripts/test_mulerouter.py
    MODEL_CODER=mulerouter/qwen3-coder python scripts/test_mulerouter.py
"""

import asyncio
import os
import sys

# Ensure the project root is on the path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()


async def main():
    api_key = os.environ.get("MULEROUTER_API_KEY")
    base_url = os.environ.get("MULEROUTER_BASE_URL", "https://api.mulerouter.ai")

    if not api_key:
        print("❌ MULEROUTER_API_KEY not set. Add it to .env and try again.")
        sys.exit(1)

    # Temporarily set MODEL_CODER so get_model("coder") returns a mulerouter model
    os.environ.setdefault("MODEL_CODER", "mulerouter/qwen3-coder")

    from agents.llm import stream_completion

    print(f"Sending test message to MuleRouter ({base_url})…")
    messages = [{"role": "user", "content": "Say hello in one short sentence."}]

    response_text = ""
    try:
        async for event in stream_completion("coder", messages):
            if event["kind"] == "text":
                response_text += event["content"]
                print(event["content"], end="", flush=True)
            elif event["kind"] == "usage":
                print(f"\n📊 Tokens — input: {event['content']['input_tokens']}, output: {event['content']['output_tokens']}")
    except Exception as exc:
        print(f"\n❌ MuleRouter request failed: {exc}")
        sys.exit(1)

    print()
    if response_text:
        print("✅ MuleRouter smoke test passed")
    else:
        print("⚠️  Empty response — check MuleRouter endpoint and model name")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
