import json
from datetime import datetime, timedelta, timezone

import requests


def fetch_live_polymarket_data(limit=1000):
    max_date = (datetime.now(timezone.utc) + timedelta(hours=24)).strftime("%Y-%m-%dT%H:%M:%SZ")
    url = (
        "https://gamma-api.polymarket.com/events"
        f"?limit={limit}&active=true&closed=false&end_date_max={max_date}&order=end_date_asc"
    )
    try:
        response = requests.get(url, timeout=15)
        response.raise_for_status()
        markets = response.json()
        print(f"[SYSTEM] Fetched {len(markets)} raw markets from API.")

        live_data = []
        for event in markets:
            event_markets = event.get("markets", [])
            active_market = None
            for market in event_markets:
                if market.get("active") and not market.get("closed"):
                    active_market = market
                    break

            if not active_market:
                continue

            title = active_market.get("question") or event.get("title", "Unknown Event")
            volume = float(event.get("volume", 0))
            outcome_prices = json.loads(active_market.get("outcomePrices", "[]"))

            price = 0.5
            if outcome_prices:
                try:
                    price = float(outcome_prices[0])
                except (ValueError, IndexError):
                    pass

            end_date_str = active_market.get("endDate") or event.get("endDate")
            expiry_hours = 0
            end_date = None
            if end_date_str:
                try:
                    if end_date_str.endswith("Z"):
                        end_date_str = end_date_str[:-1] + "+00:00"
                    end_date = datetime.fromisoformat(end_date_str)
                    now = datetime.now(timezone.utc)
                    diff = end_date - now
                    expiry_hours = diff.total_seconds() / 3600
                except ValueError:
                    expiry_hours = 0

            if not (0 < expiry_hours <= 24):
                continue

            event_id = event.get("id") or event.get("slug")
            market_id = active_market.get("conditionId") or active_market.get("questionID") or active_market.get("id") or event_id
            token_id = None
            clob_tokens_str = active_market.get("clobTokenIds", "[]")
            if clob_tokens_str:
                if isinstance(clob_tokens_str, list) and len(clob_tokens_str) > 0:
                    token_id = clob_tokens_str[0]
                elif isinstance(clob_tokens_str, str):
                    try:
                        clob_tokens = json.loads(clob_tokens_str)
                    except json.JSONDecodeError:
                        import ast
                        try:
                            clob_tokens = ast.literal_eval(clob_tokens_str)
                        except (ValueError, TypeError, SyntaxError):
                            clob_tokens = []
                    
                    if isinstance(clob_tokens, list) and len(clob_tokens) > 0:
                        token_id = clob_tokens[0]

            live_data.append(
                {
                    "event_id": event_id,
                    "market_id": market_id,
                    "token_id": token_id,
                    "title": title,
                    "odds": f"{int(price * 100)}%",
                    "price": price,
                    "volume": volume,
                    "volume_24h": float(event.get("volume24hr", 0)),
                    "expiry_hours": max(0, expiry_hours),
                    "expiry_timestamp": end_date.timestamp() if end_date else None,
                    "category": event.get("category", "Other"),
                    "predicted_profit_pct": 0.10,
                }
            )

        return live_data
    except Exception as e:
        print(f"Error fetching Polymarket data: {e}")
        return []
