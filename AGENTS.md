# AGENTS.md - Polymarket News Tracker

## Project Overview
A real-time market tracking dashboard that displays the top 50 Polymarket markets by 7-day volume, integrates TradingView charts for price visualization, and provides a live news feed for selected markets.

---

## Tech Stack

### Backend
- **Framework**: FastAPI
- **Language**: Python 3.12+
- **Package Manager**: `uv` (strict requirement)
- **Database**: SQLite (for caching market data, user selections, news articles)
- **APIs**:
  - Polymarket API (market data, volume, prices)
  - News API (for real-time news aggregation)
  - TradingView Widget (embedded charts)

### Frontend
- **Framework**: React 18+ with Vite
- **Language**: TypeScript
- **Styling**: Tailwind CSS with glassmorphism effects
- **State Management**: React Query (for API data) + Zustand (for UI state)
- **Charts**: TradingView Advanced Charts Widget

### Data Pipeline
- **Caching Layer**: SQLite database with TTL-based invalidation
- **Update Frequency**: 
  - Market data: Every 5 minutes
  - News feed: Real-time via polling (30s intervals)
  - Top 50 ranking: Every 15 minutes

---

## Project Structure

```bash
polymarket-news-tracker/
├── .python-version          # Python 3.12+
├── pyproject.toml           # uv configuration
├── uv.lock                  # Dependency lock file
├── .env.example             # Template for environment variables
├── .gitignore               # Exclude polymarket.db, .env, etc.
├── src/
│   ├── backend/
│   │   ├── __init__.py
│   │   ├── main.py          # FastAPI app entry point
│   │   ├── models.py        # SQLAlchemy models (Market, News, etc.)
│   │   ├── database.py      # SQLite connection and session management
│   │   ├── polymarket/
│   │   │   ├── __init__.py
│   │   │   ├── client.py    # Polymarket API client
│   │   │   └── schemas.py   # Pydantic models for API responses
│   │   ├── news/
│   │   │   ├── __init__.py
│   │   │   ├── aggregator.py # News fetching and filtering logic
│   │   │   └── schemas.py    # News article Pydantic models
│   │   ├── routes/
│   │   │   ├── __init__.py
│   │   │   ├── markets.py    # GET /markets/top50, GET /markets/{id}
│   │   │   └── news.py       # GET /news/{market_id}
│   │   └── tasks/
│   │       ├── __init__.py
│   │       └── update_markets.py # Background task for market updates
│   └── frontend/
│       ├── package.json
│       ├── vite.config.ts
│       ├── tsconfig.json
│       ├── src/
│       │   ├── App.tsx
│       │   ├── main.tsx
│       │   ├── components/
│       │   │   ├── MarketList.tsx      # Top 50 markets selector
│       │   │   ├── TradingViewChart.tsx # TradingView widget wrapper
│       │   │   ├── NewsFeed.tsx         # Real-time news display
│       │   │   └── TimeframeSelector.tsx # Chart timeframe controls
│       │   ├── hooks/
│       │   │   ├── useMarkets.ts       # React Query hook for markets
│       │   │   └── useNews.ts          # React Query hook for news
│       │   ├── stores/
│       │   │   └── marketStore.ts      # Zustand store for selected market
│       │   └── styles/
│       │       └── globals.css         # Tailwind + custom styles
│       └── index.html
└── README.md
```

## Agent Responsibilities

### Agent 1: Backend API Developer
**Focus**: FastAPI backend, Polymarket integration, database management

**Tasks**:
1. Set up FastAPI application with CORS for React frontend
2. Implement Polymarket API client:
   - Fetch top 50 active markets by 7-day volume
   - Filter for `active=true` status only
   - Extract market metadata (title, slug, volume, current Yes %)
3. Design SQLite schema:
   - `markets` table: id, slug, title, volume_7d, yes_percentage, last_updated, is_active
   - `news_articles` table: id, market_id, title, url, source, published_at, sentiment_score (optional)
4. Create REST endpoints:
   - `GET /api/markets/top50` → Returns top 50 markets sorted by volume
   - `GET /api/markets/{market_id}` → Returns detailed market data
   - `GET /api/news/{market_id}?limit=20` → Returns news articles for selected market
5. Implement background tasks (using `FastAPI BackgroundTasks` or `apscheduler`):
   - Update market rankings every 15 minutes
   - Fetch and cache news articles every 30 seconds for active markets
6. Add `.env` configuration:
```
   POLYMARKET_API_KEY=your_key_here
   NEWS_API_KEY=your_key_here
   DATABASE_URL=sqlite:///./polymarket.db
   CORS_ORIGINS=http://localhost:5173
```

**Deliverables**:
- Fully functional FastAPI backend with documented endpoints
- SQLite database with proper migrations (using Alembic if needed)
- Populated `.env.example`

---

### Agent 2: Frontend Developer
**Focus**: React + TypeScript UI, TradingView integration, real-time updates

**Tasks**:
1. Set up Vite + React + TypeScript project
2. Install dependencies:
```bash
   npm install react-query zustand axios tailwindcss @headlessui/react lucide-react
```
3. Implement components:
   - **MarketList**: 
     - Display top 50 markets in a scrollable, searchable list
     - Show market title, 7-day volume, current Yes %
     - Highlight selected market with glassmorphism effect
   - **TradingViewChart**:
     - Embed TradingView widget showing Yes % over time
     - Allow timeframe selection (1H, 4H, 1D, 1W, 1M)
     - Use `market_slug` to fetch correct data
   - **NewsFeed**:
     - Display news articles in a card-based layout
     - Auto-refresh every 30 seconds using React Query
     - Show article title, source, timestamp, and link
   - **TimeframeSelector**:
     - Toggle buttons for chart timeframes
     - Update TradingView widget on selection
4. State management:
   - Use Zustand for `selectedMarket` and `selectedTimeframe`
   - Use React Query for API data fetching with 5-minute cache
5. Styling:
   - Dark theme with vibrant accent colors (e.g., electric blue, neon green)
   - Glassmorphism cards with backdrop blur
   - Smooth transitions on hover/selection
   - Responsive design (mobile-first)

**Deliverables**:
- Polished React application with premium aesthetics
- Functional TradingView integration
- Real-time news feed with auto-refresh

---

### Agent 3: Data Pipeline & News Aggregator
**Focus**: News fetching, filtering, and relevance scoring

**Tasks**:
1. Implement news aggregation logic:
   - Use NewsAPI, Google News RSS, or similar service
   - Filter articles by market-related keywords (extracted from market title)
   - Example: For "Will Trump win 2024?", search for "Trump 2024 election"
2. Add sentiment analysis (optional but recommended):
   - Use lightweight NLP library (e.g., `textblob` or `vaderSentiment`)
   - Score articles as positive/negative/neutral for market context
3. Deduplication:
   - Avoid storing duplicate articles from multiple sources
   - Use URL or title hash for uniqueness checks
4. Database optimization:
   - Index `market_id` and `published_at` columns
   - Implement TTL (time-to-live) for old articles (e.g., delete after 7 days)
5. Error handling:
   - Gracefully handle API rate limits
   - Log failed requests for debugging

**Deliverables**:
- Robust news aggregation pipeline
- SQLite database with indexed news articles
- Documented news filtering logic

---

### Agent 4: DevOps & Integration
**Focus**: Build system, deployment, testing

**Tasks**:
1. Create `uv`-based Python environment:
```bash
   uv venv
   uv sync
```
2. Add startup scripts:
   - `scripts/start_backend.sh`:
```bash
     #!/bin/bash
     uv run uvicorn src.backend.main:app --reload --port 8000
```
   - `scripts/start_frontend.sh`:
```bash
     #!/bin/bash
     cd src/frontend && npm run dev
```
3. Set up `.gitignore`:
```
   .env
   polymarket.db
   __pycache__/
   node_modules/
   dist/
   .venv/
```
4. Write comprehensive `README.md`:
   - Project description
   - Setup instructions (using `uv`)
   - API endpoint documentation
   - Environment variable requirements
5. Add health checks:
   - `GET /api/health` → Returns backend status
   - `GET /api/markets/status` → Returns last update timestamp

**Deliverables**:
- Production-ready build system
- Documented setup process
- Health check endpoints

---

## Implementation Phases

### Phase 1:
- [ ] Backend: Top 50 markets endpoint with SQLite caching
- [ ] Frontend: Market list with selection
- [ ] TradingView chart integration (basic)

### Phase 2:
- [ ] News API integration
- [ ] Real-time news feed with auto-refresh
- [ ] Market-to-news keyword matching

### Phase 3:
- [ ] Premium UI with glassmorphism
- [ ] Sentiment analysis for news articles
- [ ] Performance optimization (lazy loading, pagination)

### Phase 4:
- [ ] Docker containerization

---

## Critical Requirements

1. **ALWAYS use `uv`** for Python dependency management
2. **NEVER commit `.env` or `polymarket.db`** to version control
3. **Ensure `.env.example` is populated** with all required variables
4. **Filter ONLY active markets** from Polymarket API
5. **Implement proper error handling** for all API calls
6. **Use TypeScript strict mode** in frontend
7. **Add loading states** for all async operations
8. **Verify TradingView widget renders correctly** before shipping

---

## Success Criteria

- [ ] Top 50 markets load in <2 seconds
- [ ] TradingView chart updates on market/timeframe change
- [ ] News feed auto-refreshes every 30 seconds
- [ ] UI is visually stunning with smooth animations
- [ ] All API endpoints return proper error codes
- [ ] Project builds without errors using `uv sync` and `npm install`