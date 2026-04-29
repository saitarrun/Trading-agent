import os
import requests
import json
import sys
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

ALPACA_KEY = os.getenv("APCA_API_KEY_ID")
ALPACA_SECRET = os.getenv("APCA_API_SECRET_KEY")
BASE_URL = os.getenv("APCA_BASE_URL")

def place_order(symbol, qty, side, limit_price=None):
    """Place a buy or sell order."""
    headers = {
        "APCA-API-KEY-ID": ALPACA_KEY,
        "APCA-API-SECRET-KEY": ALPACA_SECRET,
        "Content-Type": "application/json"
    }

    order_data = {
        "symbol": symbol,
        "qty": qty,
        "side": side,
        "type": "limit" if limit_price else "market",
        "time_in_force": "day",
    }

    if limit_price:
        order_data["limit_price"] = str(limit_price)

    url = f"{BASE_URL}/v2/orders"
    response = requests.post(url, headers=headers, json=order_data)
    return response.json()

def cancel_all_orders():
    """Cancel all open orders."""
    headers = {
        "APCA-API-KEY-ID": ALPACA_KEY,
        "APCA-API-SECRET-KEY": ALPACA_SECRET,
    }
    url = f"{BASE_URL}/v2/orders"
    response = requests.delete(url, headers=headers)
    return response.status_code

def _market_status_from_clock():
    """Derive market open/closed from current ET time without hitting the broker API."""
    from datetime import timezone, timedelta
    et = timezone(timedelta(hours=-4))  # EDT; close enough for open/closed check
    now = datetime.now(et)
    is_weekday = now.weekday() < 5
    market_open_time = now.replace(hour=9, minute=30, second=0, microsecond=0)
    market_close_time = now.replace(hour=16, minute=0, second=0, microsecond=0)
    is_open = is_weekday and market_open_time <= now < market_close_time
    from datetime import timedelta
    next_open = (now + timedelta(days=1)).replace(hour=9, minute=30, second=0, microsecond=0).isoformat()
    return {"is_open": is_open, "next_open": next_open, "source": "local_clock"}

def get_market_status():
    """Check if the market is open. Falls back to local clock if Alpaca API unavailable."""
    headers = {
        "APCA-API-KEY-ID": ALPACA_KEY,
        "APCA-API-SECRET-KEY": ALPACA_SECRET,
    }
    url = f"{BASE_URL}/v2/clock"
    try:
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            return response.json()
        print(f"[TRADE] Alpaca clock API returned {response.status_code}, falling back to local clock")
    except Exception as e:
        print(f"[TRADE] Alpaca clock API unreachable ({e}), falling back to local clock")
    return _market_status_from_clock()

def validate_order(symbol, qty, side, current_price, account_value, current_positions):
    """Pre-flight checks before placing any order."""
    order_value = qty * current_price
    allocation_pct = (order_value / account_value) * 100

    # Check max position size
    if allocation_pct > 10:
        return False, f"Order exceeds 10% allocation limit: {allocation_pct:.1f}%"

    # Check total exposure (positions + this order < 80%)
    total_invested = sum(float(p.get('market_value', 0)) for p in current_positions)
    if (total_invested + order_value) / account_value > 0.80:
        return False, "Order would violate 20% cash reserve requirement"

    return True, "Order validated"

if __name__ == "__main__":
    action = sys.argv[1]

    if action == "status":
        print(json.dumps(get_market_status()))
    elif action == "order":
        symbol = sys.argv[2]
        qty = sys.argv[3]
        side = sys.argv[4]
        limit_price = sys.argv[5] if len(sys.argv) > 5 else None
        print(json.dumps(place_order(symbol, qty, side, limit_price)))
    elif action == "cancel":
        print(cancel_all_orders())
