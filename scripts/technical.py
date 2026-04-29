"""Technical analysis: indicators, patterns, Fibonacci levels."""

import numpy as np
import pandas as pd
from datetime import datetime
import json

class TechnicalAnalyzer:
    """Calculate technical indicators and detect patterns."""

    def __init__(self, bars):
        """
        Args:
            bars: List of dicts with 'c' (close), 'h' (high), 'l' (low), 'v' (volume)
        """
        self.bars = bars
        self.df = self._build_dataframe()

    def _build_dataframe(self):
        """Convert bar list to DataFrame for easier computation."""
        data = {
            'close': [b['c'] for b in self.bars],
            'high': [b['h'] for b in self.bars],
            'low': [b['l'] for b in self.bars],
            'volume': [b.get('v', 0) for b in self.bars]
        }
        return pd.DataFrame(data)

    def calculate_rsi(self, period=14):
        """Relative Strength Index (0-100)."""
        delta = self.df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()

        rs = gain / loss.replace(0, 1e-9)
        rsi = 100 - (100 / (1 + rs))
        return float(rsi.iloc[-1]) if len(rsi) > 0 else 50

    def calculate_macd(self, fast=12, slow=26, signal=9):
        """MACD indicator (momentum)."""
        ema_fast = self.df['close'].ewm(span=fast).mean()
        ema_slow = self.df['close'].ewm(span=slow).mean()

        macd_line = ema_fast - ema_slow
        signal_line = macd_line.ewm(span=signal).mean()
        histogram = macd_line - signal_line

        return {
            'macd': float(macd_line.iloc[-1]) if len(macd_line) > 0 else 0,
            'signal': float(signal_line.iloc[-1]) if len(signal_line) > 0 else 0,
            'histogram': float(histogram.iloc[-1]) if len(histogram) > 0 else 0,
            'bullish': float(macd_line.iloc[-1]) > float(signal_line.iloc[-1])
        }

    def find_support_resistance(self, lookback=20):
        """Find recent support (local low) and resistance (local high)."""
        recent_data = self.df['close'].tail(lookback)

        support = float(recent_data.min())
        resistance = float(recent_data.max())

        current_price = float(self.df['close'].iloc[-1])
        distance_to_support = (current_price - support) / current_price
        distance_to_resistance = (resistance - current_price) / current_price

        return {
            'support': support,
            'resistance': resistance,
            'current_price': current_price,
            'distance_to_support_pct': distance_to_support * 100,
            'distance_to_resistance_pct': distance_to_resistance * 100
        }

    def calculate_fibonacci(self, swing_low=None, swing_high=None):
        """Calculate Fibonacci retracement levels."""
        if swing_low is None:
            swing_low = float(self.df['low'].min())
        if swing_high is None:
            swing_high = float(self.df['high'].max())

        diff = swing_high - swing_low

        levels = {
            '0%': swing_high,
            '23.6%': swing_high - (diff * 0.236),
            '38.2%': swing_high - (diff * 0.382),
            '50%': swing_high - (diff * 0.5),
            '61.8%': swing_high - (diff * 0.618),
            '78.6%': swing_high - (diff * 0.786),
            '100%': swing_low
        }

        return levels

    def detect_trend(self, period=20):
        """Simple trend detection (up/down/sideways)."""
        close_prices = self.df['close'].tail(period)

        if len(close_prices) < period:
            return "unknown"

        sma = close_prices.rolling(window=period).mean().iloc[-1]
        current = close_prices.iloc[-1]

        trend_strength = (current - sma) / sma if sma != 0 else 0

        if trend_strength > 0.02:
            return "uptrend"
        elif trend_strength < -0.02:
            return "downtrend"
        else:
            return "sideways"

    def detect_overbought_oversold(self):
        """Check if price is overbought (RSI>70) or oversold (RSI<30)."""
        rsi = self.calculate_rsi()

        if rsi > 70:
            return "overbought"
        elif rsi < 30:
            return "oversold"
        else:
            return "neutral"

    def calculate_moving_averages(self, periods=[20, 50, 200]):
        """Calculate simple moving averages."""
        mas = {}
        for period in periods:
            if len(self.df) >= period:
                ma = float(self.df['close'].rolling(window=period).mean().iloc[-1])
                mas[f'sma_{period}'] = ma
            else:
                mas[f'sma_{period}'] = None

        return mas

    def analyze(self):
        """Run complete technical analysis."""
        if len(self.bars) < 2:
            return None

        rsi = self.calculate_rsi()
        macd = self.calculate_macd()
        sr = self.find_support_resistance()
        fib = self.calculate_fibonacci()
        trend = self.detect_trend()
        overbought_oversold = self.detect_overbought_oversold()
        mas = self.calculate_moving_averages()

        # Generate trade signal
        signal = self._generate_signal(rsi, macd, trend, overbought_oversold)

        return {
            'rsi': rsi,
            'macd': macd,
            'support_resistance': sr,
            'fibonacci_levels': fib,
            'trend': trend,
            'overbought_oversold': overbought_oversold,
            'moving_averages': mas,
            'trade_signal': signal,
            'timestamp': datetime.now().isoformat()
        }

    def _generate_signal(self, rsi, macd, trend, overbought_oversold):
        """Generate buy/sell/hold signal from indicators."""
        score = 0

        # MACD bullish
        if macd['bullish']:
            score += 1

        # RSI not overbought
        if rsi < 70:
            score += 0.5
        if rsi < 30:
            score += 1

        # Trend alignment
        if trend == "uptrend":
            score += 1
        elif trend == "downtrend":
            score -= 1

        # Overbought/oversold
        if overbought_oversold == "oversold":
            score += 1
        elif overbought_oversold == "overbought":
            score -= 1

        if score >= 2:
            return "buy"
        elif score <= -1:
            return "sell"
        else:
            return "hold"


if __name__ == "__main__":
    # Test with sample data
    sample_bars = [
        {'c': 100 + i, 'h': 101 + i, 'l': 99 + i, 'v': 1000000}
        for i in range(50)
    ]

    analyzer = TechnicalAnalyzer(sample_bars)
    result = analyzer.analyze()
    print(json.dumps(result, indent=2, default=str))
