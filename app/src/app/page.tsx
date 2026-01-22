"use client";

import { useState, useEffect, useRef } from "react";

interface Message {
  role: "user" | "assistant";
  content: string;
  code?: string;
  datasets?: string[];
}

interface Thought {
  agent: string;
  content: string;
  timestamp: string;
}

export default function Home() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [thoughts, setThoughts] = useState<Thought[]>([]);
  const [currentCode, setCurrentCode] = useState<string | null>(null);
  const [connected, setConnected] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const thoughtsEndRef = useRef<HTMLDivElement>(null);

  // Connect to WebSocket for real-time thought streaming
  useEffect(() => {
    const ws = new WebSocket("ws://localhost:8000/ws");

    ws.onopen = () => {
      setConnected(true);
      console.log("Connected to thought stream");
    };

    ws.onmessage = (event) => {
      const data = JSON.parse(event.data);
      if (data.type === "thought") {
        setThoughts((prev) => [...prev, data]);
      } else if (data.agent) {
        // Direct thought object
        setThoughts((prev) => [...prev, data as Thought]);
      }
    };

    ws.onclose = () => {
      setConnected(false);
      console.log("Disconnected from thought stream");
    };

    wsRef.current = ws;

    return () => {
      ws.close();
    };
  }, []);

  // Auto-scroll
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  useEffect(() => {
    thoughtsEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [thoughts]);

  const sendMessage = async () => {
    if (!input.trim() || loading) return;

    const userMessage = input.trim();
    setInput("");
    setMessages((prev) => [...prev, { role: "user", content: userMessage }]);
    setLoading(true);

    try {
      const response = await fetch("http://localhost:8000/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: userMessage }),
      });

      const data = await response.json();

      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content: data.content,
          code: data.code,
          datasets: data.datasets,
        },
      ]);

      if (data.code) {
        setCurrentCode(data.code);
      }
    } catch (error) {
      setMessages((prev) => [
        ...prev,
        { role: "assistant", content: "Error connecting to the server." },
      ]);
    } finally {
      setLoading(false);
    }
  };

  const copyCode = () => {
    if (currentCode) {
      navigator.clipboard.writeText(currentCode);
    }
  };

  const getAgentIcon = (agent: string) => {
    switch (agent) {
      case "researcher":
        return "🔬";
      case "coder":
        return "💻";
      case "chat":
        return "💬";
      default:
        return "🤖";
    }
  };

  const getAgentColor = (agent: string) => {
    switch (agent) {
      case "researcher":
        return "text-purple-400";
      case "coder":
        return "text-emerald-400";
      case "chat":
        return "text-blue-400";
      default:
        return "text-gray-400";
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-950 via-slate-900 to-slate-950 text-white">
      {/* Header */}
      <header className="border-b border-slate-800/50 backdrop-blur-sm bg-slate-900/30 sticky top-0 z-50">
        <div className="max-w-7xl mx-auto px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-emerald-500 to-cyan-500 flex items-center justify-center text-lg font-bold">
              🌍
            </div>
            <div>
              <h1 className="text-xl font-semibold tracking-tight">
                Orbital Insight
              </h1>
              <p className="text-xs text-slate-400">
                Multi-Agent Geointelligence
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <div
              className={`w-2 h-2 rounded-full ${connected ? "bg-emerald-500" : "bg-red-500"}`}
            />
            <span className="text-xs text-slate-400">
              {connected ? "Connected" : "Disconnected"}
            </span>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="max-w-7xl mx-auto px-6 py-6">
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 h-[calc(100vh-140px)]">
          {/* Chat Panel */}
          <div className="lg:col-span-2 flex flex-col bg-slate-900/50 rounded-2xl border border-slate-800/50 overflow-hidden">
            {/* Messages */}
            <div className="flex-1 overflow-y-auto p-6 space-y-4">
              {messages.length === 0 && (
                <div className="h-full flex items-center justify-center">
                  <div className="text-center space-y-4">
                    <div className="w-20 h-20 mx-auto rounded-2xl bg-gradient-to-br from-emerald-500/20 to-cyan-500/20 flex items-center justify-center text-4xl">
                      🛰️
                    </div>
                    <h2 className="text-xl font-medium text-slate-300">
                      Welcome to Orbital Insight
                    </h2>
                    <p className="text-slate-500 max-w-md">
                      Ask me to analyze satellite imagery, detect changes, or
                      generate Earth Engine scripts for any geospatial analysis.
                    </p>
                    <div className="flex flex-wrap gap-2 justify-center mt-4">
                      {[
                        "Analyze deforestation in Amazon 2024",
                        "Show NDVI for California wildfires",
                        "Detect floods using SAR data",
                      ].map((example) => (
                        <button
                          key={example}
                          onClick={() => setInput(example)}
                          className="px-3 py-1.5 text-sm bg-slate-800 hover:bg-slate-700 rounded-lg transition-colors text-slate-300"
                        >
                          {example}
                        </button>
                      ))}
                    </div>
                  </div>
                </div>
              )}

              {messages.map((msg, i) => (
                <div
                  key={i}
                  className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}
                >
                  <div
                    className={`max-w-[80%] rounded-2xl px-4 py-3 ${
                      msg.role === "user"
                        ? "bg-gradient-to-r from-emerald-600 to-cyan-600 text-white"
                        : "bg-slate-800/80 text-slate-200"
                    }`}
                  >
                    <p className="whitespace-pre-wrap">{msg.content}</p>
                    {msg.datasets && msg.datasets.length > 0 && (
                      <div className="mt-2 flex flex-wrap gap-1">
                        {msg.datasets.slice(0, 3).map((ds) => (
                          <span
                            key={ds}
                            className="text-xs px-2 py-0.5 bg-slate-700 rounded-full"
                          >
                            {ds.split("/").pop()}
                          </span>
                        ))}
                      </div>
                    )}
                  </div>
                </div>
              ))}

              {loading && (
                <div className="flex justify-start">
                  <div className="bg-slate-800/80 rounded-2xl px-4 py-3 flex items-center gap-2">
                    <div className="flex gap-1">
                      <span className="w-2 h-2 bg-emerald-500 rounded-full animate-bounce" />
                      <span
                        className="w-2 h-2 bg-emerald-500 rounded-full animate-bounce"
                        style={{ animationDelay: "0.1s" }}
                      />
                      <span
                        className="w-2 h-2 bg-emerald-500 rounded-full animate-bounce"
                        style={{ animationDelay: "0.2s" }}
                      />
                    </div>
                    <span className="text-slate-400 text-sm">
                      Agents working...
                    </span>
                  </div>
                </div>
              )}

              <div ref={messagesEndRef} />
            </div>

            {/* Code Output */}
            {currentCode && (
              <div className="border-t border-slate-800/50 p-4 bg-slate-950/50">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-sm font-medium text-slate-300">
                    Generated Script
                  </span>
                  <div className="flex gap-2">
                    <button
                      onClick={copyCode}
                      className="px-3 py-1 text-xs bg-slate-700 hover:bg-slate-600 rounded-lg transition-colors flex items-center gap-1"
                    >
                      📋 Copy
                    </button>
                    <a
                      href="https://code.earthengine.google.com"
                      target="_blank"
                      rel="noopener noreferrer"
                      className="px-3 py-1 text-xs bg-emerald-600 hover:bg-emerald-500 rounded-lg transition-colors flex items-center gap-1"
                    >
                      🌍 Open in Earth Engine
                    </a>
                  </div>
                </div>
                <pre className="bg-slate-900 rounded-lg p-4 overflow-x-auto text-sm text-slate-300 max-h-48 overflow-y-auto">
                  <code>{currentCode}</code>
                </pre>
              </div>
            )}

            {/* Input */}
            <div className="border-t border-slate-800/50 p-4">
              <div className="flex gap-3">
                <input
                  type="text"
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  onKeyPress={(e) => e.key === "Enter" && sendMessage()}
                  placeholder="Ask about geospatial analysis..."
                  className="flex-1 bg-slate-800 border border-slate-700 rounded-xl px-4 py-3 text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-emerald-500/50 focus:border-emerald-500"
                />
                <button
                  onClick={sendMessage}
                  disabled={loading || !input.trim()}
                  className="px-6 py-3 bg-gradient-to-r from-emerald-600 to-cyan-600 hover:from-emerald-500 hover:to-cyan-500 disabled:opacity-50 disabled:cursor-not-allowed rounded-xl font-medium transition-all"
                >
                  Send
                </button>
              </div>
            </div>
          </div>

          {/* Thinking Logs Panel */}
          <div className="flex flex-col bg-slate-900/50 rounded-2xl border border-slate-800/50 overflow-hidden">
            <div className="px-4 py-3 border-b border-slate-800/50 bg-slate-900/80">
              <h2 className="font-medium text-slate-200 flex items-center gap-2">
                🧠 Thinking Logs
                <span className="text-xs text-slate-500">
                  ({thoughts.length})
                </span>
              </h2>
            </div>

            <div className="flex-1 overflow-y-auto p-4 space-y-3">
              {thoughts.length === 0 && (
                <div className="h-full flex items-center justify-center text-slate-500 text-sm">
                  Agent thoughts will appear here...
                </div>
              )}

              {thoughts.map((thought, i) => (
                <div
                  key={i}
                  className="p-3 bg-slate-800/50 rounded-xl border border-slate-700/30"
                >
                  <div className="flex items-center gap-2 mb-1">
                    <span>{getAgentIcon(thought.agent)}</span>
                    <span
                      className={`text-xs font-medium uppercase ${getAgentColor(thought.agent)}`}
                    >
                      {thought.agent}
                    </span>
                    <span className="text-xs text-slate-600">
                      {new Date(thought.timestamp).toLocaleTimeString()}
                    </span>
                  </div>
                  <p className="text-sm text-slate-300">{thought.content}</p>
                </div>
              ))}

              <div ref={thoughtsEndRef} />
            </div>

            {/* Clear button */}
            {thoughts.length > 0 && (
              <div className="border-t border-slate-800/50 p-3">
                <button
                  onClick={() => setThoughts([])}
                  className="w-full py-2 text-xs text-slate-400 hover:text-slate-200 transition-colors"
                >
                  Clear Logs
                </button>
              </div>
            )}
          </div>
        </div>
      </main>
    </div>
  );
}
