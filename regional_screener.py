#!/usr/bin/env python3
"""
Regional Screener — Daily Market Data Collection
=================================================
Scrapes ~50+ market data points from Investing.com, Yahoo Finance, IDX, CNBC, BI, ChemicalBook
Outputs structured JSON for use by the morning briefing cron agent.

Usage:
    python3 regional_screener.py                # normal run
    python3 regional_screener.py --json-only    # only output JSON (no debug)

Dependencies: curl_cffi, beautifulsoup4, lxml  (all in stocktrade venv)
"""

import curl_cffi.requests as req
from bs4 import BeautifulSoup
import json, re, os, sys
from datetime import datetime

# ──────────────────────── CONFIG ────────────────────────

TIMEOUT = 30
IMPRERSONATE = 'chrome120'
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                  '(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.9,id;q=0.8,zh-CN;q=0.7',
}
ZH_HEADERS = {**HEADERS, 'Accept-Language': 'zh-CN,en;q=0.9,id;q=0.8'}

DATA = {}

# ──────────────────────── HELPERS ────────────────────────


def fetch(url, impersonate=IMPRERSONATE, headers=HEADERS, timeout=TIMEOUT):
    r = req.get(url, impersonate=impersonate, headers=headers, timeout=timeout)
    r.raise_for_status()
    return r


def clean_num(s):
    if not s:
        return None
    s = s.strip().replace(',', '').replace('\u2033', '').replace('\u2757', '')
    return s


def code_from_name(name):
    mapping = {
        'dow jones': 'Dow',
        's&p 500': 'S&P 500',
        'nasdaq': 'Nasdaq',
        'ftse 100': 'FTSE',
        'dax': 'DAX',
        'cac 40': 'CAC',
        'nikkei 225': 'Nikkei',
        'hang seng': 'HSI',
        'shanghai': 'Shanghai',
        'idx composite': 'IDX',
        'idx lq45': 'LQ45',
        'idx kompas 100': 'IDX Kompas 100',
        'ftse indonesia local': 'FTSE Indonesia',
        'idx30': 'IDX30',
        'idx 30': 'IDX30',
        'idx energy': 'IDXEnergy',
        'idx basic materials': 'IDX BscMat',
        'idx industrials': 'IDXIndst',
        'idx consumer non-cyclicals': 'IDXNONCYC',
        'idx healthcare': 'IDXHlthcare',
        'idx consumer cyclical': 'IDXCYCLC',
        'idx technology': 'IDX Tech',
        'idx transportation': 'IDX Transprt',
        'idx infrastructure': 'IDX Infra',
        'idx finance': 'IDX Finance',
        'idx banking': 'IDX Banking',
        'u.s. 2y': 'US2Yr',
        'u.s. 5y': 'US5Yr',
        'u.s. 10y': 'US10Yr',
        'u.s. 30y': 'US30Yr',
        'indo 10y': 'Indo10Yr',
        'indonesia 10y': 'Indo10Yr',
    }
    key = name.lower().strip()
    if key in mapping:
        return mapping[key]
    return name


# ────────────────── TABLE-BASED PARSERS ──────────────────


def parse_table_pages(pages):
    results = {}
    for label, url, name_col, last_col, chg_col, chg_pct_col in pages:
        try:
            resp = fetch(url)
            bs = BeautifulSoup(resp.text, 'lxml')
            tables = bs.find_all('table')
            if not tables:
                continue
            table = tables[0]
            rows = table.find_all('tr')
            for row in rows[1:]:
                cells = row.find_all('td')
                if len(cells) <= max(name_col, last_col, chg_col, chg_pct_col):
                    continue
                name = cells[name_col].get_text(' ', strip=True)
                name_clean = re.sub(r'\s*derived$', '', name).strip()
                code = code_from_name(name_clean)
                last_txt = cells[last_col].get_text(strip=True)
                chg_txt = cells[chg_col].get_text(strip=True) if chg_col < len(cells) else ''
                pct_txt = cells[chg_pct_col].get_text(strip=True) if chg_pct_col < len(cells) else ''
                if last_txt and code:
                    results[code] = {
                        'close': clean_num(last_txt),
                        'change': clean_num(chg_txt),
                        'change_pct': pct_txt,
                        'source': label,
                    }
        except Exception as e:
            print(f"  WARN {label}: {type(e).__name__}: {str(e)[:60]}", file=sys.stderr)
    return results


def parse_commodities_futures():
    results = {}
    wanted = {
        'Crude Oil WTI': 'Oil(WT)',
        'Brent Oil': 'Oil(Brn)',
        'Natural Gas': 'Ntrl Gas',
        'Gold': 'Gold',
        'Silver': 'Silver',
        'Copper': 'Copper',
        'Aluminium': 'Aluminium',
        'Nickel': 'Nickel',
        'Tin': 'Timah',
        'US Corn': 'Corn',
        'US Soybean Oil': 'SoybeanOil',
        'US Wheat': 'Wheat',
    }
    try:
        resp = fetch('https://www.investing.com/commodities/real-time-futures')
        bs = BeautifulSoup(resp.text, 'lxml')
        tables = bs.find_all('table')
        if not tables:
            return results
        table = tables[0]
        rows = table.find_all('tr')
        for row in rows[1:]:
            cells = row.find_all('td')
            if len(cells) < 7:
                continue
            name = cells[1].get_text(' ', strip=True)
            name_clean = re.sub(r'\s*derived$', '', name).strip()
            if name_clean in wanted:
                code = wanted[name_clean]
                last = cells[3].get_text(strip=True)
                chg = cells[6].get_text(strip=True) if len(cells) > 6 else ''
                pct = cells[7].get_text(strip=True) if len(cells) > 7 else ''
                results[code] = {
                    'close': clean_num(last),
                    'change': clean_num(chg),
                    'change_pct': pct,
                    'source': 'Investing Futures',
                }
    except Exception as e:
        print(f"  WARN Commodities: {type(e).__name__}: {str(e)[:60]}", file=sys.stderr)
    return results


# ──────────────── STATE/JSON-BASED PARSERS ────────────────


def parse_instrument_page(url, label, code_name):
    result = {}
    try:
        resp = fetch(url)
        bs = BeautifulSoup(resp.text, 'lxml')
        for script in bs.find_all('script'):
            if script.get('id') == '__NEXT_DATA__':
                data = json.loads(script.string)
                state = data['props']['pageProps']['state']

                for store_key in ['commodityStore', 'indexStore', 'bondStore', 'currencyStore']:
                    store = state.get(store_key, {})
                    instrument = store.get('instrument', {})
                    if not instrument:
                        continue
                    price = instrument.get('price', {})
                    if price and price.get('last') is not None:
                        result = {
                            'close': str(price['last']),
                            'change': str(price.get('change', '')),
                            'change_pct': str(price.get('changePcr', '')),
                            'high': str(price.get('high', '')),
                            'low': str(price.get('low', '')),
                            'open': str(price.get('open', '')),
                            'prev_close': str(price.get('lastClose', '')),
                            'source': label,
                        }
                        break
                if not result:
                    quotes = state.get('quotesStore', {}).get('quotes', [])
                    if isinstance(quotes, list) and len(quotes) > 0:
                        q = quotes[0]
                        if q.get('last') is not None:
                            result = {
                                'close': str(q['last']),
                                'change': str(q.get('change', '')),
                                'change_pct': str(q.get('changePct', '')),
                                'source': label,
                            }
                break
    except Exception as e:
        print(f"  WARN {label}: {type(e).__name__}: {str(e)[:60]}", file=sys.stderr)
    return {code_name: result} if result else {}


def parse_icbi():
    result = {}
    try:
        resp = fetch('https://www.idx.co.id/en/market-data/bonds-sukuk/indobex')
        # Search for ICBI data directly in HTML - it's in a compressed NUXT format
        # Pattern: IndexCode:"ICBI (Indonesia Composite Bond Index)",IndexValue:NNNN.NNNN,IndexChgVal:±N.NNNN,IndexChgPct:±N.NNNN
        match = re.search(
            r'IndexCode:\"ICBI[^\"].*?\"[^}]*?IndexValue:([^,]+)[^}]*?IndexChgVal:([^,]+)[^}]*?IndexChgPct:([^,}]+)',
            resp.text
        )
        if match:
            result = {
                'ICBI': {
                    'close': str(match.group(1)).strip(),
                    'change': str(match.group(2)).strip(),
                    'change_pct': str(match.group(3)).strip(),
                    'source': 'IDX',
                }
            }
    except Exception as e:
        print(f"  WARN ICBI: {type(e).__name__}: {str(e)[:60]}", file=sys.stderr)
    return result


# ──────────────── YAHOO FINANCE ────────────────


def parse_yahoo_finance(ticker, code_name):
    result = {}
    try:
        url = f'https://finance.yahoo.com/quote/{ticker}/'
        resp = fetch(url)
        bs = BeautifulSoup(resp.text, 'lxml')
        # Find price - qsp-price is the ticker-specific element
        qsp = bs.find('span', {'data-testid': 'qsp-price'})
        price = qsp.get_text(strip=True) if qsp else None

        if not price:
            # Fallback: find fin-streamer for the specific ticker
            price_el = bs.find('fin-streamer', {'data-field': 'regularMarketPrice', 'data-symbol': ticker})
            if not price_el:
                price_el = bs.find('fin-streamer', {'data-field': 'regularMarketPrice'})
            price = price_el.get('data-value') or price_el.get_text(strip=True) if price_el else None

        # Get change and percent
        change_el = bs.find('fin-streamer', {'data-field': 'regularMarketChange'})
        pct_el = bs.find('fin-streamer', {'data-field': 'regularMarketChangePercent'})
        change = change_el.get('data-value') or change_el.get_text(strip=True) if change_el else ''
        pct = pct_el.get('data-value') or pct_el.get_text(strip=True) if pct_el else ''
        if price:
            price = price.replace(',', '')
            result = {
                code_name: {
                    'close': price,
                    'change': change or '',
                    'change_pct': f"{pct}%" if pct else '',
                    'source': 'Yahoo Finance',
                }
            }
    except Exception as e:
        print(f"  WARN {code_name} (Yahoo): {type(e).__name__}: {str(e)[:60]}", file=sys.stderr)
    return result


# ──────────────── YAHOO SECTOR INDICES ────────────────


def parse_yahoo_sector_indices():
    """
    Fetch all 12 IDX sector indices from Yahoo Finance.
    Some sectors (IDXENERGY.JK, IDXBASIC.JK, etc.) don't expose
    change/change% in HTML, so calculate from price - prev_close.
    """
    result = {}
    sectors = [
        ("IDXEnergy", "IDXENERGY.JK"),
        ("IDX BscMat", "IDXBASIC.JK"),
        ("IDXIndst", "IDXINDUST.JK"),
        ("IDXNONCYC", "IDXNONCYC.JK"),
        ("IDXHlthcare", "IDXHEALTH.JK"),
        ("IDXCYCLC", "IDXCYCLIC.JK"),
        ("IDX Tech", "IDXTECHNO.JK"),
        ("IDX Transprt", "IDXTRANS.JK"),
        ("IDX Infra", "IDXINFRA.JK"),
        ("IDX Finance", "IDXFINANCE.JK"),
        ("IDX Banking", "INFOBANK15.JK"),
        ("IDX Property", "IDXPROPERT.JK"),
    ]
    for code_name, ticker in sectors:
        try:
            resp = fetch(
                f'https://finance.yahoo.com/quote/{ticker}/',
                impersonate='chrome120', timeout=20,
            )
            soup = BeautifulSoup(resp.text, 'lxml')
            qsp = soup.find('span', {'data-testid': 'qsp-price'})
            price_str = qsp.get_text(strip=True).replace(',', '') if qsp else None
            if not price_str:
                pe = soup.find('fin-streamer', {'data-field': 'regularMarketPrice'})
                if pe and not pe.get('data-symbol'):
                    price_str = (pe.get('data-value', '') or
                                 pe.get_text(strip=True)).replace(',', '')
            if not price_str:
                continue
            price = price_str
            change = ''
            change_pct = ''
            prev_el = soup.find('fin-streamer', {'data-field': 'regularMarketPreviousClose'})
            if prev_el:
                prev_raw = prev_el.get('data-value', '') or prev_el.get_text(strip=True)
                prev_str = prev_raw.replace(',', '')
                if prev_str:
                    try:
                        p = float(price)
                        prev = float(prev_str)
                        diff = round(p - prev, 2)
                        pct = round((diff / prev) * 100, 2) if prev != 0 else 0
                        change = f"+{diff}" if diff >= 0 else str(diff)
                        change_pct = f"+{pct}%" if pct >= 0 else f"{pct}%"
                    except (ValueError, TypeError):
                        pass
            result[code_name] = {
                'close': price,
                'change': change,
                'change_pct': change_pct,
                'source': 'Yahoo Finance (Sector)',
            }
        except Exception as e:
            print(f"  WARN {code_name} (Yahoo Sector): {type(e).__name__}: {str(e)[:60]}", file=sys.stderr)
    return result


# ──────────────── BONDS ────────────────


def parse_indonesia_bonds():
    results = {}
    try:
        resp = fetch(
            'https://www.investing.com/rates-bonds/indonesia-government-bonds?'
            'maturity_from=40&maturity_to=290'
        )
        bs = BeautifulSoup(resp.text, 'lxml')
        tables = bs.find_all('table')
        if tables:
            table = tables[0]
            rows = table.find_all('tr')
            for row in rows:
                cells = row.find_all('td')
                if len(cells) >= 5:
                    name = cells[1].get_text(' ', strip=True)
                    if '10Y' in name or '10 Yr' in name:
                        results['Indo10Yr'] = {
                            'close': cells[2].get_text(strip=True),
                            'prev': cells[3].get_text(strip=True),
                            'source': 'Investing Bonds',
                        }
                        break
    except Exception as e:
        print(f"  WARN Indo Bonds: {type(e).__name__}: {str(e)[:60]}", file=sys.stderr)
    return results


# ──────────────── CNBC INOCD5 ────────────────


def parse_indonesia_cds():
    """Fetch Indonesia 5Y CDS from WorldGovernmentBonds.com API"""
    result = {}
    try:
        payload = {
            "GLOBALVAR": {
                "FUNCTION": "CDS",
                "DOMESTIC": True,
                "ENDPOINT": "https://www.worldgovernmentbonds.com/wp-json/common/v1/historical",
                "DATE_RIF": "2099-12-31",
                "DEBUG": True,
                "OBJ": {"UNIT": "", "DECIMAL": 2, "UNIT_DELTA": "%", "DECIMAL_DELTA": 2},
                "COUNTRY1": {
                    "SYMBOL": "39", "PAESE": "Indonesia",
                    "PAESE_UPPERCASE": "INDONESIA", "BANDIERA": "id",
                    "URL_PAGE": "indonesia",
                },
                "COUNTRY2": None,
                "OBJ1": {"DURATA_STRING": "5 Years", "DURATA": 60},
                "OBJ2": None,
            }
        }
        resp = req.post(
            'https://www.worldgovernmentbonds.com/wp-json/common/v1/historical',
            json=payload,
            headers={
                'Origin': 'https://www.worldgovernmentbonds.com',
                'Referer': 'https://www.worldgovernmentbonds.com/cds-historical-data/indonesia/5-years/',
                'X-Requested-With': 'XMLHttpRequest',
                'Content-Type': 'application/json',
            },
            impersonate='chrome120', timeout=20,
        )
        data = resp.json()
        if not data.get('success'):
            return result
        r = data['result']
        close = str(r['ultimoValore'])
        change = ''
        change_pct = ''
        html = r.get('htmlLatestChange', '')
        if html:
            soup = BeautifulSoup(html, 'lxml')
            for tr in soup.find_all('tr'):
                cells = tr.find_all('td')
                if len(cells) >= 5 and '1 Week' in cells[0].get_text(strip=True):
                    min_div = cells[2].find('div')
                    prev_val = min_div.get_text(strip=True) if min_div else ''
                    if prev_val:
                        try:
                            curr = float(close)
                            prev = float(prev_val)
                            diff = round(curr - prev, 2)
                            pc = round((diff / prev) * 100, 2) if prev != 0 else 0
                            change = f"+{diff}" if diff >= 0 else str(diff)
                            change_pct = f"+{pc}%" if pc >= 0 else f"{pc}%"
                        except (ValueError, TypeError):
                            change = cells[1].get_text(strip=True)
                            change_pct = change
                    break
        result['IndoCDS 5yr'] = {
            'close': close,
            'change': change,
            'change_pct': change_pct,
            'source': 'WorldGovernmentBonds',
        }
    except Exception as e:
        print(f"  WARN IndoCDS: {type(e).__name__}: {str(e)[:60]}", file=sys.stderr)
    return result


# ──────────────── AMMONIA ────────────────


def parse_ammonia():
    result = {}
    try:
        resp = fetch(
            'https://www.chemicalbook.com/PriceInfoall_CB9854275.htm',
            headers=ZH_HEADERS, timeout=15,
        )
        soup = BeautifulSoup(resp.text, 'lxml')
        entries = []
        for li in soup.find_all('li'):
            if li.get('class') and 'align_r' in li.get('class'):
                continue
            txt = li.get_text(' ', strip=True)
            m = re.search(r'(\d+月\d+日).*?氨.*?报价[:：]?(\d[\d,.]*)', txt)
            if m:
                entries.append({
                    'date': m.group(1),
                    'price': m.group(2).replace(',', ''),
                })
        if entries:
            latest = entries[0]
            close = latest['price']
            change = ''
            change_pct = ''
            if len(entries) >= 2:
                prev = entries[1]
                try:
                    c = float(close)
                    p = float(prev['price'])
                    diff = round(c - p, 2)
                    pc = round((diff / p) * 100, 2) if p != 0 else 0
                    change = f"+{diff}" if diff >= 0 else str(diff)
                    change_pct = f"+{pc}%" if pc >= 0 else f"{pc}%"
                except (ValueError, TypeError):
                    pass
            result['Ammonia'] = {
                'close': close,
                'change': change,
                'change_pct': change_pct,
                'date': latest['date'],
                'unit': 'Yuan/ton',
                'note': f"ChemicalBook ({entries[0]['date']})",
                'source': 'ChemicalBook',
            }
    except Exception as e:
        print(f"  WARN Ammonia: {type(e).__name__}: {str(e)[:60]}", file=sys.stderr)
    return result


# ──────────────── JISDOR ────────────────


def parse_jisdor():
    result = {}
    try:
        resp = fetch(
            'https://www.bi.go.id/id/statistik/informasi-kurs/jisdor/default.aspx',
            timeout=25,
        )
        soup = BeautifulSoup(resp.text, 'lxml')
        for td in soup.find_all('td'):
            txt = td.get_text(strip=True)
            m = re.match(r'Rp(\d{2,3}\.\d{3})[,\s]', txt)
            if m:
                result['Jisdor'] = {
                    'close': m.group(1).replace('.', ','),
                    'source': 'BI',
                }
                break
    except Exception as e:
        print(f"  WARN JISDOR: {type(e).__name__}: {str(e)[:60]}", file=sys.stderr)
    return result

# ──────────────── DXY from CNBC ────────────────


def parse_cnbc_dxy():
    result = {}
    try:
        resp = fetch(
            'https://www.cnbc.com/quotes/.DXY',
            impersonate='chrome120',
            timeout=20,
        )
        soup = BeautifulSoup(resp.text, 'lxml')
        body = soup.find('body')
        body_txt = body.get_text(' ', strip=True) if body else ''

        # Parse: "Last | 06/09/26 EDT 99.995 -0.05 ( -0.05% )"
        m = re.search(r'Last\s*\|.*?(\d{2,3}\.\d{3})\s+([+-]?\d+\.\d+)\s*\(\s*([+-]?\d+\.\d+)%\)', body_txt)
        if m:
            result['USDIndx'] = {
                'close': m.group(1),
                'change': m.group(2),
                'change_pct': m.group(3) + '%',
                'source': 'CNBC',
            }
        else:
            # Fallback: just get the price (even if change is UNCH)
            nums = re.findall(r'(\d{2,3}\.\d{3})', body_txt)
            if nums:
                result['USDIndx'] = {
                    'close': nums[0],
                    'change': '',
                    'change_pct': '',
                    'source': 'CNBC',
                }
    except Exception as e:
        print(f"  WARN DXY: {type(e).__name__}: {str(e)[:60]}", file=sys.stderr)
    return result


def parse_barchart_coal():
    """Fetch all coal futures contracts from Barchart"""
    result = {}
    month_codes = {
        "Jun": "M",
        "Jul": "N",
        "Aug": "Q",
        "Sep": "U",
    }
    
    for root_name, root_sym, label in [
        ("Newcastle", "LQ", "Coal(Nwl)"),
        ("Rotterdam", "LU", "Coal(Rot)"),
    ]:
        contracts = []
        for month_name, code in month_codes.items():
            sym = f"{root_sym}{code}26"
            try:
                resp = fetch(
                    f'https://www.barchart.com/futures/quotes/{sym}/overview',
                    impersonate='chrome120',
                    timeout=20,
                )
                soup = BeautifulSoup(resp.text, 'lxml')
                tables = soup.find_all('table')
                for table in tables:
                    rows = table.find_all('tr')
                    if rows and len(rows) > 1:
                        cells = rows[1].find_all('td')
                        if len(cells) >= 3 and cells[0].get_text(strip=True) == sym:
                            price_raw = cells[1].get_text(strip=True).replace('s', '').replace(',', '')
                            chg_raw = cells[2].get_text(strip=True).replace(',', '')
                            try:
                                price = float(price_raw)
                                chg = float(chg_raw)
                                prev_close = price - chg
                                pct = round((chg / prev_close) * 100, 2) if prev_close else 0
                                contracts.append({
                                    'month': month_name,
                                    'price': f"{price:.2f}",
                                    'change': f"{chg:+.2f}",
                                    'change_pct': f"{pct:+.2f}%",
                                })
                            except:
                                pass
                            break
            except Exception as e:
                pass
        
        if contracts:
            # Store as array for the main script to format
            result[label] = {
                'contracts': contracts,
                'source': 'Barchart',
            }
    
    return result

def main():
    debug = '--json-only' not in sys.argv
    if debug:
        print("Regional Screener -- collecting data...", file=sys.stderr)
    t0 = datetime.now()

    # 1. Major Indices
    if debug:
        print("Major Indices...", file=sys.stderr)
    DATA.update(parse_table_pages([
        ('Major Indices', 'https://www.investing.com/indices/major-indices', 1, 2, 5, 6),
    ]))

    # 2. Indonesia Indices (include all tabs: major, additional, primary sectors, other)
    if debug:
        print("IDX Indices...", file=sys.stderr)
    DATA.update(parse_table_pages([
        ('IDX Indices', 'https://www.investing.com/indices/indonesia-indices?include-major-indices=true&include-additional-indices=true&include-primary-sectors=true&include-other-indices=true', 1, 2, 5, 6),
    ]))

    # 3. Commodities Futures
    if debug:
        print("Commodities...", file=sys.stderr)
    DATA.update(parse_commodities_futures())




    # 3b. Coal futures from Barchart
    if debug:
        print("Coal from Barchart...", file=sys.stderr)
    DATA.update(parse_barchart_coal())

    # 4. Single-instrument pages
    single_pages = [
        ('Iron Ore', 'https://www.investing.com/commodities/iron-ore-62-cfr-futures', 'Iron Ore 62%'),
        ('CPO', 'https://id.investing.com/commodities/malaysian-crude-palm-oil-futures', 'CPO'),
        ('Woodpulp', 'https://id.investing.com/commodities/shfe-bleached-softwood-kraft-pulp-futures', 'Woodpulp'),
        ('Tin', 'https://www.investing.com/commodities/tin', 'Timah'),
        ('BCOMIN', 'https://www.investing.com/indices/bloomberg-industrial-metals', 'BCOMIN'),
        ('COMIN', 'https://www.investing.com/indices/commodity-index', 'Como Indx'),
        ('USD/IDR', 'https://www.investing.com/currencies/usd-idr', 'IDR'),
        ('EUR/USD', 'https://www.investing.com/currencies/eur-usd', 'Euro'),
        ('Gold Spot', 'https://www.investing.com/currencies/xau-usd', 'Gold(Spot)'),
    ]
    for label, url, code in single_pages:
        if debug:
            print(f"  {label}...", file=sys.stderr)
        DATA.update(parse_instrument_page(url, label, code))

    # 5. US Bonds
    if debug:
        print("US Bonds...", file=sys.stderr)
    DATA.update(parse_table_pages([
        ('US Bonds', 'https://www.investing.com/rates-bonds/usa-government-bonds', 1, 2, -1, -1),
    ]))

    # 6. Indonesia Bonds
    if debug:
        print("Indo Bonds...", file=sys.stderr)
    DATA.update(parse_indonesia_bonds())

    # 7. ICBI
    if debug:
        print("ICBI...", file=sys.stderr)
    DATA.update(parse_icbi())

    # 8. Yahoo Finance
    if debug:
        print("Yahoo Finance...", file=sys.stderr)
    for ticker, code in [('^VIX', 'VIX'),
                          ('TLK', 'TLKM'), ('EIDO', 'EIDO'), ('EEM', 'EEM')]:
        if debug:
            print(f"  {code}...", file=sys.stderr)
        DATA.update(parse_yahoo_finance(ticker, code))

    # 8b. IDX Sector Indices (Yahoo Finance)
    if debug:
        print("IDX Sector Indices...", file=sys.stderr)
    DATA.update(parse_yahoo_sector_indices())

    # 9. DXY (CNBC)
    if debug:
        print("DXY.. CNBC...", file=sys.stderr)
    DATA.update(parse_cnbc_dxy())

    # 10. IndoCDS
    if debug:
        print("IndoCDS...", file=sys.stderr)
    DATA.update(parse_indonesia_cds())

    # 10. Ammonia
    if debug:
        print("Ammonia...", file=sys.stderr)
    DATA.update(parse_ammonia())

    # 11. JISDOR
    if debug:
        print("JISDOR...", file=sys.stderr)
    DATA.update(parse_jisdor())

    # ── OUTPUT ──
    elapsed = (datetime.now() - t0).total_seconds()
    result = {
        'timestamp': datetime.now().isoformat(),
        'elapsed_seconds': round(elapsed, 1),
        'items_count': len(DATA),
        'data': DATA,
        'sources_used': sorted(set(
            v.get('source', 'unknown') for v in DATA.values() if isinstance(v, dict)
        )),
    }
    print(json.dumps(result, indent=2, ensure_ascii=False))
    if debug:
        print(f"\nDone in {elapsed:.1f}s -- {len(DATA)} items collected", file=sys.stderr)


if __name__ == '__main__':
    main()
