from typing import Annotated, List, TypedDict, Dict, Any
import datetime
import os
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages
from langchain_core.messages import HumanMessage, SystemMessage, BaseMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_community.tools.tavily_search import TavilySearchResults
from dotenv import load_dotenv

load_dotenv()

# --- Configuration ---
LLM_MODEL = "gemini-2.5-flash-lite"

llm = ChatGoogleGenerativeAI(
    model=LLM_MODEL,
    temperature=0.2,
    max_retries=2,
)

tavily_tool = TavilySearchResults(
    max_results=3,
    search_depth="advanced",
    include_answer=True,
    include_raw_content=True
)

# --- State Definition ---
class DebateState(TypedDict):
    messages: Annotated[List[BaseMessage], add_messages]
    market_data: Dict[str, Any]
    market_question: str
    verdict: str

# --- Agents ---

import logging

logger = logging.getLogger(__name__)

def statistics_expert(state: DebateState):
    """Analyzes market data (price, volume, etc)."""
    try:
        market_data = state.get("market_data", {})
        question = state.get("market_question", "Unknown Market")
        
        today = datetime.datetime.now().strftime("%Y-%m-%d")
        prompt = f"""
        You are a Statistics Expert for prediction markets.
        Today's date is: {today}
        
        Analyze the following market data and question: "{question}"
        
        Data: {market_data}
        
        Focus on:
        1. Current price and implied probability.
        2. Volume trends (if available).
        3. Calculate the Expected Value (EV) if possible or comment on the risk/reward ratio.
        
        Provide a quantitative assessment of whether to buy YES or NO shares, or if the market is efficient.
        """
        logger.info(f"Statistics Expert Prompt: {prompt[:100]}...")
        response = llm.invoke([HumanMessage(content=prompt)])
        return {"messages": [HumanMessage(content=f"**Statistics Expert**: {response.content}", name="Statistics Expert")]}
    except Exception as e:
        logger.error(f"Statistics Expert failed: {e}")
        return {"messages": [HumanMessage(content=f"**Statistics Expert**: (Failed to analyze) {e}", name="Statistics Expert")]}

def generalist_expert(state: DebateState):
    """Searches for recent news using Tavily."""
    try:
        question = state.get("market_question", "")
        if not question:
            return {"messages": [HumanMessage(content="**Generalist Expert**: No market question provided.", name="Generalist Expert")]}
        
        today = datetime.datetime.now().strftime("%Y-%m-%d")
        
        # Step 1: Brainstorm search queries
        query_prompt = f"""
        You are a smart News Researcher. 
        Today's date is: {today}
        
        To answer this prediction market: "{question}"
        Generate 3 distinct search queries to find the most relevant and up-to-date information.
        
        1. Query 1: The exact market terms.
        2. Query 2: Related entities, specific locations, or people involved (e.g. if it's about "Insurrection Act", search for "Minneapolis ICE shooting" or "troops deployment").
        3. Query 3: Broader context or recent breaking news affecting this topic.
        
        Output ONLY the 3 queries, one per line.
        """
        try:
             queries_response = llm.invoke([HumanMessage(content=query_prompt)])
             queries = [q.strip() for q in queries_response.content.split('\n') if q.strip()][:3]
             logger.info(f"Generated search queries: {queries}")
        except Exception as e:
             logger.warning(f"Failed to generate queries, falling back to default: {e}")
             queries = [f"latest news {question}"]

        # Step 2: Perform searches
        all_results = []
        for q in queries:
            try:
                res = tavily_tool.invoke(q)
                if isinstance(res, list):
                     all_results.extend(res)
                else:
                     all_results.append(str(res))
            except Exception as tool_err:
                logger.error(f"Tavily search failed for query '{q}': {tool_err}")

        # Simple deduplication
        unique_results = list(set([str(r) for r in all_results]))
        search_context = "\n\n".join(unique_results[:5]) 

        if not search_context:
            search_context = "No relevant search results found."

        # Step 3: Analyze
        prompt = f"""
        You are a Generalist Expert / News Analyst.
        Today's date is: {today}
        
        Your goal is to find the latest real-world events that impact this market: "{question}"
        
        You performed these searches: {queries}
        
        Search Results: 
        {search_context}
        
        Analyze how these recent news stories affect the likelihood of the event resolving YES or NO.
        Cite specific articles or events found (e.g. "According to reports on [Topic]...").
        """
        logger.info(f"Generalist Expert Prompt: {prompt[:100]}...")
        response = llm.invoke([HumanMessage(content=prompt)])
        return {"messages": [HumanMessage(content=f"**Generalist Expert**: {response.content}", name="Generalist Expert")]}
    except Exception as e:
        logger.error(f"Generalist Expert failed: {e}")
        return {"messages": [HumanMessage(content=f"**Generalist Expert**: (Failed to analyze) {e}", name="Generalist Expert")]}

def devils_advocate(state: DebateState):
    """Challenges the previous arguments."""
    try:
        messages = state.get("messages", [])
        question = state.get("market_question", "")
        
        # Extract previous arguments
        context = "\n".join([m.content for m in messages if isinstance(m, HumanMessage)])
        if not context:
            context = "No previous arguments provided."
        
        today = datetime.datetime.now().strftime("%Y-%m-%d")
        prompt = f"""
        You are the Devil's Advocate.
        Today's date is: {today}
        
        Your job is to challenge the consensus or finding logical fallacies in the arguments presented so far.
        
        Market: "{question}"
        Previous Arguments:
        {context}
        
        Identify risks, alternative interpretations, or missing data points. If everyone says YES, argue why NO might happen, and vice versa.
        """
        logger.info(f"Devil's Advocate Prompt: {prompt[:100]}...")
        response = llm.invoke([HumanMessage(content=prompt)])
        return {"messages": [HumanMessage(content=f"**Devil's Advocate**: {response.content}", name="Devil's Advocate")]}
    except Exception as e:
        logger.error(f"Devil's Advocate failed: {e}")
        return {"messages": [HumanMessage(content=f"**Devil's Advocate**: (Failed to analyze) {e}", name="Devil's Advocate")]}

def crypto_macro_analyst(state: DebateState):
    """Analyzes broader context."""
    try:
        question = state.get("market_question", "")
        
        today = datetime.datetime.now().strftime("%Y-%m-%d")
        prompt = f"""
        You are a Crypto and Macroeconomics Analyst.
        Today's date is: {today}
        
        Analyze the market "{question}" from a structural, macro, or crypto-native perspective.
        
        Does general market sentiment, crypto correlation, or macro events (Fed rates, elections, etc.) impact this?
        """
        logger.info(f"Crypto/Macro Analyst Prompt: {prompt[:100]}...")
        response = llm.invoke([HumanMessage(content=prompt)])
        return {"messages": [HumanMessage(content=f"**Crypto/Macro Analyst**: {response.content}", name="Crypto/Macro Analyst")]}
    except Exception as e:
        logger.error(f"Crypto/Macro Analyst failed: {e}")
        return {"messages": [HumanMessage(content=f"**Crypto/Macro Analyst**: (Failed to analyze) {e}", name="Crypto/Macro Analyst")]}

def moderator(state: DebateState):
    """Synthesizes the debate into a verdict."""
    try:
        messages = state.get("messages", [])
        question = state.get("market_question", "")
        
        context = "\n".join([str(m.content) for m in messages if isinstance(m, HumanMessage)])
        if not context:
            context = "No arguments presented."
        
        today = datetime.datetime.now().strftime("%Y-%m-%d")
        prompt = f"""
        You are the Moderator of the Debate Floor.
        Today's date is: {today}
        
        Review the arguments from the experts:
        
        {context}
        
        Market: "{question}"
        
        1. Summarize the key points for YES and NO.
        2. Weigh the evidence.
        3. Provide a Final Verdict: "Buy YES", "Buy NO", or "Stay Neutral".
        4. Provide a confidence score (0-100%).
        
        Format nicely with Markdown.
        """
        logger.info(f"Moderator Prompt: {prompt[:100]}...")
        response = llm.invoke([HumanMessage(content=prompt)])
        return {
            "messages": [HumanMessage(content=f"**Moderator**: {response.content}", name="Moderator")],
            "verdict": response.content
        }
    except Exception as e:
        logger.error(f"Moderator failed: {e}")
        return {
            "messages": [HumanMessage(content=f"**Moderator**: (Failed to reach verdict) {e}", name="Moderator")],
            "verdict": "Verdict generation failed."
        }

# --- Graph Construction ---

workflow = StateGraph(DebateState)

workflow.add_node("statistics_expert", statistics_expert)
workflow.add_node("generalist_expert", generalist_expert)
workflow.add_node("devils_advocate", devils_advocate)
workflow.add_node("crypto_macro_analyst", crypto_macro_analyst)
workflow.add_node("moderator", moderator)

# Parallel first round
workflow.set_entry_point("statistics_expert")
workflow.add_edge("statistics_expert", "generalist_expert")
workflow.add_edge("generalist_expert", "crypto_macro_analyst")
workflow.add_edge("crypto_macro_analyst", "devils_advocate") # Devil's advocate needs to see others' points
workflow.add_edge("devils_advocate", "moderator")
workflow.add_edge("moderator", END)

debate_app = workflow.compile()
