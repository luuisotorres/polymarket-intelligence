from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from typing import List, Dict, Any

from src.backend.database import get_db
from src.backend.models import Market
from src.backend.agents.debate import debate_app, DebateState
from langchain_core.messages import BaseMessage, HumanMessage

router = APIRouter(prefix="/api/debate", tags=["debate"])

class DebateResponse(BaseModel):
    market_id: str
    messages: List[Dict[str, str]]
    verdict: str

@router.post("/{market_id}", response_model=DebateResponse)
async def initiate_debate(
    market_id: str,
    db: AsyncSession = Depends(get_db)
) -> DebateResponse:
    """
    Initiates an AI debate for a specific market.
    """
    # 1. Fetch Market Data
    result = await db.execute(select(Market).where(Market.id == market_id))
    market = result.scalar_one_or_none()
    
    if not market:
        result = await db.execute(select(Market).where(Market.slug == market_id))
        market = result.scalar_one_or_none()
        
    if not market:
        # Note: We could fallback to API here like in markets.py, but for simplicity
        # let's assume the market exists in DB (or user visited the page already)
        raise HTTPException(status_code=404, detail="Market not found")
    
    # 2. Prepare Data for Agents
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
        "verdict": ""
    }
    
    # 3. Run Agent Workflow
    # Note: invoke is synchronous, for async we'd use ainvoke but LangGraph's async support 
    # might depend on the runner. For now, running in threadpool via FastAPI's default behavior 
    # (since this function is async, we should use ainvoke if possible or run in executor).
    # Since debate_app.compile() returns a Runnable, we can use ainvoke.
    
    try:
        final_state = await debate_app.ainvoke(initial_state)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Debate failed: {str(e)}")
    
    # 4. Format Output
    formatted_messages = []
    for msg in final_state["messages"]:
        if isinstance(msg, HumanMessage) and msg.name:
            # We filter for the named agent messages
            formatted_messages.append({
                "agent": msg.name,
                "content": str(msg.content)
            })
            
    return DebateResponse(
        market_id=market_id,
        messages=formatted_messages,
        verdict=final_state.get("verdict", "No verdict reached.")
    )
