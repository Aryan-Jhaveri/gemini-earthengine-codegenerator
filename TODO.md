# TODO

> Execution order matters — each phase builds on the previous. Do not skip ahead.
> Reference docs: `docs/multi-model-agent-rehaul.md`, `docs/coder-api-context.md`, `IMPLEMENTATION.md`

---

## Phase 1 — LiteLLM Abstraction Layer

Goal: one unified call interface that every agent imports. Enables all future model swaps to be config changes, not code changes.

### 1.1 Dependencies
- [x] Add `litellm` to `requirements.txt`
- [x] Add `httpx` to `requirements.txt` (MuleRouter raw client fallback)
- [x] Add `ANTHROPIC_API_KEY` to `.env.example` ✅ done
- [x] Add `MULEROUTER_API_KEY` + `MULEROUTER_BASE_URL` to `.env.example` ✅ done
- [x] Add model override env vars to `.env.example` ✅ done
- [ ] Verify `GOOGLE_API_KEY` still works through LiteLLM's Gemini provider

### 1.2 MuleRouter Integration
MuleRouter is the Qwen entry point (you have credits there). It needs a small custom provider shim because LiteLLM doesn't have a native MuleRouter provider — but if MuleRouter exposes an OpenAI-compatible `/chat/completions` endpoint we can use LiteLLM's `openai` provider pointed at the MuleRouter base URL.

- [ ] **Probe the MuleRouter chat endpoint** — check the MuleRouter console/docs for the text generation (chat completions) endpoint path and request format. The image-gen path is `/vendors/google/v1/nano-banana-pro/generation`; the Qwen chat path is likely `/vendors/qwen/v1/<model>/chat/completions` or similar
- [ ] If OpenAI-compatible: configure LiteLLM with `api_base=MULEROUTER_BASE_URL` and `api_key=MULEROUTER_API_KEY`
  ```python
  # In agents/llm.py, for mulerouter/* models:
  acompletion(
      model="openai/qwen3-coder",
      api_base="https://api.mulerouter.ai/vendors/qwen/v1",
      api_key=os.environ["MULEROUTER_API_KEY"],
      messages=[...],
  )
  ```
- [ ] If NOT OpenAI-compatible: write a thin `_mulerouter_complete(model, messages, **kwargs)` function in `agents/llm.py` that calls MuleRouter's API directly with `httpx` and maps the response to the same normalised event shape
- [x] Add `mulerouter/` prefix handling in `agents/models.py` so the dispatch logic in `stream_completion()` routes to the right code path
- [x] Write a smoke test: `python scripts/test_mulerouter.py` — sends a one-shot "hello" to MuleRouter Qwen, prints the response

### 1.3 `agents/models.py`
- [x] Create `agents/models.py` with `MODELS` dict mapping role → LiteLLM model string
- [x] Support env-var override per role — if `MODEL_CODER=mulerouter/qwen3-coder` is set, the Coder runs on MuleRouter Qwen with no other changes
- [x] Document which roles Qwen is suitable for: Coder (primary use of MuleRouter credits), Supervisor, Validator — NOT Researcher (Gemini-only, needs grounding)

### 1.4 `agents/llm.py`
- [x] Create `agents/llm.py` with `stream_completion(role, messages, *, tools, thinking, extra)` async generator
- [x] Implement `_normalise(chunk)` that maps provider-specific chunk shapes to uniform `{kind, content}` events
- [x] Handle Gemini-specific passthrough via `extra_body`: `thinking_config`, `tools` (google_search, url_context)
- [x] Handle Anthropic-specific passthrough via `extra_body`: `thinking` (extended thinking)
- [x] Add `raw_client(role)` escape hatch that returns the underlying SDK client for features LiteLLM hasn't caught up to
- [ ] Write a short smoke test (`python -c "import asyncio; from agents.llm import stream_completion; ..."`) confirming both Gemini and Anthropic emit normalised events

### 1.5 Port Synthesizer (proof of concept)
- [x] Refactor `agents/synthesizer.py` to call `llm.stream_completion("synthesizer", ...)` instead of direct `genai` calls
- [x] Confirm thought events still flow to WebSocket unchanged
- [x] Confirm token counts still appear in thought log
- [x] Delete the direct `genai.Client` instantiation from `synthesizer.py`

### 1.6 Port Chat Agent
- [x] Refactor `agents/chat_agent.py` to use `llm.stream_completion("chat", ...)`
- [x] Verify routing logic (research vs. code vs. conversational) still works

### 1.7 Validation
- [ ] All four existing agents still run end-to-end
- [ ] Thought log shows correct per-agent colors and events
- [ ] Synthesizer and Chat now show `claude-haiku` / `gemini-flash` in logs (or confirm via model field in usage events)

---

## Phase 2 — STAC Index + Coder Function Tools

Goal: give the Coder deterministic, ground-truth knowledge of EE dataset band names, scales, and date ranges. Eliminates the band-hallucination class of bugs.

### 2.1 STAC Index Builder
- [x] Create `scripts/build_stac_index.py`
- [x] Walk from STAC root: `https://storage.googleapis.com/earthengine-stac/catalog/catalog.json`
- [x] For each dataset entry, extract and store: `id`, `gee:type`, `eo:bands`, `gee:schema`, `extent.temporal`, `extent.spatial`, `providers`
- [x] Output: `agents/data/ee_stac_index.json` (keyed by dataset ID for O(1) lookup)
- [x] Add `agents/data/` to `.gitignore` (generated artifact, not source)
- [x] Add a `--dry-run` flag that fetches 5 datasets and prints output without writing
- [x] Run the script and commit the generated index (1089 datasets)

### 2.2 `get_dataset_schema` Tool
- [x] Create `agents/tools/stac_tools.py`
- [x] Implement `get_dataset_schema(dataset_id: str) -> dict` that loads from the index
- [x] Write the Gemini function declaration (`GET_DATASET_SCHEMA_DECL`) and Anthropic tool schema for it
- [x] Handle dataset ID variants (with and without `/`, upper/lower case normalization)
- [x] Return structured result: `{bands, scale_factors, date_range, spatial_extent, schema_properties}`

### 2.3 Port Coder to LiteLLM + Claude
- [ ] Refactor `agents/coder.py` to call `llm.stream_completion("coder", ...)`
- [ ] Replace the string-injection block at `coder.py:137-143` with native function tool declarations
- [ ] Register `GET_DATASET_SCHEMA_DECL` in the Coder's tool list
- [ ] Implement the function-call dispatch loop: when the model emits a `tool_call` event, execute the local function and feed the result back as a `tool_result` message
- [ ] Enable URL Context (`types.UrlContext()`) via `extra_body` passthrough for ad-hoc apidocs reads
- [ ] Confirm `tool_call` events stream to the thought log as `🔧` entries (already wired in frontend)

### 2.4 Validation
- [ ] Submit a query using Sentinel-2: verify the Coder calls `get_dataset_schema("COPERNICUS/S2_SR_HARMONIZED")` and uses `B4`, `B8`, scale `0.0001` — not hallucinated values
- [ ] Submit a query using Landsat-8: verify `QA_PIXEL` not `BQA`
- [ ] Tool call appears in thought log with dataset ID visible

---

## Phase 3 — Supervisor + Validator + Retry Loop

Goal: replace the ceremonial Planner with a routing Supervisor; add a Validator that catches code errors before the user sees them.

### 3.1 Dead Code Cleanup ✅
- [x] Remove `langchain` and `langchain-google-genai` from `requirements.txt`
- [x] Remove `ask_researcher` method from `coder.py` (no caller in main flow)
- [x] Remove `_resolve_pending_questions` from `orchestrator.py` (never populated in normal flow)
- [x] Remove `EE_TOOLS` export from `ee_tools.py` (never imported)
- [x] Update `agents/__init__.py` to export all active agents
- [ ] Confirm `./start.sh` still works after cleanup

### 3.2 Validator Agent ✅
- [x] Create `agents/validator.py`
- [x] Accept generated EE JS as input
- [x] Validation strategy: deterministic STAC index lookup first, then LLM review
- [x] Return `{valid: bool, errors: [str], suggestions: [str]}`
- [x] Stream validation status to thought log: `✅ Code validated` or `❌ Error: <msg>`

### 3.3 Retry Loop in Orchestrator ✅
- [x] In `orchestrator.py`, after the Coder produces code, pass it to the Validator
- [x] On failure: feed the error message back to the Coder as an additional user message and re-run
- [x] Cap at **3 retry attempts**
- [x] On exhausted retries: include the last error in the final response
- [x] Stream retry attempts to thought log: `🔄 Retry 1/3 — fixing: <error summary>`

### 3.4 Supervisor Agent ✅
- [x] Create `agents/supervisor.py` using `llm.stream_completion("supervisor", ...)`
- [x] Routes intent to one of: `research_only`, `code_only`, `full_pipeline`, `chat`
- [x] Supervisor decision streams to thought log: `📋 Routing → full_pipeline`
- [x] Update `orchestrator.py` to use Supervisor for routing
- [x] For `chat` intent: respond directly without invoking Researcher/Coder/Synthesizer
- [ ] Replace `planner.py` — delete `agents/planner.py` after Supervisor fully replaces it

### 3.5 Validation
- [ ] Inject a deliberate band name error into a query; confirm Validator catches it and Coder fixes it within 3 retries
- [ ] A conversational message ("what is NDVI?") routes to `chat` and does not trigger the full pipeline
- [ ] Thought log shows Supervisor decision, Validator result, and retry attempts

---

## Phase 4 — Embed EE Map Output

Goal: render the result of generated code as a live map tile layer in the frontend. Eliminates the copy-paste-into-Code-Editor workflow.

### 4.1 Service Account Setup
- [ ] Create a GCP service account with Earth Engine read access
- [ ] Download service account JSON key
- [ ] Add `EE_SERVICE_ACCOUNT_KEY` (path to JSON) to `.env.example`
- [ ] Add `EE_SERVICE_ACCOUNT_EMAIL` to `.env.example`
- [ ] Add EE Python library (`earthengine-api`) to `requirements.txt` if not already present
- [ ] Initialize EE in `api/main.py` using the service account on startup

### 4.2 Code Execution Backend
- [ ] Create `agents/ee_executor.py`
- [ ] Accept generated EE JS string as input
- [ ] Translate EE JS to equivalent EE Python (options: second Coder prompt, or ask Coder to emit Python via an additional instruction in Phase 2)
- [ ] Execute the Python expression in a sandboxed `try/except`
- [ ] Call `ee.data.getMapId(image, vis_params)` to get tile URL
- [ ] Return `{tile_url, center: [lat, lng], zoom, error?}`
- [ ] Rate-limit by IP at the FastAPI layer (e.g. 10 requests/minute)

### 4.3 API Endpoint
- [ ] Add `POST /execute` endpoint to `api/main.py`
- [ ] Accepts `{code: str}`, returns `{tile_url: str, center: [lat, lng], zoom: int}`
- [ ] Stream execution status to WebSocket: `🗺️ Executing code...`, `✅ Map ready`
- [ ] Handle errors gracefully: return `{error: str}` with 200 status (not 500)

### 4.4 Frontend Map Component
- [ ] Add `maplibre-gl` to `app/package.json`
- [ ] Create `app/src/app/components/MapViewer.tsx`
- [ ] Show map panel below or alongside the code output panel
- [ ] When tile URL is received, add as a raster layer with appropriate opacity
- [ ] Show loading state while execution is in progress
- [ ] Add "Open in EE Code Editor" button
- [ ] Handle the case where execution fails: show error inline, keep code visible

### 4.5 Visualization Params
- [ ] Ask the Coder (or Synthesizer) to emit suggested `vis_params` alongside the EE code
- [ ] Pass `vis_params` to `getMapId()` call
- [ ] Fall back to a sensible default (grayscale stretched to min/max) if none provided

### 4.6 Validation
- [ ] Submit "NDVI for Amazon 2023" → map tiles appear in the frontend
- [ ] Submit a query that errors → error message shown inline, no crash
- [ ] "Open in EE Code Editor" button opens correct URL in new tab

---

## Phase 5 — API Index + Example RAG

Goal: give the Coder knowledge of EE method signatures (Layer B) and idiomatic usage patterns (Layer C). Reduces deprecated-API and non-idiomatic-code errors.

### 5.1 API Index Builder
- [ ] Create `scripts/build_api_index.py`
- [ ] Scrape `https://developers.google.com/earth-engine/apidocs`
- [ ] For each method page, extract: class, method name, full signature, return type, parameter descriptions, "Examples" section
- [ ] Output: `agents/data/ee_api_index.json` keyed by `ClassName.methodName`
- [ ] Add incremental refresh mode (only re-scrape pages modified since last run)
- [ ] Handle rate limiting with polite delays

### 5.2 `lookup_ee_method` Tool
- [ ] Add `lookup_ee_method(name: str) -> dict` to `agents/tools/stac_tools.py` (or new file)
- [ ] Returns `{signature, return_type, parameters, example, url}`
- [ ] Write function declaration for Gemini and Anthropic tool schema
- [ ] Register in Coder's tool list alongside `get_dataset_schema`
- [ ] Fall back to URL Context (`types.UrlContext(urls=[apidocs_url])`) for methods not in the index

### 5.3 Example Corpus Ingest
- [ ] Create `scripts/build_example_index.py`
- [ ] Clone or fetch (without git) `google/earthengine-api` JS examples folder
- [ ] Clone or fetch `giswqs/earthengine-js-examples`
- [ ] Chunk by file (each example is self-contained)
- [ ] Embed with `text-embedding-004` via LiteLLM's `aembedding()` (keeps embedding model swappable)
- [ ] Store in SQLite + `sqlite-vec` at `agents/data/ee_examples.db`
- [ ] Output a metadata sidecar: `{title, source_url, file_path, category}` per example

### 5.4 `find_example_snippet` Tool
- [ ] Implement `find_example_snippet(query: str, k: int = 3) -> list[dict]`
- [ ] Returns `[{title, code, source_url, category}]`
- [ ] Write function declaration and register in Coder's tool list
- [ ] Test: query "cloud masking Sentinel-2" retrieves a relevant CloudMasking example

### 5.5 Validation
- [ ] Submit "compute NDVI with cloud masking on Sentinel-2": Coder calls `find_example_snippet`, result appears in thought log
- [ ] Submit a query referencing `reduceRegion`: Coder calls `lookup_ee_method("ImageCollection.reduceRegion")`, signature used correctly in output
- [ ] No hallucinated method signatures or non-existent parameters in generated code

---

## Ongoing / Cross-Cutting

- [x] **Token cost logging**: log per-role token usage to a small SQLite table (`agents/data/usage.db`); expose `GET /metrics` endpoint returning cost breakdown by agent
- [ ] **Error budget**: set hard per-API-key budget caps in `.env` (e.g. `MAX_MONTHLY_USD_ANTHROPIC=20`)
- [x] **STAC index refresh**: add a cron script or `Makefile` target to re-run `build_stac_index.py` weekly
- [ ] **Model A/B testing**: once usage logging is in, compare Coder output quality between `claude-sonnet-4-5` and `qwen3-coder` on a small query set
- [x] **Update CLAUDE.md**: reflect new agent topology, model assignments, and tool architecture after Phase 3

---

## Won't Do (Explicit Exclusions)

- GitHub Pages static export
- Fly.io / Render deployment
- GitHub Actions CI/CD
