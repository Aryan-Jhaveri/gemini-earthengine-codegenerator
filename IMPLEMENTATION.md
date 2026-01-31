# MCGEE Implementation Status

## Current State (v0.1 - MVP)

A working multi-agent system that generates Earth Engine JavaScript code from natural language queries.

### ✅ What Works

| Feature | Status |
|---------|--------|
| 4-Agent Pipeline (Planner → Researcher → Coder → Synthesizer) | ✅ |
| Real-time thought streaming via WebSocket | ✅ |
| Gemini 3 Pro with Thinking Mode | ✅ |
| Google Search grounding (when model chooses to use it) | ✅ |
| EE dataset schema verification | ✅ |
| Source citation in methodology reports | ✅ |

---

## ⚠️ Known Limitations

### 1. Grounding is Optional
**Issue**: Cannot force Gemini to use Google Search. The `DynamicRetrievalConfig` API returns 400 errors.

**Workaround**: Prompt-based enforcement ("You MUST search the web..."). Works ~80% of the time.

### 2. Coder Agent Lacks Deep EE Context
**Issue**: The Coder relies on generic prompts + research context. No direct access to:
- Earth Engine JavaScript API documentation
- Official code examples from tutorials
- Dataset catalog example snippets

**Impact**: May generate code with incorrect band names, outdated methods, or suboptimal patterns.

### 3. No URL Context for Documentation
**Issue**: The SDK supports `types.UrlContext(urls=[...])` to read external pages, but it's not implemented for the Coder agent.

---

## 🚀 Next Steps

### Phase 1: URL Context for Coder Agent
Give the Coder agent direct access to EE documentation via `url_context`:

```python
# Proposed implementation
config = types.GenerateContentConfig(
    tools=[
        types.Tool(
            url_context=types.UrlContext(
                urls=[
                    "https://developers.google.com/earth-engine/datasets/catalog/COPERNICUS_S2_SR_HARMONIZED",
                    "https://developers.google.com/earth-engine/guides/image_visualization",
                ]
            )
        )
    ]
)
```

**Priority URLs**:
1. Dataset catalog pages (contain working code examples)
2. Guides: `image_visualization`, `ic_filtering`, `ic_reducing`
3. GitHub raw examples: `earthengine-api/javascript/src/examples/`

### Phase 2: Smart URL Selection
Build a function that selects relevant URLs based on task keywords:

```python
def get_example_urls(task: str, dataset_ids: list[str]) -> list[str]:
    # 1. Always include dataset catalog pages
    # 2. Add keyword-matched guides (ndvi → normalized_difference)
    # 3. Add GitHub examples for specific operations
    return urls[:15]  # Limit for performance
```

### Phase 3: Retry Logic for Grounding
When ResearcherAgent returns zero sources:
1. Log warning
2. Retry with stronger prompt
3. Fallback to URL context with known documentation URLs

---

## 📁 Key Files

| File | Purpose |
|------|---------|
| `agents/coder.py` | Code generation with Thinking Mode |
| `agents/researcher.py` | Web research with Google Search grounding |
| `agents/orchestrator.py` | Coordinates 4-agent pipeline |
| `agents/tools/ee_tools.py` | Dataset discovery + schema verification |
| `claude.md` | Internal AI assistant documentation |

---

## 🔗 Resources

- [Earth Engine API Docs](https://developers.google.com/earth-engine/apidocs)
- [Earth Engine Guides](https://developers.google.com/earth-engine/guides)
- [Dataset Catalog](https://developers.google.com/earth-engine/datasets)
- [GitHub Examples](https://github.com/google/earthengine-api/tree/master/javascript/src/examples)
- [Google GenAI SDK - URL Context](https://ai.google.dev/gemini-api/docs/url-context)
