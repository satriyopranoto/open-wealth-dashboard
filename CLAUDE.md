# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Install dependencies
pip install -r requirements.txt

# Run development server (port 5000)
python app.py
```

No test runner or linter is configured. No build step is required — the frontend is plain HTML served by Flask.

## Architecture

Single-file Flask backend (`app.py`) serving a single-page HTML frontend (`templates/index.html`). No database — all persistence is file-based cache in `cache/`.

### Backend (`app.py`)

Three routes:
- `GET /` — serves the HTML template
- `POST /analyze` — main analysis endpoint
- `POST /refresh` — same as `/analyze` but forces cache bypass

**Data pipeline per request:**
1. Check `cache/[TICKER].csv` (24-hour TTL, line 1 is a `#`-prefixed JSON metadata header)
2. If stale/missing, download via `yfinance` with 3-attempt retry (5s delay)
3. Calculate RSI (`calculate_rsi`) and Stop Loss (`calculate_sl`) using Donchian Channel logic ported from Pine Script
4. Generate candlestick chart with matplotlib (Agg backend, no GUI) → encode as base64 PNG
5. Fetch fundamental data from yfinance → cache as `cache/[TICKER]_fundamental.json` (24-hour TTL)
6. Parse Yahoo Finance RSS feed for top 5 news items
7. Return JSON with chart, indicators, fundamentals, news, and recommendation

**Recommendation logic** (based on last candle vs. SL):
- BUY: `low > SL`
- SELL/WAIT: `high < SL`
- NEUTRAL/HOLD: otherwise

### Frontend (`templates/index.html`)

Vanilla JS + Chart.js (CDN). Sections rendered after each analysis:
- Info box (price, RSI), recommendation, chart (base64 PNG in `<img>`)
- 13 fundamental metrics (color-coded: green positive, red negative)
- Company description, related news, lot size calculator (client-side)

### Environment

Configured via `.env` (not in git):
```
FLASK_APP=app.py
FLASK_ENV=development
API_BASE_URL=http://127.0.0.1:5000
FLASK_PORT=5000
```

See `CONFIG.md` for deployment scenarios (local, network, production URL changes).

### Key implementation notes

- yfinance sometimes returns MultiIndex columns — handled at lines ~411-412 in `app.py`
- matplotlib must use `Agg` backend (set at module level) to avoid GUI errors in server context
- Comments throughout `app.py` and `index.html` are in Indonesian
