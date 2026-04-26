import requests
import json
from datetime import datetime, timezone, timedelta

def fetch_live_polymarket_data(limit=1000):
    """
    Fetches live market data from Polymarket Gamma API.
    URL: https://gamma-api.polymarket.com/events?limit=1000&active=true&closed=false
    """
    max_date = (datetime.now(timezone.utc) + timedelta(hours=24)).strftime('%Y-%m-%dT%H:%M:%SZ')
    url = f"https://gamma-api.polymarket.com/events?limit={limit}&active=true&closed=false&end_date_max={max_date}&order=end_date_asc"
    try:
        response = requests.get(url)
        response.raise_for_status()
        markets = response.json()
        print(f'[SYSTEM] Fetched {len(markets)} raw markets from API.')
        
        live_data = []
        for event in markets:
            # Polymarket events can have multiple markets. Find the first active and non-closed one.
            event_markets = event.get("markets", [])
            active_market = None
            for m in event_markets:
                if m.get("active") and not m.get("closed"):
                    active_market = m
                    break
            
            if not active_market:
                continue
            
            # Use the raw question from the market if it exists, otherwise the event title
            title = active_market.get("question") or event.get("title", "Unknown Event")
            volume = float(event.get("volume", 0))
            
            outcome_prices = json.loads(active_market.get("outcomePrices", "[]"))
            
            # Usually index 0 is 'Yes' or the first outcome
            price = 0.5 # Default
            if outcome_prices:
                try:
                    price = float(outcome_prices[0])
                except (ValueError, IndexError):
                    pass
            
            # Calculate expiry_hours
            end_date_str = active_market.get("endDate") or event.get("endDate")
            expiry_hours = 0
            if end_date_str:
                try:
                    # Handle Z or +00:00
                    if end_date_str.endswith('Z'):
                        end_date_str = end_date_str[:-1] + '+00:00'
                    end_date = datetime.fromisoformat(end_date_str)
                    now = datetime.now(timezone.utc)
                    diff = end_date - now
                    expiry_hours = diff.total_seconds() / 3600
                except ValueError:
                    expiry_hours = 0
                    
            if not (0 < expiry_hours <= 24):
                continue

            live_data.append({
                "title": title,
                "odds": f"{int(price * 100)}%",
                "price": price,
                "volume": volume,
                "volume_24h": float(event.get("volume24hr", 0)),
                "expiry_hours": max(0, expiry_hours),
                "expiry_timestamp": end_date.timestamp() if end_date_str and 'end_date' in locals() else None,
                "category": event.get("category", "Other"),
                "predicted_profit_pct": 0.10 # Placeholder for model prediction
            })
            
        return live_data
    except Exception as e:
        print(f"Error fetching Polymarket data: {e}")
        return []

if __name__ == "__main__":
    data = fetch_live_polymarket_data()
    for d in data:
        print(d)
    print(d)
