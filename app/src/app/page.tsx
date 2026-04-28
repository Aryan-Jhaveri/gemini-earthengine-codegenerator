"use client";

import { useState, useEffect, useRef } from "react";

interface AnalysisResult {
  content: string;
  code?: string;
  datasets?: string[];
}

interface Thought {
  type?: string;  // thought, source, search_query, tool_call, thinking_step
  agent: string;
  content: string;
  timestamp: string;
  // For source events
  title?: string;
  uri?: string;
  // For search_query events
  query?: string;
  // For tool_call events
  tool?: string;
  description?: string;
  // For thinking_step events
  step?: number;
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
type DashboardTab = "overview" | "methodology" | "code" | "logs" | "chat";

const tabs: { id: DashboardTab; label: string; icon: string }[] = [
  { id: "overview", label: "Overview", icon: "📊" },
  { id: "methodology", label: "Methodology & Sources", icon: "📚" },
  { id: "code", label: "Generated Code", icon: "💻" },
  { id: "logs", label: "Thought Logs", icon: "🧠" },
  { id: "chat", label: "Refine & Chat", icon: "💬" },
];

const getAgentIcon = (agent: string) => {
  switch (agent) {
    case "researcher":
      return "🔬";
    case "coder":
      return "💻";
    case "chat":
      return "💬";
    case "planner":
      return "📋";
    case "synthesizer":
      return "📝";
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
    case "planner":
      return "text-orange-400";
    case "synthesizer":
      return "text-pink-400";
    default:
      return "text-gray-400";
  }
};

// Preset examples for quick testing
const PRESET_EXAMPLES = [
  {
    name: "Illegal Gold Mining Detection (Peru)",
    data: {
      objective: "Detect illegal gold mining activity in Madre de Dios region using vegetation loss and water turbidity analysis",
      latitude: "-12.59",
      longitude: "-69.19",
      startDate: "2024-01-01",
      endDate: "2025-12-01",
      methodologyNotes: "Focus on deforestation and sediment load in rivers. Use NDVI change detection and water indices."
    }
  },
  {
    name: "Amazon Deforestation Monitoring (Brazil)",
    data: {
      objective: "Monitor deforestation rates in the Brazilian Amazon rainforest",
      latitude: "-3.47",
      longitude: "-62.21",
      startDate: "2023-01-01",
      endDate: "2024-12-01",
      methodologyNotes: "Use Sentinel-2 for cloud-free composites. Compare NDVI and forest cover changes year-over-year."
    }
  },
  {
    name: "Urban Expansion Analysis (Dubai)",
    data: {
      objective: "Analyze urban growth and land use change in Dubai metropolitan area",
      latitude: "25.20",
      longitude: "55.27",
      startDate: "2020-01-01",
      endDate: "2024-12-01",
      methodologyNotes: "Use built-up indices (NDBI) and land cover classification to track urban sprawl."
    }
  },
  {
    name: "Flood Detection (Pakistan)",
    data: {
      objective: "Detect and map flooding extent in Indus River basin during monsoon season",
      latitude: "27.70",
      longitude: "68.52",
      startDate: "2024-07-01",
      endDate: "2024-09-30",
      methodologyNotes: "Use Sentinel-1 SAR for cloud-penetrating flood detection. Compare pre/post-flood water extent."
    }
  },
  {
    name: "Sanctions Evasion — Bandar Abbas Port (Iran)",
    data: {
      objective: "Monitor vessel traffic and port loading activity at Bandar Abbas to detect potential sanctions-evasion ship-to-ship oil transfers in the Strait of Hormuz",
      latitude: "27.12",
      longitude: "56.27",
      startDate: "2023-01-01",
      endDate: "2024-12-01",
      methodologyNotes: "Use Sentinel-1 GRD IW mode VV polarization for vessel detection via constant false alarm rate (CFAR) thresholding on bright returns. Identify stationary vessel clusters in anchorage areas (potential STS transfers). Cross-reference with port berth change detection using Sentinel-2 RGB composites. Flag anomalous nighttime thermal signatures using VIIRS DNB for flaring activity."
    }
  },
  {
    name: "Poppy Cultivation Mapping (Helmand, Afghanistan)",
    data: {
      objective: "Map opium poppy cultivation extent and detect harvest timing in Helmand Province using crop phenology signatures",
      latitude: "31.35",
      longitude: "64.38",
      startDate: "2023-10-01",
      endDate: "2024-06-01",
      methodologyNotes: "Exploit poppy's distinctive NDVI phenology: rapid green-up December–February, peak NDVI March–April, sharp senescence by May. Use Sentinel-2 10-day composites to derive NDVI time-series per field parcel. Apply NDRE (Red-Edge Normalized Difference) using B05/B04 to differentiate poppy from wheat (similar NDVI but different red-edge response). Classify using temporal shape matching against known poppy calendar."
    }
  },
  {
    name: "Conflict Damage Assessment (Gaza Strip)",
    data: {
      objective: "Quantify building destruction and infrastructure damage in urban areas using SAR coherence loss and optical change detection",
      latitude: "31.35",
      longitude: "34.31",
      startDate: "2023-10-01",
      endDate: "2024-06-01",
      methodologyNotes: "Use Sentinel-1 interferometric coherence change detection: pre-event coherence minus post-event coherence highlights destroyed structures as decorrelation zones. Compute coherence from SLC pairs using COPERNICUS/S1_GRD. Validate with Sentinel-2 multitemporal RGB composites (B04, B03, B02) to visually confirm rubble signatures. Aggregate damage estimates by neighborhood grid cells (500m)."
    }
  },
  {
    name: "North Korea Crop Failure Early Warning",
    data: {
      objective: "Detect agricultural stress and potential food shortfall risk in North Korean farming regions using NDVI anomaly against multi-year baseline",
      latitude: "38.92",
      longitude: "125.73",
      startDate: "2022-04-01",
      endDate: "2024-10-01",
      methodologyNotes: "Use MODIS MOD13A2 16-day NDVI composites at 1km. Compute per-pixel NDVI anomaly against 2010–2021 climatological mean for each day-of-year. Focus on key agricultural provinces: South Hwanghae and North Hwanghae plains. Supplement with Landsat 8/9 to detect flooded paddy fields (NDWI > 0 in June) and drought stress (LST anomaly). Flag counties where growing-season cumulative NDVI falls >15% below baseline."
    }
  },
  {
    name: "Illegal Fishing Detection (West Africa EEZ)",
    data: {
      objective: "Detect dark vessel fishing activity in Guinean Exclusive Economic Zone using SAR vessel detection for vessels not broadcasting AIS",
      latitude: "10.42",
      longitude: "-15.58",
      startDate: "2023-01-01",
      endDate: "2024-12-01",
      methodologyNotes: "Apply CFAR vessel detection on Sentinel-1 IW GRD VV/VH imagery to produce vessel point detections. Filter by vessel size proxy (bright return area > 50m²) to exclude small coastal craft. Identify detections that fall within known industrial fishing grounds (>12nm from shore) without AIS transponder registration — the gap between SAR detections and AIS density heatmaps indicates dark vessels. Produce monthly density heatmaps of unregistered activity."
    }
  },
  {
    name: "Military Base Construction (South China Sea)",
    data: {
      objective: "Monitor artificial island expansion and military infrastructure build-up on Fiery Cross Reef using multitemporal change detection",
      latitude: "9.55",
      longitude: "114.23",
      startDate: "2020-01-01",
      endDate: "2024-12-01",
      methodologyNotes: "Use Sentinel-2 true-color and false-color composites (B8A, B04, B03) to map reclaimed land extent quarterly. Apply NDWI to extract precise shoreline and distinguish land from shallow reef. Use Sentinel-1 SAR to image through cloud cover for consistent monitoring. Compute area change in hectares per quarter. Flag new hard structures (hangars, radar installations) via texture analysis on high-backscatter SAR returns."
    }
  },
];


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
  const [chatMessages, setChatMessages] = useState<{ role: string; content: string }[]>([]);
  const [chatInput, setChatInput] = useState("");
  const [chatLoading, setChatLoading] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);
  const thoughtsEndRef = useRef<HTMLDivElement>(null);
  const chatEndRef = useRef<HTMLDivElement>(null);

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
          if (last && last.agent === data.agent && last.type !== "source" && last.type !== "tool_call") {
            const updatedLast = { ...last, content: last.content + data.content };
            return [...prev.slice(0, -1), updatedLast];
          } else {
            // Fallback if stream starts without a thought or agent switched
            return [...prev, { type: "thought", agent: data.agent, content: data.content, timestamp: data.timestamp }];
          }
        });
      } else if (data.type === "source") {
        // Grounding source with URL
        setThoughts((prev) => [...prev, {
          type: "source",
          agent: data.agent,
          content: `📎 ${data.title}`,
          title: data.title,
          uri: data.uri,
          timestamp: data.timestamp
        }]);
      } else if (data.type === "search_query") {
        // Google Search query used
        setThoughts((prev) => [...prev, {
          type: "search_query",
          agent: data.agent,
          content: `🔍 Searched: "${data.query}"`,
          query: data.query,
          timestamp: data.timestamp
        }]);
      } else if (data.type === "tool_call") {
        // Tool invocation
        setThoughts((prev) => [...prev, {
          type: "tool_call",
          agent: data.agent,
          content: `🔧 ${data.tool}${data.description ? `: ${data.description}` : ""}`,
          tool: data.tool,
          description: data.description,
          timestamp: data.timestamp
        }]);
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

  const [copiedCode, setCopiedCode] = useState(false);

  const copyCode = async () => {
    if (result?.code) {
      try {
        await navigator.clipboard.writeText(result.code);
        setCopiedCode(true);
        setTimeout(() => setCopiedCode(false), 2000);
      } catch (err) {
        console.error('Failed to copy:', err);
      }
    }
  };

  const resetToForm = () => {
    setViewState("form");
    setResult(null);
    setThoughts([]);
    setChatMessages([]);
  };

  // Auto-scroll chat messages
  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [chatMessages]);

  const handleChatSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!chatInput.trim() || chatLoading) return;

    const userMessage = chatInput.trim();
    setChatInput("");
    setChatMessages((prev) => [...prev, { role: "user", content: userMessage }]);
    setChatLoading(true);

    try {
      const response = await fetch("http://localhost:8000/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: userMessage }),
      });

      const data = await response.json();
      setChatMessages((prev) => [
        ...prev,
        { role: "assistant", content: data.content, code: data.code },
      ]);

      // If new code was generated, update result
      if (data.code) {
        setResult((prev) => ({ ...prev!, code: data.code }));
      }
    } catch (error) {
      setChatMessages((prev) => [
        ...prev,
        { role: "assistant", content: "Error communicating with the agent. Please try again." },
      ]);
    } finally {
      setChatLoading(false);
    }
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
                MCGEE
              </h1>
              <p className="text-xs text-slate-400">MULTIAGENT CODE-GENERATOR FOR GOOGLE EARTH ENGINE</p>
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

            {/* Preset Examples */}
            <div className="mb-6">
              <label className="text-sm font-medium text-slate-400 mb-2 block">Quick Examples</label>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
                {PRESET_EXAMPLES.map((example, i) => (
                  <button
                    key={i}
                    type="button"
                    onClick={() => setFormData(example.data)}
                    className="px-3 py-2 text-left bg-slate-800/50 hover:bg-slate-700/50 border border-slate-700/50 hover:border-cyan-600/50 rounded-lg text-sm text-slate-300 hover:text-cyan-300 transition-all"
                  >
                    <span className="font-medium block">{example.name}</span>
                    <span className="text-xs text-slate-500">{example.data.objective.slice(0, 60)}...</span>
                  </button>
                ))}
              </div>
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
                      className={`p-3 rounded-xl border animate-fadeIn ${thought.type === "source"
                        ? "bg-cyan-900/20 border-cyan-700/40"
                        : thought.type === "tool_call"
                          ? "bg-amber-900/20 border-amber-700/40"
                          : thought.type === "search_query"
                            ? "bg-purple-900/20 border-purple-700/40"
                            : thought.type === "thinking_step"
                              ? "bg-blue-900/20 border-blue-700/40"
                              : "bg-slate-800/50 border-slate-700/30"
                        }`}
                    >
                      <div className="flex items-center gap-2 mb-1">
                        <span className="text-lg">{getAgentIcon(thought.agent)}</span>
                        <span
                          className={`text-xs font-semibold uppercase tracking-wide ${getAgentColor(thought.agent)}`}
                        >
                          {thought.agent}
                        </span>
                        {thought.type && thought.type !== "thought" && (
                          <span className={`text-xs px-2 py-0.5 rounded-full ${thought.type === "source" ? "bg-cyan-800/50 text-cyan-300"
                            : thought.type === "tool_call" ? "bg-amber-800/50 text-amber-300"
                              : thought.type === "search_query" ? "bg-purple-800/50 text-purple-300"
                                : thought.type === "thinking_step" ? "bg-blue-800/50 text-blue-300"
                                  : "bg-slate-700/50 text-slate-300"
                            }`}>
                            {thought.type === "thinking_step" ? `step ${thought.step || ""}` : thought.type}
                          </span>
                        )}
                        <span className="text-xs text-slate-600">
                          {new Date(thought.timestamp).toLocaleTimeString()}
                        </span>
                      </div>
                      {thought.type === "source" && thought.uri ? (
                        <a
                          href={thought.uri}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="text-sm text-cyan-300 hover:text-cyan-200 hover:underline leading-relaxed"
                        >
                          {thought.content} ↗
                        </a>
                      ) : (
                        <p className="text-sm text-slate-300 leading-relaxed break-words whitespace-pre-wrap">
                          {thought.content}
                        </p>
                      )}
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
                <div className="p-6 space-y-4">
                  <h2 className="text-xl font-semibold text-slate-200 mb-4 flex items-center gap-2">
                    <span>📚</span> Research Methodology
                  </h2>

                  {/* Research Overview */}
                  <details open className="bg-slate-800/50 rounded-xl border border-slate-700/30 overflow-hidden">
                    <summary className="px-5 py-3 cursor-pointer hover:bg-slate-700/30 transition-colors font-medium text-slate-200 flex items-center gap-2">
                      <span>📋</span> Overview
                    </summary>
                    <div className="px-5 py-4 border-t border-slate-700/30">
                      <p className="text-slate-300 whitespace-pre-wrap leading-relaxed text-sm">
                        {result?.content || "No methodology available."}
                      </p>
                    </div>
                  </details>

                  {/* Research Queries */}
                  {(() => {
                    const searchQueries = thoughts.filter(t => t.type === "search_query");
                    if (searchQueries.length === 0) return null;
                    return (
                      <details className="bg-slate-800/50 rounded-xl border border-slate-700/30 overflow-hidden">
                        <summary className="px-5 py-3 cursor-pointer hover:bg-slate-700/30 transition-colors font-medium text-slate-200 flex items-center gap-2">
                          <span>🔍</span> Research Queries ({searchQueries.length})
                        </summary>
                        <div className="px-5 py-4 border-t border-slate-700/30 space-y-2">
                          {searchQueries.map((q, i) => (
                            <div key={i} className="flex items-start gap-2 p-2 bg-purple-900/20 rounded-lg border border-purple-700/30">
                              <span className="text-purple-400 text-xs mt-0.5">🔍</span>
                              <span className="text-sm text-slate-300">"{q.query || q.content.replace('🔍 Searched: "', '').replace('"', '')}"</span>
                            </div>
                          ))}
                        </div>
                      </details>
                    );
                  })()}

                  {/* Sources */}
                  {(() => {
                    const sources = thoughts.filter(t => t.type === "source");
                    if (sources.length === 0) return null;
                    return (
                      <details className="bg-slate-800/50 rounded-xl border border-slate-700/30 overflow-hidden">
                        <summary className="px-5 py-3 cursor-pointer hover:bg-slate-700/30 transition-colors font-medium text-slate-200 flex items-center gap-2">
                          <span>📎</span> Sources ({sources.length})
                        </summary>
                        <div className="px-5 py-4 border-t border-slate-700/30 space-y-2">
                          {sources.map((s, i) => (
                            <a
                              key={i}
                              href={s.uri}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="flex items-start gap-2 p-3 bg-cyan-900/20 rounded-lg border border-cyan-700/30 hover:bg-cyan-900/30 transition-colors group"
                            >
                              <span className="text-cyan-400 text-xs mt-0.5">📎</span>
                              <div className="flex-1 min-w-0">
                                <p className="text-sm text-cyan-300 group-hover:text-cyan-200 truncate">
                                  {s.title || s.content}
                                </p>
                                <p className="text-xs text-slate-500 truncate mt-0.5">{s.uri}</p>
                              </div>
                              <span className="text-cyan-400 text-xs">↗</span>
                            </a>
                          ))}
                        </div>
                      </details>
                    );
                  })()}

                  {/* Datasets */}
                  {result?.datasets && result.datasets.length > 0 && (
                    <details className="bg-slate-800/50 rounded-xl border border-slate-700/30 overflow-hidden">
                      <summary className="px-5 py-3 cursor-pointer hover:bg-slate-700/30 transition-colors font-medium text-slate-200 flex items-center gap-2">
                        <span>🛰️</span> Datasets Used ({result.datasets.length})
                      </summary>
                      <div className="px-5 py-4 border-t border-slate-700/30">
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
                          {result.datasets.map((ds, i) => (
                            <div key={i} className="px-3 py-2 bg-slate-900/50 text-slate-300 rounded-lg border border-slate-700/30 text-sm font-mono">
                              {ds}
                            </div>
                          ))}
                        </div>
                      </div>
                    </details>
                  )}

                  {/* Tools Used */}
                  {(() => {
                    const toolCalls = thoughts.filter(t => t.type === "tool_call");
                    if (toolCalls.length === 0) return null;
                    return (
                      <details className="bg-slate-800/50 rounded-xl border border-slate-700/30 overflow-hidden">
                        <summary className="px-5 py-3 cursor-pointer hover:bg-slate-700/30 transition-colors font-medium text-slate-200 flex items-center gap-2">
                          <span>🔧</span> Tools Used ({toolCalls.length})
                        </summary>
                        <div className="px-5 py-4 border-t border-slate-700/30 space-y-2">
                          {toolCalls.map((tc, i) => (
                            <div key={i} className="flex items-start gap-2 p-2 bg-amber-900/20 rounded-lg border border-amber-700/30">
                              <span className="text-amber-400 text-xs mt-0.5">🔧</span>
                              <div className="flex-1">
                                <p className="text-sm text-amber-300 font-medium">{tc.tool || "Unknown Tool"}</p>
                                {tc.description && (
                                  <p className="text-xs text-slate-400 mt-0.5">{tc.description}</p>
                                )}
                              </div>
                            </div>
                          ))}
                        </div>
                      </details>
                    );
                  })()}
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
                        {copiedCode ? (
                          <>
                            <span>✅</span>
                            <span>Copied!</span>
                          </>
                        ) : (
                          <>
                            <span>📋</span>
                            <span>Copy Code</span>
                          </>
                        )}
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
                          className={`p-4 rounded-xl border ${thought.type === "source"
                            ? "bg-cyan-900/20 border-cyan-700/40"
                            : thought.type === "tool_call"
                              ? "bg-amber-900/20 border-amber-700/40"
                              : thought.type === "search_query"
                                ? "bg-purple-900/20 border-purple-700/40"
                                : "bg-slate-800/50 border-slate-700/30"
                            }`}
                        >
                          <div className="flex items-center gap-2 mb-2">
                            <span className="text-lg">{getAgentIcon(thought.agent)}</span>
                            <span
                              className={`text-xs font-semibold uppercase tracking-wide ${getAgentColor(thought.agent)}`}
                            >
                              {thought.agent}
                            </span>
                            {thought.type && thought.type !== "thought" && (
                              <span className={`text-xs px-2 py-0.5 rounded-full ${thought.type === "source" ? "bg-cyan-800/50 text-cyan-300"
                                : thought.type === "tool_call" ? "bg-amber-800/50 text-amber-300"
                                  : thought.type === "search_query" ? "bg-purple-800/50 text-purple-300"
                                    : "bg-slate-700/50 text-slate-300"
                                }`}>
                                {thought.type}
                              </span>
                            )}
                            <span className="text-xs text-slate-600">
                              {new Date(thought.timestamp).toLocaleTimeString()}
                            </span>
                          </div>
                          {thought.type === "source" && thought.uri ? (
                            <a
                              href={thought.uri}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="text-sm text-cyan-300 hover:text-cyan-200 hover:underline"
                            >
                              {thought.content} ↗
                            </a>
                          ) : (
                            <p className="text-sm text-slate-300 break-words whitespace-pre-wrap leading-relaxed">{thought.content}</p>
                          )}
                        </div>
                      ))
                    )}
                  </div>
                </div>
              )}

              {activeTab === "chat" && (
                <div className="p-6 flex flex-col h-[70vh]">
                  <div className="mb-4">
                    <h2 className="text-xl font-semibold text-slate-200 flex items-center gap-2">
                      <span>💬</span> Refine & Chat
                    </h2>
                    <p className="text-sm text-slate-400 mt-1">
                      Ask questions, request modifications, or get help understanding the analysis
                    </p>
                  </div>

                  {/* Chat Messages */}
                  <div className="flex-1 overflow-y-auto space-y-4 mb-4 bg-slate-950/50 rounded-xl p-4 border border-slate-800/50">
                    {chatMessages.length === 0 ? (
                      <div className="h-full flex items-center justify-center">
                        <div className="text-center space-y-3">
                          <div className="text-5xl">💬</div>
                          <p className="text-slate-500">Start a conversation to refine your analysis</p>
                          <div className="text-sm text-slate-600 space-y-1">
                            <p>• Ask about methodology choices</p>
                            <p>• Request code modifications</p>
                            <p>• Get clarification on datasets</p>
                          </div>
                        </div>
                      </div>
                    ) : (
                      <>
                        {chatMessages.map((msg, i) => (
                          <div
                            key={i}
                            className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}
                          >
                            <div
                              className={`max-w-[80%] rounded-xl p-4 ${msg.role === "user"
                                ? "bg-gradient-to-br from-cyan-600 to-blue-600 text-white"
                                : "bg-slate-800/80 border border-slate-700/50"
                                }`}
                            >
                              <div className="flex items-center gap-2 mb-2">
                                <span className="text-sm font-semibold">
                                  {msg.role === "user" ? "You" : "🤖 Agent"}
                                </span>
                              </div>
                              <p className="text-sm leading-relaxed whitespace-pre-wrap">
                                {msg.content}
                              </p>
                              {(msg as any).code && (
                                <div className="mt-3 p-3 bg-slate-950 rounded-lg border border-slate-700/50">
                                  <div className="text-xs text-slate-400 mb-2 flex items-center justify-between">
                                    <span>Updated Code:</span>
                                    <button
                                      onClick={() => setActiveTab("code")}
                                      className="text-cyan-400 hover:text-cyan-300"
                                    >
                                      View Full →
                                    </button>
                                  </div>
                                  <pre className="text-xs text-slate-300 overflow-x-auto max-h-32">
                                    <code>{(msg as any).code.slice(0, 200)}...</code>
                                  </pre>
                                </div>
                              )}
                            </div>
                          </div>
                        ))}
                        <div ref={chatEndRef} />
                      </>
                    )}
                  </div>

                  {/* Chat Input */}
                  <form onSubmit={handleChatSubmit} className="flex gap-2">
                    <input
                      type="text"
                      value={chatInput}
                      onChange={(e) => setChatInput(e.target.value)}
                      placeholder="Ask a question or request modifications..."
                      disabled={chatLoading}
                      className="flex-1 bg-slate-900/80 border border-slate-700/50 rounded-xl px-4 py-3 text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-cyan-500/50 focus:border-cyan-500 transition-all disabled:opacity-50"
                    />
                    <button
                      type="submit"
                      disabled={!chatInput.trim() || chatLoading}
                      className="px-6 py-3 bg-gradient-to-r from-cyan-600 to-blue-600 hover:from-cyan-500 hover:to-blue-500 disabled:opacity-50 disabled:cursor-not-allowed rounded-xl font-semibold transition-all shadow-lg shadow-cyan-500/20"
                    >
                      {chatLoading ? "..." : "Send"}
                    </button>
                  </form>
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
