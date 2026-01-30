# MCGEE - Multiagent Code-generator for Google Earth Engine 🛰️

**Turn plain English into Earth Engine code using AI agents.**

Ask questions like "Show me deforestation in the Amazon" and get ready-to-use satellite analysis scripts.

---

## What It Does

```mermaid
graph LR
    A[You Ask a Question] --> B[4 AI Agents Work Together]
    B --> C[Get Earth Engine Code]
    C --> D[Paste & Run in Code Editor]
    
    style A fill:#3b82f6
    style B fill:#8b5cf6
    style C fill:#10b981
    style D fill:#f59e0b
```

**The agents:**
- � **Planner** - Breaks your question into steps
- 🔬 **Researcher** - Finds the best satellites and methods
- 💻 **Coder** - Writes the Earth Engine script
- 📝 **Synthesizer** - Explains what it did

You can watch them think in real-time!

---

## Quick Start

### 1. Get Your API Key
You need a [Google AI API key](https://aistudio.google.com/app/apikey) (free).

### 2. Setup

```bash
# Copy the example file
cp .env.example .env

# Add your API key to .env
GOOGLE_API_KEY=your-key-here
```

### 3. Install

```bash
# Python packages
pip install -r requirements.txt

# Frontend packages
cd app && npm install
```

### 4. Run

```bash
./start.sh
```

Open http://localhost:3000

---

## How It Works

```mermaid
graph TB
    User[🧑 You Type a Question] --> Chat[💬 Chat Agent]
    
    Chat --> Orch[🎯 Orchestrator]
    
    Orch --> Plan[📋 Planner<br/>Breaks into tasks]
    Orch --> Research[🔬 Researcher<br/>Finds data & methods]
    Orch --> Code[💻 Coder<br/>Writes the script]
    Orch --> Synth[📝 Synthesizer<br/>Explains the approach]
    
    Plan -.->|thoughts| WS[📡 WebSocket]
    Research -.->|thoughts| WS
    Code -.->|thoughts| WS
    Synth -.->|thoughts| WS
    
    WS --> UI[🖥️ Your Browser]
    
    Code --> Result[✅ Earth Engine Script]
    
    style User fill:#3b82f6,color:#fff
    style Result fill:#10b981,color:#fff
    style WS fill:#8b5cf6,color:#fff
```

All agents stream their thoughts live so you can see the reasoning.

---

## Example Questions

Try these:

- "Analyze Amazon deforestation from 2020-2023"
- "Show California wildfire burn scars"
- "Detect floods in Bangladesh using radar"
- "Track urban growth in Tokyo"
- "Calculate NDVI for farms in Iowa"

---

## Tech Stack

| Part | Tech |
|------|------|
| **Agents** | Google Gemini 3 Pro |
| **Backend** | Python + FastAPI |
| **Frontend** | Next.js + TypeScript |
| **Streaming** | WebSocket |
| **Target** | Google Earth Engine |

---

## Project Structure

```
orbital-insight/
├── agents/          # The 4 AI agents
├── api/             # FastAPI backend
├── app/             # Next.js frontend
└── start.sh         # Run everything
```

---

## Watch the Agents Think

Every agent streams its thoughts in real-time:

```mermaid
sequenceDiagram
    participant User
    participant Planner
    participant Researcher
    participant Coder
    participant UI
    
    User->>Planner: "Detect deforestation"
    Planner->>UI: 💭 Breaking into steps...
    Planner->>Researcher: Research task
    Researcher->>UI: 💭 Searching for Landsat data...
    Researcher->>UI: 🔗 Found 3 sources
    Researcher->>Coder: Here's what to use
    Coder->>UI: 💭 Writing script...
    Coder->>UI: 💭 Adding visualization...
    Coder->>User: ✅ Ready to use!
```

---

## License

MIT
