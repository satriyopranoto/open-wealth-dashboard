# Stocktrade - Agent Reference

## Common Issues & Fixes

---

### 1. CONNECTION ABORTED / JSON Parse Error

**Symptom:** Browser shows "CONNECTION ABORTED" after clicking Analyze.  
**Console:** Fetch error / `response.json()` fails.  
**Root cause:** Flask `jsonify` serializes `float('nan')` as `NaN` in JSON. `NaN` is **not valid JSON** — `JSON.parse()` in the browser throws a `SyntaxError`, caught as "CONNECTION ABORTED".

**Fix (app.py — analyze_stock endpoint):**
- Replace all `NaN`/`Infinity` values with `None` before `jsonify()`
- Helper function `clean_nan()` recursively walks dicts/lists and replaces `float('nan')` / `float('inf')` / `float('-inf')` with `None`
- Frontend must handle `null` values: use ternary `data.last_price != null ? data.last_price.toFixed(2) : 'N/A'`

**Key locations:**
- `app.py`: `analyze_stock()` response builder → wrap `jsonify(clean_nan(result))`
- `index.html`: `renderChart()`, price, RSI, SL display → null-safe access

---

### 2. Bokeh Chart Not Stretching Width

**Symptom:** Chart renders in a narrow strip on the left side of the chart area.  
**Inspector:** `<div class="bk-Figure">` appears but does not fill parent width.  
**Root cause:** Bokeh figures created with default sizing (fixed width ~500px). The `Column` layout had `sizing_mode="stretch_width"` but individual figures did not.

**Fix (bokeh_chart.py — generate_chart function):**
- Pass `sizing_mode="stretch_width"` to **each** `_make_base_figure()` call (both `p1` and `p2`)
- The file_html output also needs explicit CSS injection:
  ```css
  [data-root-id] { display: block !important; width: 100% !important; }
  .bk-root { width: 100% !important; }
  body { margin: 0; padding: 0; width: 100%; }
  ```

**Key locations:**
- `bokeh_chart.py`: `_make_base_figure()` defaults → add `sizing_mode` param
- `bokeh_chart.py`: `file_html()` output → inject CSS via `html.replace('</head>', ...)`
- `index.html`: `#chart-container { width: 100%; }` — stay within main container

---

### 3. Nginx DNS Resolution (Network Alias)

**Symptom:** Requests through nginx fail with connection errors.  
**Root cause:** Nginx `proxy_pass http://app:5000;` cannot resolve `app` because the Flask container lacked the DNS alias.  
**Fix:** Run Flask container with `--network-alias app`:
```bash
docker run ... --network stocktrade_default --network-alias app stocktrade-app:latest
```

---

### 4. Docker Infrastructure

- **Nginx** (`stocktrade-nginx-1`): Host port `5000` → container port `80`. Proxies to `http://app:5000`.
- **Flask App** (`stocktrade-app-1`): Internal port `5000`. Must have network alias `app`.
- **Network:** Both on `stocktrade_default`

To rebuild and deploy from the Windows git clone:
```bash
# Clone is at C:\Users\satri\code\stocktrade — build directly from there
cd /c/Users/satri/code/stocktrade
docker build -t stocktrade-app:latest "C:\Users\satri\code\stocktrade"
# or: DOCKER_BUILDKIT=0 docker build -t stocktrade-app:latest .
docker stop stocktrade-app-1 && docker rm stocktrade-app-1
docker run -d --name stocktrade-app-1 --restart unless-stopped \
  --network stocktrade_default --network-alias app \
  -v /c/Users/satri/code/stocktrade/cache:/app/cache \
  -v /c/Users/satri/code/stocktrade/logs:/app/logs \
  stocktrade-app:latest
```

**⚠️ One Source of Truth:** Semua data aplikasi (code + cache + logs) di `C:\Users\satri\code\stocktrade`. Jangan buat folder duplikat di luar repo.


---

### 5. Analyze Endpoint Method Change

Changed from POST to GET to avoid form-parsing issues with nginx:
- `app.py`: Route accepts `GET, POST, OPTIONS`
- `app.py`: `ticker = request.args.get('ticker') or request.form.get('ticker', '').strip().upper()`
- `index.html`: Fetch uses `${API_BASE_URL}/analyze?ticker=${encodeURIComponent(ticker)}` with `method: 'GET'`

---

### 6. Chart Rendering — iframe Approach

The chart is rendered via **iframe** instead of inline Bokeh components:
- `/chart_html/<ticker>` endpoint returns standalone Bokeh HTML (from `file_html()`)
- Frontend injects `<iframe src="/chart_html/<ticker>">` instead of embedding `chart_div`
- Avoids Bokeh JS conflicts with Tailwind `display: contents`
- Requires `generate_chart()` NOT to be called in the `/analyze` endpoint (saves 105KB response size)

---

### 7. Y-Axis Labels on Wrong Side (Left vs Right)

**Symptom:** Price and ADX y-axis tick labels appear on the left side instead of right.
**Root cause:** Bokeh's figure default is `y_axis_location="left"`.
**Fix:** Add `y_axis_location="right"` to both `_make_base_figure()` calls in `bokeh_chart.py` (p1 and p2).
**Key location:** `bokeh_chart.py` — `generate_chart()` → p1 and p2 figure creation.

---

### 8. Stop Loss (SL) Not Donchian

**Symptom:** SL line on chart is a flat percentage below price (e.g. 2% of Close), not the Donchian Channel.
**Root cause:** The `serve_chart_html` endpoint used `df_plot['Close'] * 0.98` instead of the EA's Donchian SL logic.
**Fix:** Call `calculate_sl(df_plot)` from `app.py` (already exists) instead of the simplified calculation.
**Key location:** `app.py` → `serve_chart_html()` — replace `sl_series = df_plot['Close'] * 0.98` with `sl_series = calculate_sl(df_plot)`.
**Donchian logic** (`calculate_sl` in app.py):
- Lookback period = `atr_multiple * atr_period` (default 2.8 × 10 = 28)
- `r` = Highest High over lookback period (shifted by 1)
- `s` = Lowest Low over lookback period (shifted by 1)
- SL = `r` (for uptrend/Long) or `s` (for downtrend/Short)

---

### 9. Timeframe Selector (H1/H4/D1/W1/MN)

**Feature:** Timeframe selector buttons below the chart — click to switch chart interval.
**Backend:** `/chart_html/<ticker>?tf=1h` accepts timeframe parameter:
- `1h` → 1-hour candles (30d), uses yfinance interval="1h"
- `4h` → 4-hour candles (60d), resampled from 1h
- `1d` → daily (400d), default
- `1wk` → weekly (2y), interval="1wk"
- `1mo` → monthly (10y), interval="1mo"
**Frontend:** `templates/index.html` — `.tf-btn` buttons call `changeTimeframe(tf, btn)`.
**Key locations:** `app.py` → `serve_chart_html()`, `templates/index.html` → `renderChart()` + `changeTimeframe()`.

---

### 10. SL Timeframe Sync (Risk Management)

**Feature:** When user clicks a timeframe button (H1/H4/D1/W1/MN), the **Stop Loss** value in the Risk Management section auto-updates to match the selected chart timeframe's Donchian SL.

**How it works:**
- `changeTimeframe(tf, btn)` in `index.html` now also calls `/sl?ticker=X&tf=1h`
- Backend `/sl` endpoint downloads data with timeframe-appropriate period/interval, calculates `calculate_sl()` on that data, returns the timeframe-specific SL
- Frontend updates `#calc-sl` textContent and calls `calculateLotSize()` to re-calc exposure with the new SL

**Example results (AAPL):**
| Timeframe | SL |
|-----------|-----|
| D1 (daily) | 273.75 (wide — higher volatility) |
| H1 | 311.91 (tighter — lower volatility) |

**Key locations:**
- `app.py` → `get_sl_for_timeframe()` (new endpoint `/sl`)
- `templates/index.html` → `changeTimeframe()` (added fetch + update logic)

**Note:** D1 button is the default active state on initial page load.

