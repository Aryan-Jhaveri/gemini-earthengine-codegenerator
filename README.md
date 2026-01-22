# Orbital Insight - Multi-Agent Geointelligence

A multi-agent system for geospatial analysis using Google Earth Engine, powered by Gemini AI.

## Features

- 🔬 **Researcher Agent**: Deep Research + Google Search grounding for methodology discovery
- 💻 **Coder Agent**: Gemini Thinking Mode for step-by-step script generation
- 💬 **Chat Agent**: Natural language interface with full context access
- 🧠 **Real-time Thinking Logs**: Watch agents reason in real-time via WebSocket
- 🌍 **Earth Engine Integration**: Query datasets, verify schemas, generate copy-paste scripts

## Quick Start

### 1. Install Dependencies

```bash
# Backend (Python)
pip install -r requirements.txt

# Frontend (Next.js)
cd app
npm install
```

### 2. Set Environment Variables

Create a `.env` file:
```
GOOGLE_API_KEY=your-gemini-api-key
GOOGLE_CLOUD_PROJECT=your-gcp-project
```

### 3. Run

```bash
# Start both services
chmod +x start.sh
./start.sh

# Or run separately:
# Backend
python -m uvicorn api.main:app --reload --port 8000

# Frontend
cd app && npm run dev
```

### 4. Open

- **Frontend**: http://localhost:3000
- **API Docs**: http://localhost:8000/docs

## Architecture

```
User → Chat Agent → [Researcher Agent ↔ Coder Agent] → Generated Script
                  ↓
           Shared Memory (all thoughts streamed via WebSocket)
```

## Example Queries

- "Analyze deforestation in Amazon for 2024"
- "Show NDVI changes for California wildfires"
- "Detect floods using Sentinel-1 SAR data"
- "Create a land cover classification for Kenya"
