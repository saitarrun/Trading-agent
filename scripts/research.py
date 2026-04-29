import os
import requests
from datetime import datetime, timedelta
import json
from dotenv import load_dotenv

load_dotenv()

ALPACA_KEY = os.getenv("APCA_API_KEY_ID")
ALPACA_SECRET = os.getenv("APCA_API_SECRET_KEY")
BASE_URL = os.getenv("APCA_BASE_URL")

def _bars_from_yfinance(symbol, limit=60):
    """Fallback: fetch bars from yfinance and normalise to Alpaca bar format."""
    try:
        import yfinance as yf
        period_map = {5: "5d", 20: "1mo", 60: "3mo", 100: "6mo", 200: "1y"}
        period = next((v for k, v in sorted(period_map.items()) if limit <= k), "1y")
        ticker = yf.Ticker(symbol)
        hist = ticker.history(period=period, interval="1d", auto_adjust=False)
        if hist.empty:
            return {}
        bars = [
            {"t": str(idx.date()), "o": row["Open"], "h": row["High"],
             "l": row["Low"], "c": row["Close"], "v": row["Volume"]}
            for idx, row in hist.tail(limit).iterrows()
        ]
        return {"bars": bars, "symbol": symbol, "source": "yfinance"}
    except Exception as e:
        print(f"[RESEARCH] yfinance fallback failed for {symbol}: {e}")
        return {}

def get_bars(symbol, timeframe="1Day", limit=60):
    """Fetch historical price bars. Falls back to yfinance if Alpaca data API unavailable."""
    headers = {
        "APCA-API-KEY-ID": ALPACA_KEY,
        "APCA-API-SECRET-KEY": ALPACA_SECRET,
    }
    url = f"https://data.alpaca.markets/v2/stocks/{symbol}/bars"
    params = {"timeframe": timeframe, "limit": limit, "adjustment": "raw"}
    try:
        response = requests.get(url, headers=headers, params=params, timeout=10)
        if response.status_code == 200:
            return response.json()
        print(f"[RESEARCH] Alpaca data API {response.status_code} for {symbol}, trying yfinance fallback")
    except Exception as e:
        print(f"[RESEARCH] Alpaca data API unreachable for {symbol} ({e}), trying yfinance fallback")
    return _bars_from_yfinance(symbol, limit)

def get_account():
    """Get current portfolio status. Returns safe defaults if Alpaca API unavailable."""
    headers = {
        "APCA-API-KEY-ID": ALPACA_KEY,
        "APCA-API-SECRET-KEY": ALPACA_SECRET,
    }
    url = f"{BASE_URL}/v2/account"
    try:
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            return response.json()
        print(f"[RESEARCH] Alpaca account API returned {response.status_code}, using defaults")
    except Exception as e:
        print(f"[RESEARCH] Alpaca account API unreachable ({e}), using defaults")
    return {"portfolio_value": "100000", "cash": "100000", "account_number": "PAPER_OFFLINE", "source": "default"}

def get_positions():
    """Get all open positions. Returns empty list if Alpaca API unavailable."""
    headers = {
        "APCA-API-KEY-ID": ALPACA_KEY,
        "APCA-API-SECRET-KEY": ALPACA_SECRET,
    }
    url = f"{BASE_URL}/v2/positions"
    try:
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            return response.json()
        print(f"[RESEARCH] Alpaca positions API returned {response.status_code}, returning empty positions")
    except Exception as e:
        print(f"[RESEARCH] Alpaca positions API unreachable ({e}), returning empty positions")
    return []

def get_news(symbol):
    """Get recent news for a symbol."""
    headers = {
        "APCA-API-KEY-ID": ALPACA_KEY,
        "APCA-API-SECRET-KEY": ALPACA_SECRET,
    }
    url = f"https://data.alpaca.markets/v1beta1/news"
    params = {
        "symbols": symbol,
        "limit": 5,
        "sort": "desc"
    }
    response = requests.get(url, headers=headers, params=params)
    return response.json()

if __name__ == "__main__":
    import sys
    action = sys.argv[1] if len(sys.argv) > 1 else "account"
    symbol = sys.argv[2] if len(sys.argv) > 2 else None

    if action == "bars" and symbol:
        print(json.dumps(get_bars(symbol)))
    elif action == "news" and symbol:
        print(json.dumps(get_news(symbol)))
    elif action == "positions":
        print(json.dumps(get_positions()))
    else:
        print(json.dumps(get_account()))
