# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Install dependencies
pip install -r requirements.txt

# Run development server (port 5000)
python app.py

# CLI batch downloader (incremental — only fetches new trading days)
python downloader.py uslist.csv --output-folder cache
python downloader.py idlist.csv --output-folder cache

# Production deployment (nginx + Flask via gunicorn)
docker-compose up
```

No test runner or linter is configured. No build step is required — the frontend is plain HTML served by Flask.

## Architecture

Flask backend (`app.py`) + logging module (`log_utils.py`) + CLI tool (`downloader.py`), serving a single-page HTML frontend (`templates/index.html`). No database — all persistence is file-based cache in `cache/` and logs in `logs/`.

### Files

| File | Purpose |
|------|---------|
| `app.py` | Main Flask backend (~2200 lines) |
| `log_utils.py` | Action logging module |
| `downloader.py` | Standalone CLI batch downloader |
| `templates/index.html` | Single-page frontend (vanilla JS) |
| `templates/logs.html` | Usage log viewer page |
| `nginx.conf` | Reverse proxy config (production) |
| `docker-compose.yml` | Orchestrates nginx + Flask |

### Backend (`app.py`)

#### Routes

**Core analysis:**
- `GET /` — serves the HTML template (SPA)
- `GET /assets/<filename>` — serves static files from `/assets`
- `POST /analyze` — main analysis endpoint
- `POST /refresh` — same as `/analyze` but forces cache bypass

**Screeners (Indonesia):**
- `GET|POST /screener/most-active` — most active IDX stocks
- `GET|POST /screener/day-gainers` — day gainers IDX stocks
- `GET|POST /screener/net-net` — net-net strategy IDX stocks
- `GET|POST /screener/acquirers-multiple` — Acquirers Multiple IDX stocks
- `GET|POST /screener/id-bb-breakout` — BB breakout screener from `idlist.csv`

**Screeners (US):**
- `GET|POST /screener/us-most-active`
- `GET|POST /screener/us-day-gainers`
- `GET|POST /screener/us-net-net`
- `GET|POST /screener/us-acquirers-multiple`
- `GET|POST /screener/us-bb-breakout` — BB breakout screener from `uslist.csv`

**Screener SSE:**
- `GET /screener/bb-progress` — Server-Sent Events stream for BB screener progress

**Extraction (bulk data sync):**
- `POST /extract/us` — spawn background thread to download all tickers in `uslist.csv`
- `POST /extract/id` — spawn background thread to download all tickers in `idlist.csv`
- `GET /extract/progress` — SSE stream for extraction progress
- `GET /extract/status` — current extraction status + rate limit info

**Logs:**
- `GET /logs` — usage log viewer (query params: `date=YYYY-MM-DD`, `limit=N`)

#### Data pipeline per `/analyze` request

1. Check `cache/[TICKER].csv` (1-hour TTL, line 1 is a `#`-prefixed JSON metadata header)
2. If stale/missing, download via `yfinance` with 3-attempt retry (5s delay)
3. Calculate RSI (`calculate_rsi`, 14-period), Stop Loss (`calculate_sl`, Donchian channel ported from Pine Script), and Bollinger Bands (`calculate_bollinger_bands`, 20-period SMA ± 2 std)
4. Generate candlestick chart with matplotlib (Agg backend, no GUI) → encode as base64 PNG
5. Fetch fundamental data from yfinance → cache as `cache/[TICKER]_fundamental.json` (24-hour TTL)
6. Fetch top 10 news articles via `pygooglenews` (Google News, Indonesian + English) → cache 1 hour
7. Return JSON with chart, indicators, fundamentals, news, and recommendation

**Recommendation logic** (based on last candle vs. SL):
- BUY: `low > SL`
- SELL/WAIT: `high < SL`
- NEUTRAL/HOLD: otherwise

#### Screener system

Standard screeners (most-active, day-gainers, net-net, acquirers-multiple) use `yahooquery.Screener`. Indonesia stocks are filtered by `.JK` suffix; US stocks are unfiltered. Results cached 1 hour at `cache/screener_{name}.csv`.

BB breakout screeners scan all tickers in the watchlist CSV, calculate SL + Bollinger Bands per ticker, and flag `price > SL && price > upper_BB` as BUY signals. These run in a background daemon thread; real-time progress is streamed via SSE at `/screener/bb-progress`.

#### Extraction system

`/extract/us` and `/extract/id` spawn daemon threads to download 200 days of OHLCV for every ticker in the watchlist CSV. Rate-limited to 60 minutes between runs using a marker file at `cache/.extraction_{name}_marker.txt`. Progress is streamed via SSE at `/extract/progress`.

### Logging system (`log_utils.py`)

Every feature usage is logged to `logs/usage-YYYY-MM-DD.log` (JSON lines, daily rotation).

Log entry fields: `timestamp`, `feature`, `action`, `status`, `params`, `duration_ms`, `ip`, `detail`

`_get_client_ip()` extracts the real client IP from `X-Forwarded-For` (handles nginx reverse proxy).

Logs are viewable at `GET /logs?date=YYYY-MM-DD&limit=N`.

### CLI downloader (`downloader.py`)

Standalone script for incremental batch updates — only fetches new trading days since the last cached date. Shares the 60-minute rate-limit marker pattern with the extraction system.

### Frontend (`templates/index.html`)

Vanilla JS + Chart.js (CDN). Sections rendered after each analysis:
- Info box (price, RSI), recommendation, chart (base64 PNG in `<img>`)
- 13 fundamental metrics (color-coded: green positive, red negative)
- Company description, related news, lot size calculator (client-side)
- Screener tables (multiple strategies, BB breakout with live progress)
- Extraction tool for bulk data synchronization

### Cache summary

| Type | Path | TTL | Format |
|------|------|-----|--------|
| Stock data | `cache/{ticker}.csv` | 1 hour | CSV + JSON metadata header |
| Fundamentals | `cache/{ticker}_fundamental.json` | 24 hours | JSON |
| Screener results | `cache/screener_{name}.csv` | 1 hour | CSV + JSON metadata |
| News | `cache/{ticker}_news.json` | 1 hour | JSON |
| Rate limit marker | `cache/.extraction_{name}_marker.txt` | — | Timestamp file |

### Environment

Configured via `.env` (not in git):
```
FLASK_APP=app.py
FLASK_ENV=development
API_BASE_URL=http://127.0.0.1:5000
FLASK_PORT=5000
```

See `CONFIG.md` for deployment scenarios (local, network, production URL changes).

### Docker / Nginx

`docker-compose.yml` brings up two services: nginx (reverse proxy, port 5000) and the Flask app (gunicorn). Volumes `./cache` and `./logs` are mounted for persistence. For network/production deployments, `API_BASE_URL` in `.env` must match the deployment IP or domain.

### Key implementation notes

- yfinance sometimes returns MultiIndex columns — handled at lines ~411-412 in `app.py`
- matplotlib must use `Agg` backend (set at module level) to avoid GUI errors in server context
- Comments throughout `app.py` and `index.html` are in Indonesian (Bahasa Indonesia)
- SSE responses use `text/event-stream` with `Cache-Control: no-cache` and keep-alive flushing
- Daemon threads for extraction/BB screener share mutable global dicts (`extraction_progress`, `bb_screener_progress`) for SSE polling — no locks, single-writer pattern
