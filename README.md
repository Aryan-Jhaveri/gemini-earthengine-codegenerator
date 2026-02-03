# MCGEE - Multiagent Code-generator for Google Earth Engine 🛰️

A multi-agent LLM app that generates Google Earth Engine code. Give it a research objective, location, and time range — get working code.

Built with Gemini 3 Pro for the Gemini 3 Hackathon.

---

## Demo

**▶️ [Watch Demo on YouTube](https://www.youtube.com/watch?v=_hWtLnabNxg)**

---

## How to Run

### Prerequisites

- Python 3.10+
- Node.js 18+
- [Google AI API key](https://aistudio.google.com/app/apikey) (free)

### 1. Clone & Setup

```bash
git clone https://github.com/Aryan-Jhaveri/gemini-earthengine-codegenerator.git
cd gemini-earthengine-codegenerator

# Create environment file
cp .env.example .env
```

Edit `.env` and add your API key:
```
GOOGLE_API_KEY=your-api-key-here
```

### 2. Install Dependencies

```bash
# Backend
pip install -r requirements.txt

# Frontend
cd app && npm install && cd ..
```

### 3. Run

```bash
./start.sh
```

Open **http://localhost:3000**

---

## Docker (Alternative)

If you have Docker installed:

```bash
docker compose up --build
```

---

## Troubleshooting

| Issue | Fix |
|-------|-----|
| Port already in use | `lsof -ti:8000 | xargs kill -9` |
| Module not found | Make sure you ran `pip install -r requirements.txt` |
| API key error | Check your `.env` file |

---

## Example Prompts

- "Analyze Amazon deforestation from 2020-2023"
- "Detect floods in Bangladesh using radar"
- "Calculate NDVI for farms in Iowa"

---

## Project Structure

```
mcgee/
├── agents/          # AI agents (Planner, Researcher, Coder, Synthesizer)
├── api/             # FastAPI backend
├── app/             # Next.js frontend
└── start.sh         # Run script
```

---

## License

MIT
