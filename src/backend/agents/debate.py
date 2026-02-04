"""Debate Floor Agent System - Multi-agent debate for market analysis."""

from typing import Annotated, List, TypedDict, Dict, Any, Optional
import datetime
import os
import math
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages
from langchain_core.messages import HumanMessage, SystemMessage, BaseMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_community.tools.tavily_search import TavilySearchResults
from dotenv import load_dotenv

load_dotenv()


# --- Agent Configuration ---
class AgentConfig(TypedDict):
    """Configuration for which agents to include in the debate."""
    statistics_expert: bool
    generalist_expert: bool
    devils_advocate: bool
    crypto_macro_analyst: bool
    time_decay_analyst: bool
    top_traders_analyst: bool


DEFAULT_AGENT_CONFIG: AgentConfig = {
    "statistics_expert": True,
    "generalist_expert": True,
    "devils_advocate": True,
    "crypto_macro_analyst": True,
    "time_decay_analyst": True,
    "top_traders_analyst": True,
}

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


# --- Statistics Calculation Tools ---

def calculate_expected_value(yes_price: float, estimated_prob: float) -> Dict[str, Any]:
    """
    Calculate Expected Value for YES and NO bets.
    
    Args:
        yes_price: Current market price (0-100 scale)
        estimated_prob: Your estimated probability of YES (0-100 scale)
    
    Returns:
        Dict with EV calculations and recommendation
    """
    # Normalize to 0-1 scale
    price = yes_price / 100
    prob = estimated_prob / 100
    
    # EV = (Probability of Win * Profit) - (Probability of Loss * Loss)
    # For YES bet: Win pays (1-price)/price, lose pays 1
    yes_profit = (1 - price) / price if price > 0 else 0
    yes_ev = (prob * yes_profit) - ((1 - prob) * 1)
    
    # For NO bet at (1 - price)
    no_price = 1 - price
    no_profit = (1 - no_price) / no_price if no_price > 0 else 0
    no_ev = ((1 - prob) * no_profit) - (prob * 1)
    
    # Determine recommendation
    if yes_ev > 0.05:
        recommendation = "BUY YES (+EV)"
    elif no_ev > 0.05:
        recommendation = "BUY NO (+EV)"
    elif yes_ev > 0:
        recommendation = "Slight YES edge"
    elif no_ev > 0:
        recommendation = "Slight NO edge"
    else:
        recommendation = "Market is fairly priced"
    
    return {
        "yes_ev": round(yes_ev * 100, 2),  # As percentage return
        "no_ev": round(no_ev * 100, 2),
        "edge": round(abs(yes_price - estimated_prob), 2),
        "recommendation": recommendation
    }


def calculate_implied_probability(yes_price: float) -> Dict[str, Any]:
    """
    Extract market-implied probabilities and vig.
    
    Args:
        yes_price: Current YES price (0-100 scale)
    
    Returns:
        Dict with implied probabilities and market efficiency metrics
    """
    yes_prob = yes_price / 100
    no_prob = (100 - yes_price) / 100
    
    # Vig calculation (overround)
    total = yes_prob + no_prob  # Should be exactly 1 in efficient market
    vig = (total - 1) * 100  # Usually 0 on Polymarket (no fee on share prices)
    
    # True probabilities adjusted for vig
    true_yes = yes_prob / total if total > 0 else 0.5
    true_no = no_prob / total if total > 0 else 0.5
    
    return {
        "implied_yes_prob": round(yes_price, 2),
        "implied_no_prob": round(100 - yes_price, 2),
        "vig_percentage": round(vig, 3),
        "breakeven_yes": round(yes_price, 2),  # Need this % to break even on YES
        "breakeven_no": round(100 - yes_price, 2)  # Need this % to break even on NO
    }


def calculate_kelly_criterion(yes_price: float, estimated_prob: float) -> Dict[str, Any]:
    """
    Calculate Kelly Criterion for optimal bet sizing.
    
    Args:
        yes_price: Current market price (0-100 scale)
        estimated_prob: Your estimated probability (0-100 scale)
    
    Returns:
        Dict with Kelly fractions and recommendations
    """
    price = yes_price / 100
    prob = estimated_prob / 100
    
    # Kelly formula: f* = (bp - q) / b
    # where b = odds (profit per unit bet), p = win probability, q = 1 - p
    
    # For YES bet
    if price > 0 and price < 1:
        b_yes = (1 - price) / price  # Odds for YES
        kelly_yes = (b_yes * prob - (1 - prob)) / b_yes if b_yes > 0 else 0
    else:
        kelly_yes = 0
    
    # For NO bet
    no_price = 1 - price
    if no_price > 0 and no_price < 1:
        b_no = (1 - no_price) / no_price  # Odds for NO
        kelly_no = (b_no * (1 - prob) - prob) / b_no if b_no > 0 else 0
    else:
        kelly_no = 0
    
    # Determine optimal side
    if kelly_yes > kelly_no and kelly_yes > 0:
        optimal_kelly = kelly_yes
        optimal_side = "YES"
    elif kelly_no > 0:
        optimal_kelly = kelly_no
        optimal_side = "NO"
    else:
        optimal_kelly = 0
        optimal_side = "NONE"
    
    # Clamp between 0 and 1
    optimal_kelly = max(0, min(1, optimal_kelly))
    
    return {
        "full_kelly": round(optimal_kelly * 100, 2),
        "half_kelly": round(optimal_kelly * 50, 2),
        "quarter_kelly": round(optimal_kelly * 25, 2),
        "optimal_side": optimal_side,
        "recommendation": f"Bet {round(optimal_kelly * 25, 1)}%-{round(optimal_kelly * 50, 1)}% of bankroll on {optimal_side}" if optimal_kelly > 0.01 else "No bet recommended (no edge)"
    }


def analyze_price_volatility(prices: List[float]) -> Dict[str, Any]:
    """
    Compute volatility metrics from price history.
    
    Args:
        prices: List of historical prices (0-100 scale)
    
    Returns:
        Dict with volatility metrics and regime classification
    """
    if not prices or len(prices) < 2:
        return {
            "std_dev": 0,
            "mean": 50,
            "coefficient_of_variation": 0,
            "volatility_regime": "Unknown (insufficient data)",
            "range": 0
        }
    
    n = len(prices)
    mean = sum(prices) / n
    variance = sum((p - mean) ** 2 for p in prices) / n
    std_dev = math.sqrt(variance)
    
    cv = (std_dev / mean * 100) if mean > 0 else 0
    price_range = max(prices) - min(prices)
    
    # Classify volatility regime
    if std_dev < 2:
        regime = "Low volatility (stable)"
    elif std_dev < 5:
        regime = "Moderate volatility"
    elif std_dev < 10:
        regime = "High volatility"
    else:
        regime = "Extreme volatility"
    
    return {
        "std_dev": round(std_dev, 2),
        "mean": round(mean, 2),
        "coefficient_of_variation": round(cv, 2),
        "volatility_regime": regime,
        "range": round(price_range, 2),
        "high": round(max(prices), 2),
        "low": round(min(prices), 2)
    }


def calculate_momentum_indicators(prices: List[float]) -> Dict[str, Any]:
    """
    Calculate momentum indicators (SMA, EMA, trend signals).
    
    Args:
        prices: List of historical prices (oldest to newest)
    
    Returns:
        Dict with momentum indicators and signals
    """
    if not prices or len(prices) < 3:
        return {
            "sma_short": None,
            "sma_long": None,
            "ema": None,
            "current_price": prices[-1] if prices else 0,
            "trend_signal": "Insufficient data"
        }
    
    current = prices[-1]
    
    # Short-term SMA (last 1/4 of data or min 3 points)
    short_period = max(3, len(prices) // 4)
    sma_short = sum(prices[-short_period:]) / short_period
    
    # Long-term SMA (full data)
    sma_long = sum(prices) / len(prices)
    
    # EMA calculation (smoothing factor = 2 / (period + 1))
    ema_period = min(10, len(prices))
    alpha = 2 / (ema_period + 1)
    ema = prices[-ema_period]
    for p in prices[-ema_period + 1:]:
        ema = alpha * p + (1 - alpha) * ema
    
    # Determine trend signal
    if current > sma_short > sma_long:
        trend = "Strong Bullish (price > short SMA > long SMA)"
    elif current > sma_short:
        trend = "Bullish (price above short-term average)"
    elif current < sma_short < sma_long:
        trend = "Strong Bearish (price < short SMA < long SMA)"
    elif current < sma_short:
        trend = "Bearish (price below short-term average)"
    else:
        trend = "Neutral (consolidating)"
    
    # Momentum (rate of change)
    if len(prices) >= 5:
        roc = ((current - prices[-5]) / prices[-5] * 100) if prices[-5] > 0 else 0
    else:
        roc = 0
    
    return {
        "current_price": round(current, 2),
        "sma_short": round(sma_short, 2),
        "sma_long": round(sma_long, 2),
        "ema": round(ema, 2),
        "rate_of_change": round(roc, 2),
        "trend_signal": trend
    }


def compute_support_resistance(prices: List[float]) -> Dict[str, Any]:
    """
    Identify support and resistance levels from price data.
    
    Args:
        prices: List of historical prices
    
    Returns:
        Dict with support/resistance levels and current position
    """
    if not prices or len(prices) < 5:
        return {
            "support": None,
            "resistance": None,
            "current_position": "Insufficient data"
        }
    
    current = prices[-1]
    low = min(prices)
    high = max(prices)
    
    # Simple support/resistance based on percentile clustering
    sorted_prices = sorted(prices)
    n = len(sorted_prices)
    
    # Support: 20th percentile
    support_idx = int(n * 0.2)
    support = sorted_prices[support_idx]
    
    # Resistance: 80th percentile
    resistance_idx = int(n * 0.8)
    resistance = sorted_prices[resistance_idx]
    
    # Position analysis
    range_size = resistance - support if resistance > support else 1
    position_pct = (current - support) / range_size * 100
    
    if current <= support * 1.02:  # Within 2% of support
        position = f"At support ({support:.1f}%) - potential bounce zone"
    elif current >= resistance * 0.98:  # Within 2% of resistance
        position = f"At resistance ({resistance:.1f}%) - potential rejection zone"
    elif position_pct > 70:
        position = f"Upper range ({position_pct:.0f}%) - approaching resistance"
    elif position_pct < 30:
        position = f"Lower range ({position_pct:.0f}%) - approaching support"
    else:
        position = f"Mid-range ({position_pct:.0f}%)"
    
    return {
        "support": round(support, 2),
        "resistance": round(resistance, 2),
        "period_low": round(low, 2),
        "period_high": round(high, 2),
        "current_position": position
    }


def calculate_time_decay_metrics(end_date_str: str, current_price: float) -> Dict[str, Any]:
    """
    Calculate time decay metrics for a prediction market.
    
    Args:
        end_date_str: Market end/resolution date as string
        current_price: Current YES price (0-100 scale)
    
    Returns:
        Dict with time decay analysis
    """
    try:
        # Parse end date
        if end_date_str and end_date_str != "Unknown":
            # Try multiple date formats
            for fmt in ["%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M:%SZ"]:
                try:
                    end_date = datetime.datetime.strptime(str(end_date_str).split(".")[0], fmt)
                    break
                except ValueError:
                    continue
            else:
                return {"error": "Could not parse end date", "days_remaining": None}
        else:
            return {"error": "No end date provided", "days_remaining": None}
        
        now = datetime.datetime.now()
        time_delta = end_date - now
        days_remaining = time_delta.days + (time_delta.seconds / 86400)
        hours_remaining = time_delta.total_seconds() / 3600
        
        if days_remaining < 0:
            return {
                "days_remaining": 0,
                "hours_remaining": 0,
                "status": "EXPIRED",
                "urgency": "Market has ended",
                "theta_impact": "N/A"
            }
        
        # Classify urgency
        if hours_remaining <= 24:
            urgency = "CRITICAL"
            urgency_desc = "Less than 24 hours - high gamma, expect volatility"
        elif days_remaining <= 3:
            urgency = "HIGH"
            urgency_desc = "Under 3 days - time pressure increasing"
        elif days_remaining <= 7:
            urgency = "MODERATE"
            urgency_desc = "Under a week - monitor closely"
        elif days_remaining <= 30:
            urgency = "LOW"
            urgency_desc = "Over a week - time is on your side"
        else:
            urgency = "MINIMAL"
            urgency_desc = "Over a month - plenty of time for thesis to play out"
        
        # Calculate theta (time decay factor)
        # Higher theta = faster price convergence expected
        if days_remaining > 0:
            # Theta increases as resolution approaches (like options)
            theta = 1 / math.sqrt(max(days_remaining, 0.1))
        else:
            theta = 1.0
        
        # Probability-time analysis
        # Markets at extreme prices with little time = likely priced correctly
        # Markets at 40-60% with little time = high uncertainty, volatile
        price_uncertainty = 1 - abs(current_price - 50) / 50  # 0 at extremes, 1 at 50%
        time_pressure = min(1, 7 / max(days_remaining, 0.1))  # 1 if <7 days, lower if more
        
        volatility_risk = price_uncertainty * time_pressure
        
        if volatility_risk > 0.7:
            vol_assessment = "HIGH - Uncertain outcome with little time = expect large swings"
        elif volatility_risk > 0.4:
            vol_assessment = "MODERATE - Some price movement expected"
        else:
            vol_assessment = "LOW - Price likely stable or already at terminal value"
        
        # Theta advantage analysis
        if current_price > 80 and days_remaining < 7:
            theta_advice = "Time favors YES holders - market pricing in high likelihood"
        elif current_price < 20 and days_remaining < 7:
            theta_advice = "Time favors NO holders - market pricing in low likelihood"
        elif 40 < current_price < 60 and days_remaining < 3:
            theta_advice = "Coin flip with clock ticking - high risk, wait for clarity or avoid"
        elif days_remaining > 30:
            theta_advice = "Plenty of time for information to emerge - patience may be rewarded"
        else:
            theta_advice = "Monitor for catalysts that could accelerate price discovery"
        
        return {
            "days_remaining": round(days_remaining, 1),
            "hours_remaining": round(hours_remaining, 1),
            "end_date": end_date.strftime("%Y-%m-%d %H:%M"),
            "urgency": urgency,
            "urgency_description": urgency_desc,
            "theta_factor": round(theta, 3),
            "volatility_risk": round(volatility_risk, 2),
            "volatility_assessment": vol_assessment,
            "theta_advice": theta_advice
        }
        
    except Exception as e:
        return {"error": str(e), "days_remaining": None}


# --- State Definition ---
class DebateState(TypedDict):
    messages: Annotated[List[BaseMessage], add_messages]
    market_data: Dict[str, Any]
    market_question: str
    verdict: str
    price_history_24h: Optional[List[float]]  # Price history for calculations
    price_history_7d: Optional[List[float]]   # 7-day price history
    top_traders: Optional[List[Dict[str, Any]]]

# --- Agents ---

import logging

logger = logging.getLogger(__name__)

def statistics_expert(state: DebateState):
    """
    Statistical analysis agent with actual calculation tools.
    
    Computes Expected Value, Kelly Criterion, volatility, momentum indicators,
    and support/resistance levels before synthesizing with LLM.
    """
    try:
        market_data = state.get("market_data", {})
        question = state.get("market_question", "Unknown Market")
        prices_24h = state.get("price_history_24h", [])
        prices_7d = state.get("price_history_7d", [])
        
        current_price = market_data.get("price", 50.0)
        volume_24h = market_data.get("volume_24h", 0)
        volume_7d = market_data.get("volume_7d", 0)
        liquidity = market_data.get("liquidity", 0)
        end_date = market_data.get("end_date", "Unknown")
        
        today = datetime.datetime.now().strftime("%Y-%m-%d")
        
        # --- Run Statistical Calculations ---
        
        # 1. Implied probability analysis
        implied = calculate_implied_probability(current_price)
        
        # 2. Volatility analysis (use 7d data if available, else 24h)
        price_data = prices_7d if prices_7d else prices_24h
        volatility = analyze_price_volatility(price_data)
        
        # 3. Momentum indicators
        momentum = calculate_momentum_indicators(price_data)
        
        # 4. Support/Resistance levels
        sr_levels = compute_support_resistance(price_data)
        
        # 5. Expected Value calculation
        # Use current price as baseline estimate (assume market efficiency)
        # Then show what EV would be at different probability estimates
        ev_at_market = calculate_expected_value(current_price, current_price)
        ev_bullish = calculate_expected_value(current_price, min(95, current_price + 10))
        ev_bearish = calculate_expected_value(current_price, max(5, current_price - 10))
        
        # 6. Kelly Criterion (if there's perceived edge from momentum)
        # Estimate probability adjustment based on momentum
        momentum_adj = 0
        if momentum.get("trend_signal", "").startswith("Strong Bullish"):
            momentum_adj = 5
        elif momentum.get("trend_signal", "").startswith("Bullish"):
            momentum_adj = 2
        elif momentum.get("trend_signal", "").startswith("Strong Bearish"):
            momentum_adj = -5
        elif momentum.get("trend_signal", "").startswith("Bearish"):
            momentum_adj = -2
        
        adjusted_prob = max(5, min(95, current_price + momentum_adj))
        kelly = calculate_kelly_criterion(current_price, adjusted_prob)
        
        # --- Build Analysis Report ---
        stats_report = f"""
## Quantitative Analysis Report

### Market Overview
- **Current Price**: {current_price:.1f}%
- **24h Volume**: ${volume_24h:,.0f}
- **7d Volume**: ${volume_7d:,.0f}
- **Liquidity**: ${liquidity:,.0f}
- **End Date**: {end_date}

### Implied Probability
- Market implies **{implied['implied_yes_prob']:.1f}%** chance of YES
- Breakeven: Need {implied['breakeven_yes']:.1f}%+ true probability for YES bet to be +EV

### Price Volatility ({volatility['volatility_regime']})
- Standard Deviation: {volatility['std_dev']:.2f}%
- Price Range: {volatility['low']:.1f}% - {volatility['high']:.1f}% (Δ{volatility['range']:.1f}%)
- Coefficient of Variation: {volatility['coefficient_of_variation']:.1f}%

### Momentum Analysis
- **Trend**: {momentum['trend_signal']}
- Current: {momentum['current_price']:.1f}% | Short SMA: {momentum.get('sma_short', 'N/A')} | Long SMA: {momentum.get('sma_long', 'N/A')}
- Rate of Change: {momentum.get('rate_of_change', 0):.1f}%

### Support & Resistance
- **Support**: {sr_levels.get('support', 'N/A')}%
- **Resistance**: {sr_levels.get('resistance', 'N/A')}%
- **Position**: {sr_levels.get('current_position', 'N/A')}

### Expected Value Analysis
- If market is efficient (true prob = {current_price:.0f}%): EV ≈ 0%
- If bullish edge (+10%): YES EV = {ev_bullish['yes_ev']:.1f}%, {ev_bullish['recommendation']}
- If bearish edge (-10%): NO EV = {ev_bearish['no_ev']:.1f}%, {ev_bearish['recommendation']}

### Kelly Criterion (Momentum-Adjusted)
- Adjusted probability estimate: {adjusted_prob:.1f}%
- **Optimal Side**: {kelly['optimal_side']}
- Quarter Kelly (conservative): {kelly['quarter_kelly']:.1f}% of bankroll
- Half Kelly (moderate): {kelly['half_kelly']:.1f}% of bankroll
- {kelly['recommendation']}
        """.strip()
        
        # --- LLM Synthesis ---
        prompt = f"""
        You are a Statistics Expert for prediction markets.
        Today's date is: {today}
        
        Market Question: "{question}"
        
        I have computed the following quantitative analysis:
        
        {stats_report}
        
        Based on these calculations:
        1. Is the market efficiently priced or is there an edge?
        2. What does the momentum and volatility suggest about near-term price action?
        3. Given the support/resistance levels, where are the key entry/exit points?
        4. Final recommendation: BUY YES, BUY NO, or AVOID?
        
        Be specific and reference the calculated numbers.
        """
        
        logger.info(f"Statistics Expert computed report, invoking LLM for synthesis...")
        response = llm.invoke([HumanMessage(content=prompt)])
        
        # Combine computed stats with LLM synthesis
        full_response = f"{stats_report}\n\n---\n\n### Expert Interpretation\n\n{response.content}"
        
        return {"messages": [HumanMessage(content=f"**Statistics Expert**: {full_response}", name="Statistics Expert")]}
    except Exception as e:
        logger.error(f"Statistics Expert failed: {e}")
        return {"messages": [HumanMessage(content=f"**Statistics Expert**: (Failed to analyze) {e}", name="Statistics Expert")]}


def top_traders_analyst(state: DebateState):
    """
    Analyze top traders for performance, PnL, and recent flow direction.
    """
    try:
        top_traders = state.get("top_traders") or []
        question = state.get("market_question", "Unknown Market")
        market_data = state.get("market_data", {})
        current_price = market_data.get("price", 50.0)

        if not top_traders:
            return {"messages": [HumanMessage(content="**Top Traders Analyst**: No top trader data available for this market.", name="Top Traders Analyst")]}

        def format_usd(value: float) -> str:
            return f"${value:,.0f}"

        trader_lines = []
        for trader in top_traders:
            name = trader.get("name") or trader.get("address", "Unknown")
            address = trader.get("address", "Unknown")
            total_volume = float(trader.get("total_volume", 0))
            trade_count = int(trader.get("trade_count", 0))
            bullish_volume = float(trader.get("bullish_volume", 0))
            bearish_volume = float(trader.get("bearish_volume", 0))
            bias = trader.get("bias", "mixed")
            last_trade = trader.get("last_trade_at", "Unknown")
            pnl = trader.get("global_pnl")
            balance = trader.get("total_balance")
            source = trader.get("source", "trades")
            position_amount = trader.get("position_amount")
            outcome_index = trader.get("outcome_index")

            pnl_text = format_usd(pnl) if isinstance(pnl, (int, float)) else "N/A"
            balance_text = format_usd(balance) if isinstance(balance, (int, float)) else "N/A"

            if source == "holders":
                side = "YES" if outcome_index == 0 else "NO" if outcome_index == 1 else "?"
                shares = float(position_amount) if isinstance(position_amount, (int, float)) else 0.0
                trader_lines.append(
                    f"- **{name}** (`{address[:6]}…{address[-4:]}`) | "
                    f"Position: {shares:,.0f} shares ({side}) | "
                    f"PnL {pnl_text} | Balance {balance_text}"
                )
            else:
                trader_lines.append(
                    f"- **{name}** (`{address[:6]}…{address[-4:]}`) | "
                    f"Volume {format_usd(total_volume)} across {trade_count} trades | "
                    f"Flow: {bias} (bull {format_usd(bullish_volume)} vs bear {format_usd(bearish_volume)}) | "
                    f"PnL {pnl_text} | Balance {balance_text} | Last trade {last_trade}"
                )

        traders_report = "\n".join(trader_lines)

        prompt = f"""
        You are the Top Traders Analyst on the Debate Floor.

        Market: "{question}"
        Current Price: {current_price:.1f}%

        Here are the top actors (preferably top holders; otherwise top traders) and their recent activity:
        {traders_report}

        Please evaluate:
        1. Which traders show the strongest positive or negative track record (PnL, consistency)?
        2. What does the aggregate flow suggest (bullish vs bearish pressure)?
        3. Are the most profitable traders aligned or fading the market price?
        4. Any notable momentum or reversals in trader behavior?

        Provide a concise, actionable summary for debate participants.
        Use bullet points and highlight the key traders by name.
        """

        response = llm.invoke([HumanMessage(content=prompt)])
        full_response = f"## Top Traders Snapshot\n\n{traders_report}\n\n---\n\n### Expert Interpretation\n\n{response.content}"

        return {"messages": [HumanMessage(content=f"**Top Traders Analyst**: {full_response}", name="Top Traders Analyst")]}
    except Exception as e:
        logger.error(f"Top Traders Analyst failed: {e}")
        return {"messages": [HumanMessage(content=f"**Top Traders Analyst**: (Failed to analyze) {e}", name="Top Traders Analyst")]}

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


def time_decay_analyst(state: DebateState):
    """
    Time Decay & Resolution Analyst.
    
    Specializes in understanding time-to-resolution dynamics,
    theta decay, and optimal entry/exit timing based on market expiration.
    """
    try:
        market_data = state.get("market_data", {})
        question = state.get("market_question", "Unknown Market")
        prices_24h = state.get("price_history_24h", [])
        prices_7d = state.get("price_history_7d", [])
        
        current_price = market_data.get("price", 50.0)
        end_date = market_data.get("end_date", "Unknown")
        volume_24h = market_data.get("volume_24h", 0)
        
        today = datetime.datetime.now().strftime("%Y-%m-%d")
        
        # --- Calculate Time Decay Metrics ---
        time_metrics = calculate_time_decay_metrics(end_date, current_price)
        
        # --- Analyze Recent Price Velocity ---
        velocity_analysis = ""
        if prices_24h and len(prices_24h) >= 2:
            recent_change = prices_24h[-1] - prices_24h[0]
            if abs(recent_change) > 5:
                velocity_analysis = f"Price moved {recent_change:+.1f}% in last 24h - active information flow"
            else:
                velocity_analysis = f"Price stable (Δ{recent_change:+.1f}%) - market in wait-and-see mode"
        else:
            velocity_analysis = "Insufficient price data for velocity analysis"
        
        # --- Build Time Analysis Report ---
        if time_metrics.get("error"):
            time_report = f"""
## Time Decay Analysis

⚠️ **Unable to analyze**: {time_metrics.get('error')}

Without a resolution date, time-based analysis is not possible.
Proceed with caution and rely on other signals.
            """.strip()
        else:
            days = time_metrics.get("days_remaining", "?")
            hours = time_metrics.get("hours_remaining", "?")
            urgency = time_metrics.get("urgency", "Unknown")
            urgency_desc = time_metrics.get("urgency_description", "")
            theta = time_metrics.get("theta_factor", 0)
            vol_risk = time_metrics.get("volatility_risk", 0)
            vol_assess = time_metrics.get("volatility_assessment", "")
            theta_advice = time_metrics.get("theta_advice", "")
            end_dt = time_metrics.get("end_date", "Unknown")
            
            # Urgency emoji
            urgency_emoji = {
                "CRITICAL": "🔴",
                "HIGH": "🟠",
                "MODERATE": "🟡",
                "LOW": "🟢",
                "MINIMAL": "⚪"
            }.get(urgency, "⚪")
            
            time_report = f"""
## Time Decay & Resolution Analysis

### Resolution Timeline
- **Resolution Date**: {end_dt}
- **Time Remaining**: {days} days ({hours:.0f} hours)
- **Urgency**: {urgency_emoji} {urgency} - {urgency_desc}

### Theta Analysis (Time Decay Factor)
- **Theta Factor**: {theta:.3f} (higher = faster expected convergence)
- **Volatility Risk Score**: {vol_risk:.2f}/1.00
- **Volatility Assessment**: {vol_assess}

### Price Velocity
- {velocity_analysis}
- **24h Volume**: ${volume_24h:,.0f}

### Strategic Implications
{theta_advice}
            """.strip()
        
        # --- LLM Synthesis ---
        prompt = f"""
        You are a Time Decay & Resolution Analyst for prediction markets.
        Today's date is: {today}
        
        Market Question: "{question}"
        Current Price: {current_price:.1f}%
        
        I have computed the following time-based analysis:
        
        {time_report}
        
        Based on this time analysis:
        1. Is the timing favorable for entering a position now, or should the user wait?
        2. What specific catalysts or events should occur before resolution that could move the price?
        3. Is the current price "priced in" given the time remaining, or is there mispricing?
        4. What's the optimal strategy considering time decay (hold, take profits, cut losses, wait)?
        
        Be specific about timing recommendations. Reference the calculated metrics.
        """
        
        logger.info(f"Time Decay Analyst computed report, invoking LLM for synthesis...")
        response = llm.invoke([HumanMessage(content=prompt)])
        
        full_response = f"{time_report}\n\n---\n\n### Expert Interpretation\n\n{response.content}"
        
        return {"messages": [HumanMessage(content=f"**Time Decay Analyst**: {full_response}", name="Time Decay Analyst")]}
    except Exception as e:
        logger.error(f"Time Decay Analyst failed: {e}")
        return {"messages": [HumanMessage(content=f"**Time Decay Analyst**: (Failed to analyze) {e}", name="Time Decay Analyst")]}


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

# Agent definitions for dynamic graph building
AGENT_NODES = {
    "statistics_expert": statistics_expert,
    "top_traders_analyst": top_traders_analyst,
    "generalist_expert": generalist_expert,
    "devils_advocate": devils_advocate,
    "crypto_macro_analyst": crypto_macro_analyst,
    "time_decay_analyst": time_decay_analyst,
}

# Preferred order of agents (Devil's Advocate should come after others to challenge their points)
# Time Decay Analyst comes after Statistics to add temporal context to the quantitative analysis
AGENT_ORDER = [
    "statistics_expert",
    "time_decay_analyst",
    "top_traders_analyst",
    "generalist_expert",
    "crypto_macro_analyst",
    "devils_advocate",
]


def build_debate_graph(config: Optional[AgentConfig] = None) -> StateGraph:
    """
    Build a debate graph with only the enabled agents.
    
    Args:
        config: Agent configuration specifying which agents to enable.
                If None, all agents are enabled.
    
    Returns:
        Compiled LangGraph workflow.
    """
    if config is None:
        config = DEFAULT_AGENT_CONFIG
    
    workflow = StateGraph(DebateState)
    
    # Determine which agents are enabled (in order)
    enabled_agents = [agent for agent in AGENT_ORDER if config.get(agent, True)]
    
    # Log enabled agents
    logger.info(f"Building debate graph with agents: {enabled_agents}")
    
    # Add enabled agent nodes
    for agent_name in enabled_agents:
        workflow.add_node(agent_name, AGENT_NODES[agent_name])
    
    # Moderator is always added (required for verdict)
    workflow.add_node("moderator", moderator)
    
    # Build the chain
    if enabled_agents:
        # Set entry point to first enabled agent
        workflow.set_entry_point(enabled_agents[0])
        
        # Chain agents together
        for i in range(len(enabled_agents) - 1):
            workflow.add_edge(enabled_agents[i], enabled_agents[i + 1])
        
        # Last agent connects to moderator
        workflow.add_edge(enabled_agents[-1], "moderator")
    else:
        # No agents enabled, go straight to moderator
        workflow.set_entry_point("moderator")
    
    workflow.add_edge("moderator", END)
    
    return workflow.compile()


# Default app with all agents enabled (for backwards compatibility)
debate_app = build_debate_graph()
