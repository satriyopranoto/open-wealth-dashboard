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
docker build -t stocktrade-app:latest .
docker stop stocktrade-app-1 && docker rm stocktrade-app-1
docker run -d --name stocktrade-app-1 --restart unless-stopped \
  --network stocktrade_default --network-alias app \
  -v /c/Users/satri/stocktrade/cache:/app/cache \
  -v /c/Users/satri/stocktrade/logs:/app/logs \
  stocktrade-app:latest
```

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
