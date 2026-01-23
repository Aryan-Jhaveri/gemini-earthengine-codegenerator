"""
Researcher Agent

Uses Gemini Deep Research + Google Search grounding to:
1. Research methodologies for geospatial analysis tasks
2. Discover relevant Earth Engine datasets
3. Gather context requirements for the Coder agent
4. Answer questions from Coder agent autonomously
"""

from google import genai
from google.genai import types
from typing import Optional
import os

from .memory import shared_memory, AgentType, MessageType
from .tools.ee_tools import browse_datasets, get_asset_metadata, get_band_schema, get_dataset_docs


class ResearcherAgent:
    """
    Researcher Agent with Deep Research and EE Tools.
    
    Capabilities:
    - Deep Research for multi-step web research
    - Google Search grounding for real-time information
    - Earth Engine tools for dataset discovery
    - Autonomous response to Coder questions
    """
    
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("GOOGLE_API_KEY")
        # genai.configure(api_key=self.api_key) # Deprecated in favor of Client(api_key=...)
        
        # Model for Deep Research (asynchronous, comprehensive)
        self.deep_research_model = "gemini-3-pro-preview"
        
        # Model for quick responses
        self.quick_model = "gemini-3-pro-preview"
        
        self.system_prompt = """You are a Geospatial Research Agent specialized in Google Earth Engine analysis.

Your responsibilities:
1. Research the best methodologies for geospatial analysis tasks
2. Recommend appropriate Earth Engine datasets
3. Identify required preprocessing steps
4. Provide context that the Coder agent needs to generate scripts

When researching, consider:
- Satellite data sources (Landsat, Sentinel, MODIS, etc.)
- Temporal requirements (date ranges, revisit times)
- Spatial resolution needs
- Processing algorithms (indices, classifications, change detection)
- Cloud masking and quality filtering requirements

Always provide structured output with:
- Recommended datasets with exact Earth Engine IDs
- Required bands and their names
- Preprocessing steps
- Analysis methodology
- Output format requirements"""

    def _stream_thought(self, content: str) -> None:
        """Stream a thought to shared memory."""
        shared_memory.add_thought(AgentType.RESEARCHER, content)
    
    def _use_ee_tools(self, query: str) -> dict:
        """Use Earth Engine tools to gather dataset information."""
        shared_memory.add_tool_call(AgentType.RESEARCHER, "browse_datasets", query[:50])
        
        results = {
            "datasets": [],
            "schemas": {},
            "previews": {}
        }
        
        # Browse for relevant datasets
        datasets = browse_datasets(query)
        results["datasets"] = datasets
        self._stream_thought(f"📂 Found {len(datasets)} relevant datasets")
        
        # Get schema for top datasets
        for ds in datasets[:3]:
            dataset_id = ds["id"]
            shared_memory.add_tool_call(AgentType.RESEARCHER, "get_band_schema", dataset_id)
            schema = get_band_schema(dataset_id)
            if "error" not in schema:
                results["schemas"][dataset_id] = schema
        
        return results
    
    async def research(self, query: str, use_deep_research: bool = False) -> dict:
        """
        Conduct research on a geospatial analysis topic.
        
        Args:
            query: The research query
            use_deep_research: If True, use Deep Research (slower but comprehensive)
        
        Returns:
            Research results dict
        """
        self._stream_thought("🔬 Research Phase [1/5]: Initializing...")
        self._stream_thought(f"Query: {query}")
        
        # First, gather EE tool data
        self._stream_thought("📂 Research Phase [2/5]: Gathering Earth Engine datasets...")
        ee_data = self._use_ee_tools(query)
        
        # Build context from EE tools
        tool_context = f"""
Earth Engine Data Available:
Datasets Found: {[d['name'] for d in ee_data['datasets']]}
Dataset IDs: {[d['id'] for d in ee_data['datasets']]}

Band Schemas:
{ee_data['schemas']}
"""
        
        # Research prompt
        research_prompt = f"""
Research Task: {query}

{tool_context}

Provide a comprehensive research report including:
1. Recommended methodology
2. Best datasets to use (with exact Earth Engine IDs)
3. Required preprocessing steps
4. Band names to use for analysis
5. Any important considerations

Format as structured JSON.
"""
        
        self._stream_thought("🌐 Research Phase [3/5]: Researching methodology online with Google Search grounding...")
        self._stream_thought("⏳ Streaming research with Thinking Mode enabled...")
        
        try:
            client = genai.Client(api_key=self.api_key)
            
            # Config with Google Search grounding + Thinking Mode
            config = types.GenerateContentConfig(
                tools=[types.Tool(google_search=types.GoogleSearch())],
                thinking_config=types.ThinkingConfig(
                    include_thoughts=True,
                    thinking_budget=2048
                )
            )
            
            model_to_use = self.deep_research_model if use_deep_research else self.quick_model
            
            if use_deep_research:
                self._stream_thought("Using Deep Research mode (this may take a few minutes)...")
            
            self._stream_thought("💭 Thinking Process Started...")
            
            # Use sync streaming wrapped in thread to not block event loop
            import asyncio
            
            def run_streaming():
                """Run sync streaming in a thread."""
                research_result = ""
                thought_count = 0
                full_response = None
                
                response_stream = client.models.generate_content_stream(
                    model=model_to_use,
                    contents=research_prompt,
                    config=config
                )
                
                for chunk in response_stream:
                    full_response = chunk
                    
                    if hasattr(chunk, 'candidates') and chunk.candidates:
                        for candidate in chunk.candidates:
                            if hasattr(candidate, 'content') and candidate.content:
                                for part in candidate.content.parts:
                                    if hasattr(part, 'thought') and part.thought:
                                        thought_count += 1
                                        thought_preview = part.text[:200] + "..." if len(part.text) > 200 else part.text
                                        self._stream_thought(f"💭 [{thought_count}] {thought_preview}")
                                    elif hasattr(part, 'text') and part.text:
                                        research_result += part.text
                    elif chunk.text:
                        research_result += chunk.text
                
                return research_result, thought_count, full_response
            
            # Run in thread to avoid blocking event loop
            research_result, thought_count, full_response = await asyncio.to_thread(run_streaming)
            
            if thought_count > 0:
                self._stream_thought(f"✅ Completed {thought_count} thinking steps")
            
            # Token counting
            try:
                count_resp = client.models.count_tokens(
                    model=model_to_use,
                    contents=research_prompt
                )
                self._stream_thought(f"📊 Token Analysis - Input Token Count: {count_resp.total_tokens}")
            except Exception as tok_err:
                print(f"Token count error: {tok_err}")
            
            # Extract and stream grounding metadata (sources)
            self._stream_thought("📎 Research Phase [4/5]: Extracting sources and citations...")
            sources = []
            search_queries = []
            
            # Try to get grounding metadata from the final response
            if full_response and full_response.candidates and full_response.candidates[0].grounding_metadata:
                gm = full_response.candidates[0].grounding_metadata
                
                # Stream search queries that were used
                if hasattr(gm, 'web_search_queries') and gm.web_search_queries:
                    for q in gm.web_search_queries:
                        search_queries.append(q)
                        shared_memory.add_search_query(AgentType.RESEARCHER, q)
                
                # Stream grounding sources with URLs
                if gm.grounding_chunks:
                    for chunk in gm.grounding_chunks:
                        if chunk.web:
                            source_info = {
                                "title": chunk.web.title,
                                "uri": chunk.web.uri
                            }
                            sources.append(source_info)
                            shared_memory.add_source(
                                AgentType.RESEARCHER,
                                chunk.web.title,
                                chunk.web.uri
                            )
            
            # Append sources to the report if found
            if sources:
                source_text = "\n\n**Sources:**\n" + "\n".join([
                    f"- [{s['title']}]({s['uri']})" for s in sources
                ])
                research_result += source_text
                self._stream_thought(f"✅ Found {len(sources)} grounded sources")
            
            self._stream_thought("✅ Research Phase [5/5]: Complete! Methodology and sources ready.")
            
            # Store in shared memory
            shared_memory.set_research_context("latest_research", {
                "query": query,
                "result": research_result,
                "ee_data": ee_data,
                "sources": sources,
                "search_queries": search_queries
            })
            
            return {
                "query": query,
                "research": research_result,
                "datasets": ee_data["datasets"],
                "schemas": ee_data["schemas"],
                "sources": sources,
                "search_queries": search_queries
            }
            
        except Exception as e:
            error_msg = f"Research error: {str(e)}"
            self._stream_thought(error_msg)
            return {"error": error_msg, "ee_data": ee_data}
    
    async def answer_question(self, question: str, from_agent: AgentType) -> str:
        """
        Answer a question from another agent.
        
        Args:
            question: The question to answer
            from_agent: Which agent is asking
        
        Returns:
            Answer string
        """
        self._stream_thought(f"Received question from {from_agent.value}: {question}")
        
        # Record the question
        shared_memory.add_agent_message(
            from_agent=from_agent,
            to_agent=AgentType.RESEARCHER,
            message_type=MessageType.QUESTION,
            content=question
        )
        
        # Get any relevant context from memory
        context = shared_memory.get_full_context()
        research_context = context.get("research_context", {})
        
        # Check if this is an EE-related question
        ee_keywords = ["band", "dataset", "collection", "schema", "sentinel", "landsat", "modis"]
        is_ee_question = any(kw in question.lower() for kw in ee_keywords)
        
        if is_ee_question:
            self._stream_thought("This is an Earth Engine question, using tools...")
            ee_data = self._use_ee_tools(question)
            tool_context = f"EE Data: {ee_data}"
        else:
            tool_context = ""
        
        # Build answer prompt
        prompt = f"""
Question from {from_agent.value} agent: {question}

Previous Research Context:
{research_context}

{tool_context}

Provide a clear, helpful answer that the Coder agent can use.
"""
        
        client = genai.Client(api_key=self.api_key)
        response = client.models.generate_content(
            model=self.quick_model,
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction=self.system_prompt
            )
        )
        answer = response.text
        
        self._stream_thought(f"Answering: {answer[:100]}...")
        
        # Record the answer
        shared_memory.add_agent_message(
            from_agent=AgentType.RESEARCHER,
            to_agent=from_agent,
            message_type=MessageType.ANSWER,
            content=answer
        )
        
        return answer
    
    def check_pending_questions(self) -> list:
        """Check for unanswered questions directed at this agent."""
        return shared_memory.get_pending_questions(AgentType.RESEARCHER)


# Singleton instance
researcher_agent = ResearcherAgent()
