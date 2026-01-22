"use client";

import { useState, useEffect, useRef } from "react";

interface AnalysisResult {
  content: string;
  code?: string;
  datasets?: string[];
}

interface Thought {
  agent: string;
  content: string;
  timestamp: string;
}

interface FormData {
  objective: string;
  latitude: string;
  longitude: string;
  startDate: string;
  endDate: string;
  methodologyNotes: string;
}

type ViewState = "form" | "thinking" | "dashboard";
type DashboardTab = "overview" | "methodology" | "code" | "logs";

const tabs: { id: DashboardTab; label: string; icon: string }[] = [
  { id: "overview", label: "Overview", icon: "📊" },
  { id: "methodology", label: "Methodology & Sources", icon: "📚" },
  { id: "code", label: "Generated Code", icon: "💻" },
  { id: "logs", label: "Thought Logs", icon: "🧠" },
];

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

export default function Home() {
  const [formData, setFormData] = useState<FormData>({
    objective: "",
    latitude: "",
    longitude: "",
    startDate: "2023-01-01",
    endDate: "2024-01-01",
    methodologyNotes: "",
  });
  const [result, setResult] = useState<AnalysisResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [thoughts, setThoughts] = useState<Thought[]>([]);
  const [connected, setConnected] = useState(false);
  const [viewState, setViewState] = useState<ViewState>("form");
  const [activeTab, setActiveTab] = useState<DashboardTab>("overview");
  const wsRef = useRef<WebSocket | null>(null);
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
      } else if (data.type === "thought_stream") {
        setThoughts((prev) => {
          const last = prev[prev.length - 1];
          // Only append if the last thought is from the same agent, implies continuity
          if (last && last.agent === data.agent) {
            const updatedLast = { ...last, content: last.content + data.content };
            return [...prev.slice(0, -1), updatedLast];
          } else {
            // Fallback if stream starts without a thought (shouldn't happen with my backend change)
            // or if agent switched
            return [...prev, { agent: data.agent, content: data.content, timestamp: data.timestamp }];
          }
        });
      } else if (data.agent) {
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

  // Auto-scroll thoughts
  useEffect(() => {
    thoughtsEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [thoughts]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!formData.objective.trim() || loading) return;

    setLoading(true);
    setThoughts([]);
    setResult(null);
    setViewState("thinking");

    const message = `
Research Objective: ${formData.objective}
Location: Latitude ${formData.latitude}, Longitude ${formData.longitude}
Time Period: ${formData.startDate} to ${formData.endDate}
${formData.methodologyNotes ? `Methodology Notes: ${formData.methodologyNotes}` : ""}
    `.trim();

    try {
      const response = await fetch("http://localhost:8000/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message }),
      });

      const data = await response.json();
      setResult({
        content: data.content,
        code: data.code,
        datasets: data.datasets,
      });
      setViewState("dashboard");
      setActiveTab("overview");
    } catch (error) {
      setResult({
        content: "Error connecting to the server. Please ensure the backend is running.",
      });
      setViewState("dashboard");
    } finally {
      setLoading(false);
    }
  };

  const copyCode = () => {
    if (result?.code) {
      navigator.clipboard.writeText(result.code);
    }
  };

  const resetToForm = () => {
    setViewState("form");
    setResult(null);
    setThoughts([]);
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-950 via-slate-900 to-slate-950 text-white">
      {/* Header */}
      <header className="border-b border-slate-800/50 backdrop-blur-sm bg-slate-900/30 sticky top-0 z-50">
        <div className="max-w-7xl mx-auto px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-cyan-500 to-blue-600 flex items-center justify-center text-lg font-bold shadow-lg shadow-cyan-500/20">
              🌍
            </div>
            <div>
              <h1 className="text-xl font-semibold tracking-tight">
                Google Earth Engine GEO AI
              </h1>
              <p className="text-xs text-slate-400">POWERED BY GEMINI 3</p>
            </div>
          </div>
          <div className="flex items-center gap-4">
            {viewState === "dashboard" && (
              <button
                onClick={resetToForm}
                className="px-4 py-2 text-sm bg-slate-800 hover:bg-slate-700 rounded-lg transition-colors"
              >
                ← New Analysis
              </button>
            )}
            <div className="flex items-center gap-2 px-3 py-1.5 bg-slate-800/60 rounded-full border border-slate-700/50">
              <span className="text-yellow-400 text-sm">✨</span>
              <span className="text-xs text-slate-300">
                Search Grounding & Thinking Enabled
              </span>
            </div>
            <div className="flex items-center gap-2">
              <div
                className={`w-2 h-2 rounded-full ${connected ? "bg-emerald-500" : "bg-red-500"
                  }`}
              />
              <span className="text-xs text-slate-400">
                {connected ? "Connected" : "Disconnected"}
              </span>
            </div>
          </div>
        </div>
      </header>

      <main>
        {/* FORM VIEW */}
        {viewState === "form" && (
          <div className="max-w-2xl mx-auto px-6 py-12">
            <div className="text-center mb-8">
              <div className="w-20 h-20 mx-auto rounded-2xl bg-gradient-to-br from-cyan-500/20 to-blue-600/20 flex items-center justify-center text-4xl mb-4 border border-cyan-500/20">
                🛰️
              </div>
              <h2 className="text-2xl font-semibold text-slate-200 mb-2">
                Geospatial Analysis Mission
              </h2>
              <p className="text-slate-500">
                Define your research parameters and let the AI agents generate methodology and code
              </p>
            </div>

            <form onSubmit={handleSubmit} className="space-y-6">
              {/* Research Objective */}
              <div className="space-y-2">
                <label className="flex items-center gap-2 text-sm font-medium text-cyan-400">
                  <span className="text-base">🔍</span>
                  Research Objective
                </label>
                <input
                  type="text"
                  name="objective"
                  value={formData.objective}
                  onChange={(e) => setFormData(prev => ({ ...prev, objective: e.target.value }))}
                  placeholder="Illegal gold mining detection using spectra"
                  className="w-full bg-slate-900/80 border border-slate-700/50 rounded-xl px-4 py-3 text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-cyan-500/50 focus:border-cyan-500 transition-all"
                />
              </div>

              {/* Coordinates */}
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <label className="flex items-center gap-2 text-sm font-medium text-cyan-400">
                    <span className="text-base">📍</span>
                    Latitude
                  </label>
                  <input
                    type="number"
                    name="latitude"
                    value={formData.latitude}
                    onChange={(e) => setFormData(prev => ({ ...prev, latitude: e.target.value }))}
                    placeholder="-12.91"
                    step="any"
                    className="w-full bg-slate-900/80 border border-slate-700/50 rounded-xl px-4 py-3 text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-cyan-500/50 focus:border-cyan-500 transition-all"
                  />
                </div>
                <div className="space-y-2">
                  <label className="flex items-center gap-2 text-sm font-medium text-cyan-400">
                    <span className="text-base">📍</span>
                    Longitude
                  </label>
                  <input
                    type="number"
                    name="longitude"
                    value={formData.longitude}
                    onChange={(e) => setFormData(prev => ({ ...prev, longitude: e.target.value }))}
                    placeholder="-70.52"
                    step="any"
                    className="w-full bg-slate-900/80 border border-slate-700/50 rounded-xl px-4 py-3 text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-cyan-500/50 focus:border-cyan-500 transition-all"
                  />
                </div>
              </div>

              {/* Date Range */}
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <label className="flex items-center gap-2 text-sm font-medium text-emerald-400">
                    <span className="text-base">📅</span>
                    Start Date
                  </label>
                  <input
                    type="date"
                    name="startDate"
                    value={formData.startDate}
                    onChange={(e) => setFormData(prev => ({ ...prev, startDate: e.target.value }))}
                    className="w-full bg-slate-900/80 border border-slate-700/50 rounded-xl px-4 py-3 text-white focus:outline-none focus:ring-2 focus:ring-cyan-500/50 focus:border-cyan-500 transition-all [color-scheme:dark]"
                  />
                </div>
                <div className="space-y-2">
                  <label className="flex items-center gap-2 text-sm font-medium text-emerald-400">
                    <span className="text-base">📅</span>
                    End Date
                  </label>
                  <input
                    type="date"
                    name="endDate"
                    value={formData.endDate}
                    onChange={(e) => setFormData(prev => ({ ...prev, endDate: e.target.value }))}
                    className="w-full bg-slate-900/80 border border-slate-700/50 rounded-xl px-4 py-3 text-white focus:outline-none focus:ring-2 focus:ring-cyan-500/50 focus:border-cyan-500 transition-all [color-scheme:dark]"
                  />
                </div>
              </div>

              {/* Methodology Notes */}
              <div className="space-y-2">
                <label className="flex items-center gap-2 text-sm font-medium text-slate-400">
                  <span className="text-base">✨</span>
                  Methodology Notes (Optional)
                </label>
                <textarea
                  name="methodologyNotes"
                  value={formData.methodologyNotes}
                  onChange={(e) => setFormData(prev => ({ ...prev, methodologyNotes: e.target.value }))}
                  placeholder="e.g. Prefer Sentinel-2 over Landsat, check for specific vegetation indices..."
                  rows={3}
                  className="w-full bg-slate-900/80 border border-slate-700/50 rounded-xl px-4 py-3 text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-cyan-500/50 focus:border-cyan-500 transition-all resize-none"
                />
              </div>

              {/* Submit Button */}
              <button
                type="submit"
                disabled={loading || !formData.objective.trim()}
                className="w-full py-4 bg-gradient-to-r from-cyan-600 to-blue-600 hover:from-cyan-500 hover:to-blue-500 disabled:opacity-50 disabled:cursor-not-allowed rounded-xl font-semibold text-lg transition-all shadow-lg shadow-cyan-500/20 hover:shadow-cyan-500/30"
              >
                Generate Methodology & Code
              </button>
            </form>

            {/* How it works */}
            <div className="mt-8 p-4 bg-slate-900/50 rounded-xl border border-slate-800/50">
              <p className="text-sm text-slate-400">
                <span className="font-medium text-slate-300">How it works:</span>{" "}
                This agent uses Gemini 3 to act as a senior remote sensing researcher.
                It analyzes your research objective, selects appropriate satellite data,
                and generates production-ready Earth Engine code.
              </p>
            </div>
          </div>
        )}

        {/* THINKING DIALOG */}
        {viewState === "thinking" && (
          <div className="fixed inset-0 bg-slate-950/90 backdrop-blur-sm z-50 flex items-center justify-center p-6">
            <div className="w-full max-w-2xl bg-slate-900 rounded-2xl border border-slate-700/50 shadow-2xl overflow-hidden">
              {/* Dialog Header */}
              <div className="px-6 py-4 border-b border-slate-800/50 bg-gradient-to-r from-slate-900 to-slate-800">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-cyan-500 to-blue-600 flex items-center justify-center animate-pulse">
                    🧠
                  </div>
                  <div>
                    <h2 className="font-semibold text-lg text-white">Agents Analyzing...</h2>
                    <p className="text-sm text-slate-400">
                      Researching methodology and generating code
                    </p>
                  </div>
                </div>
              </div>

              {/* Thought Stream */}
              <div className="h-80 overflow-y-auto p-4 space-y-3 bg-slate-950/50">
                {thoughts.length === 0 ? (
                  <div className="h-full flex items-center justify-center">
                    <div className="text-center space-y-3">
                      <div className="flex justify-center gap-1">
                        <span className="w-3 h-3 bg-cyan-500 rounded-full animate-bounce" />
                        <span
                          className="w-3 h-3 bg-cyan-500 rounded-full animate-bounce"
                          style={{ animationDelay: "0.1s" }}
                        />
                        <span
                          className="w-3 h-3 bg-cyan-500 rounded-full animate-bounce"
                          style={{ animationDelay: "0.2s" }}
                        />
                      </div>
                      <p className="text-slate-500">Initializing agents...</p>
                    </div>
                  </div>
                ) : (
                  thoughts.map((thought, i) => (
                    <div
                      key={i}
                      className="p-3 bg-slate-800/50 rounded-xl border border-slate-700/30 animate-fadeIn"
                    >
                      <div className="flex items-center gap-2 mb-1">
                        <span className="text-lg">{getAgentIcon(thought.agent)}</span>
                        <span
                          className={`text-xs font-semibold uppercase tracking-wide ${getAgentColor(thought.agent)}`}
                        >
                          {thought.agent}
                        </span>
                        <span className="text-xs text-slate-600">
                          {new Date(thought.timestamp).toLocaleTimeString()}
                        </span>
                      </div>
                      <p className="text-sm text-slate-300 leading-relaxed">
                        {thought.content}
                      </p>
                    </div>
                  ))
                )}
                <div ref={thoughtsEndRef} />
              </div>

              {/* Progress Indicator */}
              <div className="px-6 py-4 border-t border-slate-800/50 bg-slate-900">
                <div className="flex items-center gap-3">
                  <div className="flex-1 h-1.5 bg-slate-800 rounded-full overflow-hidden">
                    <div className="h-full bg-gradient-to-r from-cyan-500 to-blue-500 rounded-full animate-progress" />
                  </div>
                  <span className="text-xs text-slate-500">
                    {thoughts.length} thoughts
                  </span>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* DASHBOARD VIEW */}
        {viewState === "dashboard" && (
          <div className="max-w-7xl mx-auto px-6 py-6">
            {/* Tab Navigation */}
            <div className="flex gap-2 mb-6 p-1 bg-slate-900/50 rounded-xl border border-slate-800/50 w-fit">
              {tabs.map((tab) => (
                <button
                  key={tab.id}
                  onClick={() => setActiveTab(tab.id)}
                  className={`px-4 py-2.5 rounded-lg text-sm font-medium transition-all flex items-center gap-2 ${activeTab === tab.id
                    ? "bg-gradient-to-r from-cyan-600 to-blue-600 text-white shadow-lg"
                    : "text-slate-400 hover:text-white hover:bg-slate-800"
                    }`}
                >
                  <span>{tab.icon}</span>
                  {tab.label}
                </button>
              ))}
            </div>

            {/* Tab Content */}
            <div className="bg-slate-900/50 rounded-2xl border border-slate-800/50 min-h-[60vh]">
              {activeTab === "overview" && (
                <div className="p-6 space-y-6">
                  <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                    {/* Mission Summary Card */}
                    <div className="p-5 bg-slate-800/50 rounded-xl border border-slate-700/30">
                      <div className="flex items-center gap-2 mb-3">
                        <span className="text-xl">🎯</span>
                        <h3 className="font-medium text-slate-200">Mission</h3>
                      </div>
                      <p className="text-sm text-slate-400">{formData.objective}</p>
                    </div>

                    {/* Location Card */}
                    <div className="p-5 bg-slate-800/50 rounded-xl border border-slate-700/30">
                      <div className="flex items-center gap-2 mb-3">
                        <span className="text-xl">📍</span>
                        <h3 className="font-medium text-slate-200">Location</h3>
                      </div>
                      <p className="text-sm text-slate-400">
                        {formData.latitude || "N/A"}, {formData.longitude || "N/A"}
                      </p>
                    </div>

                    {/* Time Range Card */}
                    <div className="p-5 bg-slate-800/50 rounded-xl border border-slate-700/30">
                      <div className="flex items-center gap-2 mb-3">
                        <span className="text-xl">📅</span>
                        <h3 className="font-medium text-slate-200">Time Period</h3>
                      </div>
                      <p className="text-sm text-slate-400">
                        {formData.startDate} → {formData.endDate}
                      </p>
                    </div>
                  </div>

                  {/* Datasets Used */}
                  {result?.datasets && result.datasets.length > 0 && (
                    <div className="p-5 bg-slate-800/50 rounded-xl border border-slate-700/30">
                      <div className="flex items-center gap-2 mb-3">
                        <span className="text-xl">🛰️</span>
                        <h3 className="font-medium text-slate-200">Datasets Identified</h3>
                      </div>
                      <div className="flex flex-wrap gap-2">
                        {result.datasets.map((ds) => (
                          <span
                            key={ds}
                            className="px-3 py-1.5 bg-cyan-900/30 text-cyan-300 rounded-lg border border-cyan-800/50 text-sm"
                          >
                            {ds}
                          </span>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Quick Summary */}
                  <div className="p-5 bg-gradient-to-br from-slate-800/50 to-slate-900/50 rounded-xl border border-slate-700/30">
                    <div className="flex items-center gap-2 mb-3">
                      <span className="text-xl">✅</span>
                      <h3 className="font-medium text-slate-200">Analysis Complete</h3>
                    </div>
                    <p className="text-sm text-slate-400 leading-relaxed">
                      {result?.content?.slice(0, 300)}
                      {result?.content && result.content.length > 300 ? "..." : ""}
                    </p>
                    <button
                      onClick={() => setActiveTab("methodology")}
                      className="mt-3 text-sm text-cyan-400 hover:text-cyan-300 transition-colors"
                    >
                      Read full methodology →
                    </button>
                  </div>
                </div>
              )}

              {activeTab === "methodology" && (
                <div className="p-6">
                  <div className="prose prose-invert prose-sm max-w-none">
                    <h2 className="text-xl font-semibold text-slate-200 mb-4 flex items-center gap-2">
                      <span>📚</span> Research Methodology
                    </h2>
                    <div className="p-5 bg-slate-800/30 rounded-xl border border-slate-700/30">
                      <p className="text-slate-300 whitespace-pre-wrap leading-relaxed">
                        {result?.content || "No methodology available."}
                      </p>
                    </div>
                  </div>
                </div>
              )}

              {activeTab === "code" && (
                <div className="p-6 space-y-4">
                  <div className="flex items-center justify-between">
                    <h2 className="text-xl font-semibold text-slate-200 flex items-center gap-2">
                      <span>💻</span> Generated Earth Engine Script
                    </h2>
                    <div className="flex gap-2">
                      <button
                        onClick={copyCode}
                        className="px-4 py-2 text-sm bg-slate-700 hover:bg-slate-600 rounded-lg transition-colors flex items-center gap-2"
                      >
                        📋 Copy Code
                      </button>
                      <a
                        href="https://code.earthengine.google.com"
                        target="_blank"
                        rel="noopener noreferrer"
                        className="px-4 py-2 text-sm bg-gradient-to-r from-cyan-600 to-blue-600 hover:from-cyan-500 hover:to-blue-500 rounded-lg transition-colors flex items-center gap-2"
                      >
                        🌍 Open in Earth Engine
                      </a>
                    </div>
                  </div>
                  <pre className="bg-slate-950 rounded-xl p-6 overflow-x-auto text-sm text-slate-300 border border-slate-800/50 max-h-[60vh] overflow-y-auto">
                    <code>{result?.code || "// No code generated yet"}</code>
                  </pre>
                </div>
              )}

              {activeTab === "logs" && (
                <div className="p-6">
                  <h2 className="text-xl font-semibold text-slate-200 mb-4 flex items-center gap-2">
                    <span>🧠</span> Agent Thought Logs
                    <span className="text-sm font-normal text-slate-500">
                      ({thoughts.length} thoughts)
                    </span>
                  </h2>
                  <div className="space-y-3 max-h-[60vh] overflow-y-auto">
                    {thoughts.length === 0 ? (
                      <p className="text-slate-500 text-sm">No thoughts recorded.</p>
                    ) : (
                      thoughts.map((thought, i) => (
                        <div
                          key={i}
                          className="p-4 bg-slate-800/50 rounded-xl border border-slate-700/30"
                        >
                          <div className="flex items-center gap-2 mb-2">
                            <span className="text-lg">{getAgentIcon(thought.agent)}</span>
                            <span
                              className={`text-xs font-semibold uppercase tracking-wide ${getAgentColor(thought.agent)}`}
                            >
                              {thought.agent}
                            </span>
                            <span className="text-xs text-slate-600">
                              {new Date(thought.timestamp).toLocaleTimeString()}
                            </span>
                          </div>
                          <p className="text-sm text-slate-300">{thought.content}</p>
                        </div>
                      ))
                    )}
                  </div>
                </div>
              )}
            </div>
          </div>
        )}
      </main>

      {/* Keep thinking dialog visible during loading even when on dashboard transition */}
      {loading && viewState !== "thinking" && (
        <div className="fixed inset-0 bg-slate-950/90 backdrop-blur-sm z-50 flex items-center justify-center p-6">
          <div className="w-full max-w-2xl bg-slate-900 rounded-2xl border border-slate-700/50 shadow-2xl overflow-hidden">
            <div className="px-6 py-4 border-b border-slate-800/50 bg-gradient-to-r from-slate-900 to-slate-800">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-cyan-500 to-blue-600 flex items-center justify-center animate-pulse">
                  🧠
                </div>
                <div>
                  <h2 className="font-semibold text-lg text-white">Agents Analyzing...</h2>
                  <p className="text-sm text-slate-400">
                    Researching methodology and generating code
                  </p>
                </div>
              </div>
            </div>
            <div className="h-80 overflow-y-auto p-4 space-y-3 bg-slate-950/50">
              {thoughts.map((thought, i) => (
                <div
                  key={i}
                  className="p-3 bg-slate-800/50 rounded-xl border border-slate-700/30 animate-fadeIn"
                >
                  <div className="flex items-center gap-2 mb-1">
                    <span className="text-lg">{getAgentIcon(thought.agent)}</span>
                    <span
                      className={`text-xs font-semibold uppercase tracking-wide ${getAgentColor(thought.agent)}`}
                    >
                      {thought.agent}
                    </span>
                  </div>
                  <p className="text-sm text-slate-300">{thought.content}</p>
                </div>
              ))}
              <div ref={thoughtsEndRef} />
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
