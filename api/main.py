"""
FastAPI Backend with WebSocket Streaming

Provides:
- REST endpoints for chat
- WebSocket for real-time thought streaming
- Agent orchestration
"""

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
import asyncio
import os
import sys

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

from agents.orchestrator import orchestrator
from agents.memory import shared_memory
from agents.chat_agent import chat_agent


app = FastAPI(
    title="Orbital Insight API",
    description="Multi-Agent Geointelligence API",
    version="1.0.0"
)

# CORS for Next.js frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Request/Response Models
class ChatRequest(BaseModel):
    message: str
    use_deep_research: Optional[bool] = False


class ChatResponse(BaseModel):
    type: str
    content: str
    code: Optional[str] = None
    datasets: Optional[list] = None


class AnalysisRequest(BaseModel):
    query: str
    use_deep_research: Optional[bool] = False


# WebSocket connections
active_connections: list[WebSocket] = []


@app.get("/")
async def root():
    return {"message": "Orbital Insight API", "status": "running"}


@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """
    Process a chat message through the agent system.
    """
    try:
        result = await orchestrator.process_user_message(request.message)
        return ChatResponse(
            type=result.get("type", "general"),
            content=result.get("content", ""),
            code=result.get("code"),
            datasets=result.get("datasets")
        )
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/analyze")
async def analyze(request: AnalysisRequest):
    """
    Run a full analysis pipeline.
    """
    try:
        result = await orchestrator.run_full_analysis(
            request.query,
            request.use_deep_research
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/context")
async def get_context():
    """
    Get the current shared memory context.
    """
    return shared_memory.get_full_context()


@app.get("/latest-script")
async def get_latest_script():
    """
    Get the most recent generated script.
    """
    script = shared_memory.get_latest_script()
    if script:
        return script.to_dict()
    return {"message": "No scripts generated yet"}


@app.delete("/clear")
async def clear_memory():
    """
    Clear all stored memory.
    """
    shared_memory.clear()
    return {"message": "Memory cleared"}


# WebSocket for real-time thought streaming
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """
    WebSocket endpoint for real-time thought streaming.
    Clients receive all agent thoughts as they happen.
    """
    await websocket.accept()
    active_connections.append(websocket)
    
    try:
        # Stream thoughts from shared memory
        async for item in shared_memory.thought_stream():
            try:
                await websocket.send_json(item)
            except Exception:
                break
    except WebSocketDisconnect:
        active_connections.remove(websocket)
    except Exception:
        if websocket in active_connections:
            active_connections.remove(websocket)


@app.websocket("/ws/chat")
async def websocket_chat(websocket: WebSocket):
    """
    WebSocket endpoint for interactive chat with streaming.
    """
    await websocket.accept()
    
    try:
        while True:
            # Receive message from client
            data = await websocket.receive_json()
            message = data.get("message", "")
            
            if not message:
                continue
            
            # Start processing in background
            result_task = asyncio.create_task(
                orchestrator.process_user_message(message)
            )
            
            # Stream thoughts while processing
            stream_task = asyncio.create_task(
                stream_thoughts_to_websocket(websocket)
            )
            
            # Wait for processing to complete
            result = await result_task
            
            # Cancel streaming
            stream_task.cancel()
            
            # Send final result
            await websocket.send_json({
                "type": "result",
                "data": result
            })
            
    except WebSocketDisconnect:
        pass
    except Exception as e:
        try:
            await websocket.send_json({"type": "error", "message": str(e)})
        except:
            pass


async def stream_thoughts_to_websocket(websocket: WebSocket):
    """Helper to stream thoughts during processing."""
    try:
        async for item in shared_memory.thought_stream():
            await websocket.send_json({
                "type": "thought",
                "data": item
            })
    except asyncio.CancelledError:
        pass


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
