"""Debate Floor API routes for AI-powered market analysis."""

import json
import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional

from src.backend.database import get_db
from src.backend.models import Market
from src.backend.agents.debate import build_debate_graph, DebateState, AgentConfig
from src.backend.routes.markets import fetch_price_history_from_clob
from langchain_core.messages import BaseMessage, HumanMessage

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/debate", tags=["debate"])


class AgentConfigRequest(BaseModel):
    """Request model for agent configuration."""
    statistics_expert: bool = Field(default=True, description="Enable Statistics Expert agent")
    generalist_expert: bool = Field(default=True, description="Enable Generalist Expert (News Analyst) agent")
    devils_advocate: bool = Field(default=True, description="Enable Devil's Advocate agent")
    crypto_macro_analyst: bool = Field(default=True, description="Enable Crypto/Macro Analyst agent")
    time_decay_analyst: bool = Field(default=True, description="Enable Time Decay & Resolution Analyst agent")


class DebateRequest(BaseModel):
    """Request model for initiating a debate."""
    agents: Optional[AgentConfigRequest] = Field(
        default=None,
        description="Configuration for which agents to include. If not provided, all agents are enabled."
    )


class DebateResponse(BaseModel):
    """Response model for debate results."""
    market_id: str
    messages: List[Dict[str, str]]
    verdict: str
    enabled_agents: List[str]


@router.post("/{market_id}", response_model=DebateResponse)
async def initiate_debate(
    market_id: str,
    request: Optional[DebateRequest] = None,
    db: AsyncSession = Depends(get_db)
) -> DebateResponse:
    """
    Initiates an AI debate for a specific market.
    
    Users can optionally specify which agents to include in the debate
    to reduce token usage and processing time.
    """
    # 1. Fetch Market Data
    result = await db.execute(select(Market).where(Market.id == market_id))
    market = result.scalar_one_or_none()
    
    if not market:
        result = await db.execute(select(Market).where(Market.slug == market_id))
        market = result.scalar_one_or_none()
        
    if not market:
        raise HTTPException(status_code=404, detail="Market not found")
    
    # 2. Fetch Price History for Statistics Expert
    price_history_24h: List[float] = []
    price_history_7d: List[float] = []
    
    if market.clob_token_ids:
        try:
            token_ids = json.loads(market.clob_token_ids)
            if token_ids and len(token_ids) > 0:
                yes_token_id = token_ids[0]
                
                # Fetch 24h history (15-min fidelity)
                history_24h = await fetch_price_history_from_clob(yes_token_id, "1d", 15)
                if history_24h:
                    price_history_24h = [h["p"] * 100 for h in history_24h]  # Convert to 0-100 scale
                
                # Fetch 7d history (1-hour fidelity)
                history_7d = await fetch_price_history_from_clob(yes_token_id, "7d", 60)
                if history_7d:
                    price_history_7d = [h["p"] * 100 for h in history_7d]  # Convert to 0-100 scale
                    
                logger.info(f"Fetched price history: 24h={len(price_history_24h)} points, 7d={len(price_history_7d)} points")
        except Exception as e:
            logger.warning(f"Failed to fetch price history for debate: {e}")
    
    # 3. Prepare Data for Agents
    market_data = {
        "title": market.title,
        "price": market.yes_percentage,
        "volume_24h": market.volume_24h,
        "volume_7d": market.volume_7d,
        "liquidity": market.liquidity,
        "end_date": str(market.end_date)
    }
    
    initial_state: DebateState = {
        "messages": [],
        "market_data": market_data,
        "market_question": market.title,
        "verdict": "",
        "price_history_24h": price_history_24h,
        "price_history_7d": price_history_7d
    }
    
    # 3. Build Agent Config from Request
    agent_config: AgentConfig = {
        "statistics_expert": True,
        "generalist_expert": True,
        "devils_advocate": True,
        "crypto_macro_analyst": True,
        "time_decay_analyst": True,
    }
    
    if request and request.agents:
        agent_config = {
            "statistics_expert": request.agents.statistics_expert,
            "generalist_expert": request.agents.generalist_expert,
            "devils_advocate": request.agents.devils_advocate,
            "crypto_macro_analyst": request.agents.crypto_macro_analyst,
            "time_decay_analyst": request.agents.time_decay_analyst,
        }
    
    # Track enabled agents for response
    enabled_agents = [k for k, v in agent_config.items() if v]
    
    # 4. Build Dynamic Graph and Run
    try:
        debate_graph = build_debate_graph(agent_config)
        final_state = await debate_graph.ainvoke(initial_state)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Debate failed: {str(e)}")
    
    # 5. Format Output
    formatted_messages = []
    for msg in final_state["messages"]:
        if isinstance(msg, HumanMessage) and msg.name:
            formatted_messages.append({
                "agent": msg.name,
                "content": str(msg.content)
            })
            
    return DebateResponse(
        market_id=market_id,
        messages=formatted_messages,
        verdict=final_state.get("verdict", "No verdict reached."),
        enabled_agents=enabled_agents
    )
