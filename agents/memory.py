"""
Shared Memory Store for Multi-Agent System

Stores all agent thoughts, research context, code outputs, and inter-agent messages.
Enables real-time streaming via WebSocket and provides full context to Chat Agent.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, AsyncGenerator, Callable, Optional
from enum import Enum
import asyncio
import json


class AgentType(str, Enum):
    CHAT = "chat"
    RESEARCHER = "researcher"
    CODER = "coder"


class MessageType(str, Enum):
    THOUGHT = "thought"
    RESEARCH = "research"
    CODE = "code"
    QUESTION = "question"
    ANSWER = "answer"
    USER_MESSAGE = "user_message"
    AGENT_RESPONSE = "agent_response"
    SOURCE = "source"  # Grounding source with URL
    SEARCH_QUERY = "search_query"  # Google Search query used
    TOOL_CALL = "tool_call"  # Tool invocation
    METHODOLOGY = "methodology"  # Synthesized methodology section


@dataclass
class Thought:
    """A single thought from an agent."""
    agent: AgentType
    content: str
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: dict = field(default_factory=dict)
    
    def to_dict(self) -> dict:
        return {
            "type": "thought",
            "agent": self.agent.value,
            "content": self.content,
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata
        }


@dataclass
class AgentMessage:
    """Inter-agent communication message."""
    from_agent: AgentType
    to_agent: AgentType
    message_type: MessageType
    content: str
    timestamp: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> dict:
        return {
            "type": "agent_message",
            "from": self.from_agent.value,
            "to": self.to_agent.value,
            "message_type": self.message_type.value,
            "content": self.content,
            "timestamp": self.timestamp.isoformat()
        }


@dataclass
class Script:
    """Generated Earth Engine script."""
    code: str
    description: str
    datasets_used: list[str] = field(default_factory=list)
    timestamp: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> dict:
        return {
            "type": "script",
            "code": self.code,
            "description": self.description,
            "datasets_used": self.datasets_used,
            "timestamp": self.timestamp.isoformat()
        }


class SharedMemory:
    """
    Central memory store accessible by all agents.
    
    Features:
    - Real-time thought streaming via callbacks
    - Full context retrieval for Chat Agent
    - Inter-agent message passing
    - Persistent conversation history
    """
    
    def __init__(self):
        self.thoughts: list[Thought] = []
        self.research_context: dict[str, Any] = {}
        self.code_outputs: list[Script] = []
        self.agent_messages: list[AgentMessage] = []
        self.conversation_history: list[dict] = []
        
        # Callbacks for real-time streaming
        self._thought_callbacks: list[Callable] = []
        self._message_callbacks: list[Callable] = []
        
        # Async queue for streaming
        self._stream_queue: asyncio.Queue = asyncio.Queue()
    
    def add_thought(self, agent: AgentType, content: str, metadata: dict = None) -> Thought:
        """Add a thought and notify all listeners."""
        thought = Thought(
            agent=agent,
            content=content,
            metadata=metadata or {}
        )
        self.thoughts.append(thought)
        
        # Trigger callbacks for real-time streaming
        for callback in self._thought_callbacks:
            try:
                callback(thought)
            except Exception:
                pass
        
        # Add to async stream queue
        try:
            self._stream_queue.put_nowait(thought.to_dict())
        except asyncio.QueueFull:
            pass
        
        return thought
    
    def add_stream_update(self, agent: AgentType, content_chunk: str, metadata: dict = None) -> None:
        """Stream a partial update (token/chunk) without creating a new thought."""
        data = {
            "type": "thought_stream",
            "agent": agent.value,
            "content": content_chunk,
            "timestamp": datetime.now().isoformat(),
            "metadata": metadata or {}
        }
        
        # Add to async stream queue
        try:
            self._stream_queue.put_nowait(data)
        except asyncio.QueueFull:
            pass
    
    def add_source(self, agent: AgentType, title: str, uri: str) -> None:
        """Stream a grounding source with URL."""
        data = {
            "type": "source",
            "agent": agent.value,
            "title": title,
            "uri": uri,
            "timestamp": datetime.now().isoformat()
        }
        
        # Also add as a thought for persistence
        self.thoughts.append(Thought(
            agent=agent,
            content=f"📎 Source: {title}",
            metadata={"uri": uri, "title": title}
        ))
        
        try:
            self._stream_queue.put_nowait(data)
        except asyncio.QueueFull:
            pass
    
    def add_search_query(self, agent: AgentType, query: str) -> None:
        """Stream a Google Search query that was used."""
        data = {
            "type": "search_query",
            "agent": agent.value,
            "query": query,
            "timestamp": datetime.now().isoformat()
        }
        
        # Also add as a thought for persistence
        self.thoughts.append(Thought(
            agent=agent,
            content=f"🔍 Searched: {query}",
            metadata={"query": query}
        ))
        
        try:
            self._stream_queue.put_nowait(data)
        except asyncio.QueueFull:
            pass
    
    def add_tool_call(self, agent: AgentType, tool_name: str, description: str = "") -> None:
        """Stream a tool invocation event."""
        data = {
            "type": "tool_call",
            "agent": agent.value,
            "tool": tool_name,
            "description": description,
            "timestamp": datetime.now().isoformat()
        }
        
        self.thoughts.append(Thought(
            agent=agent,
            content=f"🔧 Calling: {tool_name}" + (f" - {description}" if description else ""),
            metadata={"tool": tool_name}
        ))
        
        try:
            self._stream_queue.put_nowait(data)
        except asyncio.QueueFull:
            pass
    
    def add_agent_message(
        self,
        from_agent: AgentType,
        to_agent: AgentType,
        message_type: MessageType,
        content: str
    ) -> AgentMessage:
        """Record inter-agent communication."""
        msg = AgentMessage(
            from_agent=from_agent,
            to_agent=to_agent,
            message_type=message_type,
            content=content
        )
        self.agent_messages.append(msg)
        
        # Stream to listeners
        try:
            self._stream_queue.put_nowait(msg.to_dict())
        except asyncio.QueueFull:
            pass
        
        return msg
    
    def add_script(self, code: str, description: str, datasets: list[str] = None) -> Script:
        """Store a generated script."""
        script = Script(
            code=code,
            description=description,
            datasets_used=datasets or []
        )
        self.code_outputs.append(script)
        
        # Stream to listeners
        try:
            self._stream_queue.put_nowait(script.to_dict())
        except asyncio.QueueFull:
            pass
            
        return script
    
    def set_research_context(self, key: str, value: Any) -> None:
        """Store research findings."""
        self.research_context[key] = {
            "value": value,
            "timestamp": datetime.now().isoformat()
        }
    
    def add_conversation_turn(self, role: str, content: str) -> None:
        """Add to conversation history."""
        self.conversation_history.append({
            "role": role,
            "content": content,
            "timestamp": datetime.now().isoformat()
        })
    
    def get_full_context(self) -> dict:
        """
        Get complete context for Chat Agent.
        Includes all thoughts, research, code, and messages.
        """
        return {
            "thoughts": [t.to_dict() for t in self.thoughts[-50:]],  # Last 50 thoughts
            "research_context": self.research_context,
            "code_outputs": [s.to_dict() for s in self.code_outputs],
            "agent_messages": [m.to_dict() for m in self.agent_messages[-20:]],
            "conversation_history": self.conversation_history[-20:]
        }
    
    def get_latest_script(self) -> Optional[Script]:
        """Get the most recent generated script."""
        return self.code_outputs[-1] if self.code_outputs else None
    
    def on_thought(self, callback: Callable[[Thought], None]) -> None:
        """Register callback for real-time thought streaming."""
        self._thought_callbacks.append(callback)
    
    async def thought_stream(self) -> AsyncGenerator[dict, None]:
        """Async generator for streaming thoughts via WebSocket."""
        while True:
            try:
                item = await asyncio.wait_for(self._stream_queue.get(), timeout=30.0)
                yield item
            except asyncio.TimeoutError:
                # Send keepalive
                yield {"type": "keepalive", "timestamp": datetime.now().isoformat()}
    
    def get_pending_questions(self, for_agent: AgentType) -> list[AgentMessage]:
        """Get unanswered questions directed at an agent."""
        questions = [
            m for m in self.agent_messages
            if m.to_agent == for_agent and m.message_type == MessageType.QUESTION
        ]
        # Filter out answered ones
        answered_ids = set()
        for m in self.agent_messages:
            if m.message_type == MessageType.ANSWER:
                # Find the question this answers (simple heuristic)
                for q in questions:
                    if m.from_agent == q.to_agent and m.to_agent == q.from_agent:
                        answered_ids.add(id(q))
        
        return [q for q in questions if id(q) not in answered_ids]
    
    def clear(self) -> None:
        """Clear all stored data."""
        self.thoughts.clear()
        self.research_context.clear()
        self.code_outputs.clear()
        self.agent_messages.clear()
        self.conversation_history.clear()


# Global shared memory instance
shared_memory = SharedMemory()
