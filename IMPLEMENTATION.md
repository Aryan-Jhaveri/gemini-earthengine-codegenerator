# MCGEE Implementation Status & Improvement Plan

## Current State (v0.1 — MVP)

A working multi-agent system that generates Earth Engine JavaScript code from natural language queries.

### ✅ What Works

| Feature | Status |
|---------|--------|
| 4-Agent Pipeline (Planner → Researcher → Coder → Synthesizer) | ✅ |
| Real-time thought streaming via WebSocket | ✅ |
| Gemini 3 Pro with Thinking Mode | ✅ |
| Google Search grounding (when model chooses to use it) | ✅ |
| EE dataset schema verification (read-only, prompt-injected) | ✅ |
| Source citation in methodology reports | ✅ |
| Thought-log UX with per-agent color coding | ✅ |

---

## ⚠️ Honest Assessment of Gaps

A code review surfaced architectural mismatches that explain why the project feels incomplete.

### 1. The Planner is ceremonial
- `agents/orchestrator.py:90` calls `planner.plan(query)` and returns the `tasks` list to the client at line 122, but **the tasks are never consumed by Researcher, Coder, or Synthesizer**.
- The Planner emits parallel/sequential flags and dependencies, but the orchestrator runs the next three agents strictly sequentially (lines 93 → 106 → 115) regardless of what the plan says.

### 2. "Inter-agent dialogue" is mostly a thought-streaming bus
- `_resolve_pending_questions()` (orchestrator.py:56–75) loops over `researcher.check_pending_questions()`, but the normal pipeline never enqueues questions there.
- `coder.ask_researcher()` (coder.py:79–106) exists but has no caller in the main flow.
- "Shared memory" is a one-way append-only context object, not a dialogue protocol.

### 3. EE tools are prompt context, not real function calls
- `ee_tools.py` defines `browse_datasets`, `get_band_schema`, etc. as plain Python functions.
- The Researcher invokes them imperatively and stringifies the output into the prompt (researcher.py:109–118). Same pattern in Coder (coder.py:137–143).
- Only `google_search` is declared to Gemini as a tool. EE tools are **not** registered for native function-calling, so the model cannot decide to look up a band schema mid-generation.
- There is no validation pass that compiles or dry-runs the generated JS against the EE API.

### 4. Frontend is dev-bound
- `app/src/app/page.tsx:154` hardcodes `ws://localhost:8000/ws`; lines 245 and 305 hardcode `http://localhost:8000/chat`.
- `app/next.config.ts` is empty — no `output: 'export'`, no env-var substitution, no `basePath`.
- `api/main.py:39` allows CORS only for `localhost:3000`.
- Result: it cannot be statically exported to GitHub Pages without changes.

### 5. Dead-ish code
- `langchain` and `langchain-google-genai` are in `requirements.txt` but unused.
- `EE_TOOLS` is exported from `ee_tools.py:275–301` but never imported.
- `agents/__init__.py` exports only a subset of agents.

---

## 🎯 Improvement Plan

Three workstreams, in priority order:

1. **Rehaul agent architecture** — replace the linear chain with an orchestrator-workers + evaluator-optimizer topology.
2. **Embed EE map output** — render the *result* of generated code in-app so users don't copy-paste into the EE Code Editor.
3. **Ship the frontend to GitHub Pages** — separate the Next.js SPA from the FastAPI backend.

---

## Workstream 1: Agent Architecture Rehaul

### The right pattern

Anthropic's *Building Effective Agents* (Dec 2024) names five patterns. The current code is **prompt chaining** — fine when subtasks are fixed, but EE generation isn't: dataset choice, band selection, and reducers vary per query, and bad output is only caught when the user pastes into the Code Editor.

The right combination is **orchestrator-workers** (a manager that decomposes dynamically) wrapped around an **evaluator-optimizer loop** (a critic that runs the generated script and feeds errors back to the coder until it compiles).

References:
- Anthropic, *Building Effective Agents* — https://www.anthropic.com/engineering/building-effective-agents
- LangGraph hierarchical teams — https://langchain-ai.github.io/langgraph/tutorials/multi_agent/hierarchical_agent_teams/
- LangGraph Supervisor — https://github.com/langchain-ai/langgraph-supervisor-py
- CrewAI (role-based crews) — https://docs.crewai.com/en/introduction
- Microsoft Agent Framework (AutoGen successor) — https://learn.microsoft.com/en-us/agent-framework/overview/
- OpenAI Agents SDK (handoffs) — https://openai.github.io/openai-agents-python/handoffs/

### Concrete redesign

```
┌──────────────────────────────────────────────────┐
│                 Supervisor (LLM)                 │
│  routes intent: research | code | refine | chat  │
└──────────────────────────────────────────────────┘
       │            │            │            │
   ┌───▼────┐  ┌────▼────┐  ┌────▼────┐  ┌────▼────┐
   │Research│  │  Coder  │◄─┤Validator│  │Synthesis│
   │ +EE doc│  │+EE tool │  │ ee.parse│  │ +cites  │
   └────────┘  │  calls  │  └─────────┘  └─────────┘
               └─────────┘       │
                    ▲────────────┘ retry loop
```

Implementation steps:
1. **Register EE tools as Gemini function-calling tools** (not prompt context). Use `types.Tool(function_declarations=[...])` so the model can call `get_band_schema(dataset_id)` mid-generation. Reference: https://ai.google.dev/gemini-api/docs/function-calling
2. **Add a Validator agent.** Backend executes the generated script with the EE Python API in a sandboxed try/except: `ee.Algorithms.Describe(eval_js(script))` or, more simply, parse and resolve dataset IDs against `ee.ImageCollection(<id>).first().bandNames().getInfo()`. On failure, the error message is fed back to the Coder for revision (max 3 retries).
3. **Replace the Planner with a Supervisor.** The Supervisor decides *which* worker to invoke next based on shared state, instead of always running all four.
4. **Either adopt LangGraph or stay framework-free.** LangGraph natively models cycles and streams to WebSockets; it's the lowest-friction path. If avoiding new deps, build the loop manually but still model it as a state machine, not a procedure.
5. **Delete the unused machinery**: dead `ask_researcher` path, unused `langchain` imports, ceremonial `_resolve_pending_questions`.

---

## Workstream 2: Embed Earth Engine Output

The user pain point — "copy-paste into Code Editor and iterate" — is solvable. There are four candidate approaches; only one is pragmatic.

| Option | Verdict | Why |
|--------|---------|-----|
| Code Editor "Get Link" deep-link | Partial | Opens script in code.earthengine.google.com but the viewer **must have an EE account**. Good as a "open in EE" button, not as embedded output. Docs: https://developers.google.com/earth-engine/guides/playground |
| Earth Engine Apps (iframe) | ❌ | Apps are "publicly viewable without sign-in" but **publishing is a manual Code Editor action** — there is no API to deploy a generated script as an App. Docs: https://developers.google.com/earth-engine/guides/apps |
| `geemap` Folium output | Partial | Python-only; renders in Jupyter, not a Next.js client |
| **`ee.data.getMapId()` → XYZ tiles** | ✅ **Recommended** | Backend executes the generated script with a service-account, calls `getMapId()`, returns a tile URL the frontend renders on Leaflet/MapLibre. End users never authenticate. Docs: https://developers.google.com/earth-engine/apidocs/ee-data-getmapid and REST: https://developers.google.com/earth-engine/reference/rest/v1/projects.maps.tiles/get |

### Recommended flow

1. User submits query → agents generate JS as today.
2. Backend translates the generated EE JS into the equivalent Python expression (or asks the Coder to emit Python directly via a second prompt) and runs it under a **service-account credential**.
3. Backend calls `ee.Image(...).getMapId({vis_params})`; receives a `tile_fetcher.url_format` (an XYZ template).
4. Backend streams the tile URL + center/zoom to the frontend.
5. Frontend renders the tiles via **MapLibre GL JS** or **Leaflet** as a raster layer.
6. Add a "Open in EE Code Editor" button that uses Code Editor share-link as a fallback for power users.

Auth note: the service account holds the EE quota; rate-limit per IP/session at the FastAPI layer to prevent abuse. EE service-account setup: https://developers.google.com/earth-engine/guides/service_account

References:
- `ee.data.getMapId` — https://developers.google.com/earth-engine/apidocs/ee-data-getmapid
- EE REST tiles endpoint — https://developers.google.com/earth-engine/reference/rest/v1/projects.maps.tiles/get
- `geemap` (reference implementation of the tile pattern) — https://geemap.org
- EE service accounts — https://developers.google.com/earth-engine/guides/service_account
- MapLibre GL JS — https://maplibre.org/maplibre-gl-js/docs/

---

## Workstream 3: Ship Frontend to GitHub Pages

Next.js 16 supports static export, but it's a real surgery — not a config flip.

### Steps

1. **`app/next.config.ts`**: set `output: 'export'`, `images: { unoptimized: true }`, `basePath: '/<repo-name>'` (since github.io is project-scoped), `trailingSlash: true`.
2. **Externalize backend URLs.** Replace every hardcoded `localhost:8000` with `process.env.NEXT_PUBLIC_API_URL` and `NEXT_PUBLIC_WS_URL`. These bake in at build time.
3. **Audit for static-export blockers**: no API routes, no Route Handlers, no Server Actions, no middleware, no ISR. The current app is client-only React, so this is mostly a sanity check.
4. **GitHub Actions workflow** to `next build && next export` and publish `out/` to `gh-pages`. Add a `.nojekyll` file.
5. **Pin Next.js minor version**. There is an open Next.js 16 issue where RSC manifest 404s on GitHub Pages: https://github.com/vercel/next.js/issues/85374 — confirm a working version before locking in.
6. **CORS on backend**: add the `https://<user>.github.io` origin to `api/main.py:39`.

Static export docs: https://nextjs.org/docs/pages/guides/static-exports

### Where to host the FastAPI backend

GitHub Pages is static-only, so the backend goes elsewhere. Both options below support FastAPI + WebSockets (the `/ws` endpoint is non-negotiable for the thought-log).

| Host | Pros | Cons |
|------|------|------|
| **Fly.io** ✅ | First-class WebSockets, scale-to-zero, global edge, full ASGI support | Requires Dockerfile + `fly.toml`, billing card required |
| **Render** | Git-push deploy, free tier, no Dockerfile required | Free tier sleeps after 15 min idle, fewer regions |

**Avoid HuggingFace Spaces** for this app — there are open reports of WebSocket 404s on Spaces' proxy: https://discuss.huggingface.co/t/fastapi-websocket-returns-http-404-on-spaces/159865

References:
- Fly.io docs — https://fly.io/docs/
- Fly.io WebSockets — https://fly.io/docs/networking/services/
- Render FastAPI guide — https://render.com/docs/deploy-fastapi
- Render WebSockets — https://render.com/docs/web-services#websockets

---

## ✅ Bug Fix: Concurrent Request Serialization

**Root cause**: `shared_memory` is a process-wide singleton. When two `/analyze`
requests arrive before the first completes, both pipelines run concurrently in FastAPI's
event loop. The Researcher yields at `await asyncio.to_thread(run_streaming)`, at which
point the second pipeline's Coder advances — making it appear the Coder ran before the
Researcher finished. Both pipelines' thought events land in the same WebSocket stream
and interleave in the UI.

**Fix**: serialize `/analyze` with an `asyncio.Lock` in `api/main.py`. Return HTTP 429
immediately if another analysis is in progress. See `docs/concurrency-fix.md`.

**Future path**: scope `SharedMemory` per-request (pass `request_id` through all six
agent classes + orchestrator) to allow true parallel analyses.

---

## 📋 Recommended Execution Order

1. **Static export + env-var URLs** (1 day). Lowest risk, immediately useful — frontend can ship to github.io against the existing local backend.
2. **Deploy backend to Fly.io** (1 day). Containerize, add CORS for the github.io origin, verify WebSocket upgrade.
3. **EE tile embedding** (2–3 days). Service account + `getMapId()` + MapLibre layer. This is the user-facing win.
4. **Validator agent + retry loop** (2 days). The single biggest reliability improvement to the agent system — catches band-name and method errors before the user sees them.
5. **Convert EE tools to Gemini function-calling** (1–2 days). Makes the Researcher/Coder genuinely tool-using.
6. **Replace Planner with Supervisor (LangGraph or hand-rolled)** (3–4 days). Largest refactor; do last.

---

## 📚 Full Reference List

### Agent architecture
- Anthropic, *Building Effective Agents* — https://www.anthropic.com/engineering/building-effective-agents
- LangGraph hierarchical agent teams — https://langchain-ai.github.io/langgraph/tutorials/multi_agent/hierarchical_agent_teams/
- LangGraph Supervisor — https://github.com/langchain-ai/langgraph-supervisor-py
- CrewAI — https://docs.crewai.com/en/introduction
- Microsoft Agent Framework — https://learn.microsoft.com/en-us/agent-framework/overview/
- AutoGen → Agent Framework migration — https://learn.microsoft.com/en-us/agent-framework/migration-guide/from-autogen/
- OpenAI Agents SDK handoffs — https://openai.github.io/openai-agents-python/handoffs/
- Gemini function calling — https://ai.google.dev/gemini-api/docs/function-calling
- Gemini grounding — https://ai.google.dev/gemini-api/docs/grounding
- Gemini URL context — https://ai.google.dev/gemini-api/docs/url-context

### Earth Engine
- EE API docs — https://developers.google.com/earth-engine/apidocs
- EE guides — https://developers.google.com/earth-engine/guides
- Dataset catalog — https://developers.google.com/earth-engine/datasets
- `ee.data.getMapId` — https://developers.google.com/earth-engine/apidocs/ee-data-getmapid
- EE REST tiles — https://developers.google.com/earth-engine/reference/rest/v1/projects.maps.tiles/get
- EE Apps — https://developers.google.com/earth-engine/guides/apps
- EE Code Editor (playground) — https://developers.google.com/earth-engine/guides/playground
- EE service accounts — https://developers.google.com/earth-engine/guides/service_account
- EE web apps tutorial — https://developers.google.com/earth-engine/tutorials/community/creating-web-apps
- `geemap` — https://geemap.org

### Deployment
- Next.js static exports — https://nextjs.org/docs/pages/guides/static-exports
- Next.js 16 RSC 404 on Pages (track) — https://github.com/vercel/next.js/issues/85374
- Fly.io docs — https://fly.io/docs/
- Fly.io WebSockets — https://fly.io/docs/networking/services/
- Render FastAPI — https://render.com/docs/deploy-fastapi
- Render WebSockets — https://render.com/docs/web-services#websockets
- MapLibre GL JS — https://maplibre.org/maplibre-gl-js/docs/
