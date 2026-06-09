import requests
import json

r = requests.post("http://localhost:5000/analyze", data={"ticker": "TSLA", "force_refresh": "true"})
data = r.json()
print("Status:", data.get("status"))
print("DCF Fair Price:", data.get("fundamental", {}).get("fair_price_dcf", "N/A"))
print("Last Price:", data.get("last_price"))
print()

# Also test with another ticker that has simpler financials
r2 = requests.post("http://localhost:5000/analyze", data={"ticker": "TLKM.JK", "force_refresh": "true"})
data2 = r2.json()
print("=== TLKM.JK ===")
print("Status:", data2.get("status"))
print("DCF Fair Price:", data2.get("fundamental", {}).get("fair_price_dcf", "N/A"))
print("Last Price:", data2.get("last_price"))
