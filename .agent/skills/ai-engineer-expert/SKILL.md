---
name: ai-engineer-expert
description: Expert in Agent Orchestration using LangChain, LangGraph, Tavily, and Gemini. Use this skill when the user wants to build, debug, or architect AI agents, specifically focusing on graph-based orchestration, web search integration, and cost-effective LLM usage with Gemini Flash Lite.
---

# AI Engineer Expert

This skill provides expert guidance for building AI agents using **LangChain** and **LangGraph**, with **Tavily** for search and **Gemini** for intelligence.

## Core Stack

-   **Orchestration**: `langgraph` (State management, cyclicity, persistence)
-   **Framework**: `langchain`, `langchain-google-genai`, `langchain-community`
-   **Tools**: `tavily-python` (Web search)
-   **LLM**: `gemini-2.5-flash-lite` (via Google Generative AI)

## Best Practices

### 1. LLM Configuration (Critical)

Always prioritize cost-efficiency by using the `gemini-2.5-flash-lite` model unless the user explicitly requests otherwise.

```python
from langchain_google_genai import ChatGoogleGenerativeAI

llm = ChatGoogleGenerativeAI(
    model="gemini-2.5-flash-lite",
    temperature=0,
    max_tokens=None,
    timeout=None,
    max_retries=2,
    # other params...
)
```

### 2. Tavily Search Tool Integration

Use the standard `TavilySearchResults` tool from community packages.

```python
from langchain_community.tools.tavily_search import TavilySearchResults

tool = TavilySearchResults(
    max_results=5,
    search_depth="advanced",
    include_answer=True,
    include_raw_content=True,
    include_images=False,
    # ...
)
```

### 3. LangGraph Architecture

Follow the standard `StateGraph` pattern. Always define a typed `State` using `TypedDict` or Pydantic (if needed for validation, though TypedDict is preferred for simple graphs).

#### Standard Graph Pattern

```python
from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode

class AgentState(TypedDict):
    messages: Annotated[List, add_messages]

def agent_node(state: AgentState):
    # invokation logic
    pass

workflow = StateGraph(AgentState)
workflow.add_node("agent", agent_node)
workflow.add_node("tools", ToolNode([tool]))

workflow.set_entry_point("agent")
workflow.add_conditional_edges("agent", should_continue)
workflow.add_edge("tools", "agent")

app = workflow.compile()
```

### 4. General Engineering

-   **Type Hinting**: Use strict type hints for all node functions.
-   **Async Support**: Prefer `async` functions for IO-bound graph nodes.
-   **Environment Variables**: Ensure `GOOGLE_API_KEY` and `TAVILY_API_KEY` are present in `.env`.

## when to use

Use this skill for:
1.  Setting up new agent projects.
2.  Refactoring existing chains into graphs.
3.  Optimizing agent costs by switching to Flash Lite.
4.  Debugging LangGraph state or routing issues.
