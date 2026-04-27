# MCGEE — Multiagent Code-generator for Google Earth Engine 🛰️

A multi-agent LLM system that generates Google Earth Engine JavaScript from a plain-English research objective. Give it a location, time range, and mission — get working, validated code.

---

## Demo

**[Watch Demo on YouTube](https://www.youtube.com/watch?v=_hWtLnabNxg)**

---

## Architecture

Six specialised agents collaborate in a pipeline:

```
Supervisor → Planner → Researcher → Coder ↔ Validator (retry ×3) → Synthesizer
```

| Agent | Model | Role |
|-------|-------|------|
| **Supervisor** | Gemini 2.5 Flash | Routes intent (full pipeline / chat) |
| **Planner** | Gemini 2.5 Flash | Decomposes the mission into tasks |
| **Researcher** | Gemini 2.5 Pro + Google Search | Finds methodology & datasets |
| **Coder** | Claude Sonnet 4.5 (default) | Generates EE JavaScript |
| **Validator** | Gemini 2.5 Flash + STAC index | Checks band names & dataset IDs |
| **Synthesizer** | Claude Haiku 4.5 | Writes a methodology report with citations |

All agent thoughts stream to the frontend in real time via WebSocket.

---

## How to Run

### Prerequisites

- Python 3.10+
- Node.js 18+
- [Google AI API key](https://aistudio.google.com/app/apikey) (Gemini)
- [Anthropic API key](https://console.anthropic.com/) (Claude)

### 1. Clone & Setup

```bash
git clone <repo-url>
cd orbital-insight

cp .env.example .env
# Edit .env — add GOOGLE_API_KEY and ANTHROPIC_API_KEY at minimum
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
cd app && npm install && cd ..
```

### 3. Run

```bash
./start.sh
# Frontend: http://localhost:3000
# Backend:  http://localhost:8000
```

---

## Docker

```bash
docker compose up --build
```

---

## Model Overrides

Any agent's model can be swapped via environment variable — no code changes needed:

```bash
# Use MuleRouter Qwen for the Coder instead of Claude
MODEL_CODER=mulerouter/qwen3-coder ./start.sh

# All available overrides (see .env.example for the full list):
MODEL_SUPERVISOR=gemini/gemini-2.5-flash
MODEL_RESEARCHER=gemini/gemini-2.5-pro
MODEL_CODER=anthropic/claude-sonnet-4-5
MODEL_VALIDATOR=gemini/gemini-2.5-flash
MODEL_SYNTHESIZER=anthropic/claude-haiku-4-5
MODEL_CHAT=gemini/gemini-2.5-flash
```

---

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/chat` | Process a chat message |
| `POST` | `/analyze` | Run the full analysis pipeline |
| `GET` | `/context` | Current shared memory snapshot |
| `GET` | `/latest-script` | Most recent generated EE script |
| `GET` | `/metrics` | Per-agent token usage and cost breakdown |
| `DELETE` | `/clear` | Reset shared memory |
| `WS` | `/ws` | Real-time thought stream |

---

## Example Prompts

- "Analyze Amazon deforestation from 2020-2023"
- "Detect floods in Bangladesh using Sentinel-1 radar"
- "Calculate NDVI for farmland in Iowa, July 2023"
- "Map urban heat island effect in Phoenix, summer 2022"

---

## Developer Tools

```bash
make stac-index          # Rebuild the EE dataset index (1089 datasets)
make stac-index-dry      # Preview 5 datasets without writing
make test-mulerouter     # Smoke-test MuleRouter Qwen integration
```

---

## Project Structure

```
mcgee/
├── agents/              # All AI agents + LiteLLM abstraction
│   ├── llm.py           # Unified stream_completion() — wraps LiteLLM
│   ├── models.py        # Role → model string registry
│   ├── supervisor.py    # Intent routing
│   ├── researcher.py    # Google Search grounding (native Gemini SDK)
│   ├── coder.py         # EE code generation
│   ├── validator.py     # STAC-backed code validation
│   ├── synthesizer.py   # Methodology report
│   ├── data/            # ee_stac_index.json + usage.db
│   └── tools/           # stac_tools.py + ee_tools.py
├── scripts/             # build_stac_index.py, test_mulerouter.py
├── api/                 # FastAPI backend
├── app/                 # Next.js frontend
├── Makefile
└── start.sh
```

---

## Troubleshooting

| Issue | Fix |
|-------|-----|
| Port in use | `lsof -ti:8000 \| xargs kill -9` |
| Module not found | `pip install -r requirements.txt` |
| API key error | Check your `.env` file |
| Coder produces wrong band names | Run `make stac-index` to refresh the dataset index |

---

## License

MIT
