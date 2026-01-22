"""
Researcher Agent

Uses Gemini Deep Research + Google Search grounding to:
1. Research methodologies for geospatial analysis tasks
2. Discover relevant Earth Engine datasets
3. Gather context requirements for the Coder agent
4. Answer questions from Coder agent autonomously
"""

import google.generativeai as genai
from google.generativeai import types
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
        genai.configure(api_key=self.api_key)
        
        # Model for Deep Research (asynchronous, comprehensive)
        self.deep_research_model = "gemini-3-pro"
        
        # Model for quick responses
        self.quick_model = "gemini-3-pro"
        
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
        self._stream_thought(f"Searching for datasets related to: {query}")
        
        results = {
            "datasets": [],
            "schemas": {},
            "previews": {}
        }
        
        # Browse for relevant datasets
        datasets = browse_datasets(query)
        results["datasets"] = datasets
        self._stream_thought(f"Found {len(datasets)} relevant datasets")
        
        # Get schema for top datasets
        for ds in datasets[:3]:
            dataset_id = ds["id"]
            self._stream_thought(f"Getting schema for {dataset_id}")
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
        self._stream_thought(f"Starting research: {query}")
        
        # First, gather EE tool data
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
        
        self._stream_thought("Consulting Gemini for methodology research...")
        
        try:
            if use_deep_research:
                # Use Deep Research for comprehensive analysis
                self._stream_thought("Using Deep Research mode (this may take a few minutes)...")
                
                client = genai.Client(api_key=self.api_key)
                config = types.GenerateContentConfig(
                    tools=[types.Tool(google_search=types.GoogleSearch())],
                    response_modalities=["TEXT"]
                )
                
                response = await client.aio.models.generate_content(
                    model=self.deep_research_model,
                    contents=research_prompt,
                    config=config
                )
                
                research_result = response.text
            else:
                # Use quick model with search grounding
                model = genai.GenerativeModel(
                    model_name=self.quick_model,
                    system_instruction=self.system_prompt
                )
                response = model.generate_content(research_prompt)
                research_result = response.text
            
            self._stream_thought("Research complete!")
            
            # Store in shared memory
            shared_memory.set_research_context("latest_research", {
                "query": query,
                "result": research_result,
                "ee_data": ee_data
            })
            
            return {
                "query": query,
                "research": research_result,
                "datasets": ee_data["datasets"],
                "schemas": ee_data["schemas"]
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
        
        model = genai.GenerativeModel(
            model_name=self.quick_model,
            system_instruction=self.system_prompt
        )
        response = model.generate_content(prompt)
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
