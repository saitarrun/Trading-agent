"""Adaptive trading strategies: trend, range, breakout, reversal, momentum."""

import numpy as np
import pandas as pd
from datetime import datetime
import json

class StrategySelector:
    """Select and execute appropriate trading strategy based on market conditions."""

    def __init__(self, bars, regime=None, performance_tracker=None):
        """
        Args:
            bars: List of dicts with 'c' (close), 'h' (high), 'l' (low), 'v' (volume)
            regime: Current market regime (for performance feedback)
            performance_tracker: PerformanceTracker instance for confidence adjustment
        """
        self.bars = bars
        self.regime = regime
        self.performance_tracker = performance_tracker
        self.df = self._build_dataframe()

    def _build_dataframe(self):
        """Convert bars to DataFrame."""
        data = {
            'close': [b['c'] for b in self.bars],
            'high': [b['h'] for b in self.bars],
            'low': [b['l'] for b in self.bars],
            'volume': [b.get('v', 0) for b in self.bars]
        }
        return pd.DataFrame(data)

    def calculate_volatility(self, period=20):
        """Calculate historical volatility."""
        returns = self.df['close'].pct_change()
        volatility = returns.rolling(window=period).std().iloc[-1]
        return float(volatility) if not np.isnan(volatility) else 0

    def calculate_rate_of_change(self, period=12):
        """Rate of Change (ROC): measures speed of price movement."""
        if len(self.df) < period + 1:
            return 0
        current = self.df['close'].iloc[-1]
        past = self.df['close'].iloc[-(period+1)]
        roc = ((current - past) / past) * 100
        return float(roc)

    def detect_bull_market(self, lookback=252):
        """Detect bull market (sustained uptrend, 20%+ rise)."""
        if len(self.df) < lookback:
            lookback = len(self.df)

        start_price = self.df['close'].iloc[-lookback]
        current_price = self.df['close'].iloc[-1]
        gain = (current_price - start_price) / start_price

        return gain > 0.20, gain

    def detect_bear_market(self, lookback=252):
        """Detect bear market (sustained downtrend, 20%+ decline)."""
        if len(self.df) < lookback:
            lookback = len(self.df)

        start_price = self.df['close'].iloc[-lookback]
        current_price = self.df['close'].iloc[-1]
        decline = (current_price - start_price) / start_price

        return decline < -0.20, decline

    def detect_correction(self, lookback=252):
        """Detect correction (10-20% decline from peak)."""
        if len(self.df) < lookback:
            lookback = len(self.df)

        recent_high = self.df['close'].iloc[-lookback:].max()
        current = self.df['close'].iloc[-1]
        drawdown = (current - recent_high) / recent_high

        return -0.20 < drawdown < -0.10, drawdown

    def detect_breakout(self, lookback=30):
        """Detect breakout above resistance."""
        if len(self.df) < lookback:
            return False, 0

        recent_high = self.df['high'].iloc[-lookback:].max()
        current = self.df['close'].iloc[-1]

        breakout_amount = (current - recent_high) / recent_high
        is_breakout = current > recent_high

        return is_breakout, breakout_amount

    def detect_range_market(self, lookback=30):
        """Detect range-bound market (oscillating between support/resistance)."""
        if len(self.df) < lookback:
            return False, 0, 0

        recent_high = self.df['high'].iloc[-lookback:].max()
        recent_low = self.df['low'].iloc[-lookback:].min()
        current = self.df['close'].iloc[-1]

        range_width = recent_high - recent_low
        distance_from_high = (recent_high - current) / range_width if range_width > 0 else 0
        distance_from_low = (current - recent_low) / range_width if range_width > 0 else 0

        # Range market: price oscillating, not near boundaries
        is_range = 0.3 < distance_from_low < 0.7

        return is_range, distance_from_low, distance_from_high

    def detect_reversal(self, lookback=20):
        """Detect potential reversal points."""
        if len(self.df) < lookback:
            return None, 0

        recent_prices = self.df['close'].iloc[-lookback:]
        if recent_prices.iloc[-1] == recent_prices.min():
            return "bottom_reversal", (recent_prices.max() - recent_prices.iloc[-1]) / recent_prices.iloc[-1]
        elif recent_prices.iloc[-1] == recent_prices.max():
            return "top_reversal", (recent_prices.iloc[-1] - recent_prices.min()) / recent_prices.min()

        return None, 0

    def _adjust_confidence_for_performance(self, strategy_name, base_confidence):
        """Adjust confidence based on historical performance."""
        if not self.performance_tracker or not self.regime:
            return base_confidence
        return self.performance_tracker.adjust_strategy_confidence(strategy_name, self.regime, base_confidence)

    def select_strategy(self):
        """Intelligently select trading strategy based on current market conditions."""
        volatility = self.calculate_volatility()
        roc = self.calculate_rate_of_change()
        is_bull, bull_gain = self.detect_bull_market()
        is_bear, bear_decline = self.detect_bear_market()
        is_correction, correction_pct = self.detect_correction()
        is_breakout, breakout_amt = self.detect_breakout()
        is_range, dist_low, dist_high = self.detect_range_market()
        reversal_type, reversal_strength = self.detect_reversal()

        # Strategy selection logic
        if is_bull and not is_correction:
            base_conf = 0.9 if roc > 2 else 0.7
            return "trend_trading", {
                'description': 'Bullish trend - follow upside momentum',
                'confidence': self._adjust_confidence_for_performance("trend_trading", base_conf),
                'roc': roc,
                'action': 'Buy dips, hold strength'
            }

        if is_bear:
            base_conf = 0.9 if roc < -2 else 0.7
            return "trend_trading", {
                'description': 'Bearish trend - reduce exposure',
                'confidence': self._adjust_confidence_for_performance("trend_trading", base_conf),
                'roc': roc,
                'action': 'Avoid new longs, consider shorts'
            }

        if is_breakout and volatility < 0.05:
            base_conf = 0.85
            return "breakout_trading", {
                'description': 'Breakout opportunity from consolidation',
                'confidence': self._adjust_confidence_for_performance("breakout_trading", base_conf),
                'volatility': volatility,
                'action': 'Enter on close above resistance'
            }

        if is_range and volatility < 0.04:
            base_conf = 0.8
            return "range_trading", {
                'description': 'Range-bound market',
                'confidence': self._adjust_confidence_for_performance("range_trading", base_conf),
                'distance_to_support': dist_low,
                'distance_to_resistance': dist_high,
                'action': 'Buy near support, sell near resistance'
            }

        if reversal_type == "bottom_reversal" and reversal_strength > 0.05:
            base_conf = 0.75
            return "reversal_trading", {
                'description': 'Potential bottom reversal',
                'confidence': self._adjust_confidence_for_performance("reversal_trading", base_conf),
                'reversal_strength': reversal_strength,
                'action': 'Watch for confirmation, buy breakout'
            }

        if reversal_type == "top_reversal":
            base_conf = 0.7
            return "reversal_trading", {
                'description': 'Potential top reversal',
                'confidence': self._adjust_confidence_for_performance("reversal_trading", base_conf),
                'reversal_strength': reversal_strength,
                'action': 'Take profits, reduce exposure'
            }

        if is_correction and abs(roc) > 1:
            base_conf = 0.75
            return "momentum_trading", {
                'description': 'Strong momentum despite pullback',
                'confidence': self._adjust_confidence_for_performance("momentum_trading", base_conf),
                'roc': roc,
                'action': 'Buy dip in strong uptrend'
            }

        # Default
        return "hold", {
            'description': 'Indeterminate market conditions',
            'confidence': 0.5,
            'action': 'Wait for clearer signal'
        }

    def analyze(self):
        """Complete strategy analysis."""
        if len(self.bars) < 20:
            return None

        volatility = self.calculate_volatility()
        roc = self.calculate_rate_of_change()
        is_bull, bull_gain = self.detect_bull_market()
        is_bear, bear_decline = self.detect_bear_market()
        is_correction, correction_pct = self.detect_correction()
        is_breakout, breakout_amt = self.detect_breakout()
        is_range, dist_low, dist_high = self.detect_range_market()
        reversal_type, reversal_strength = self.detect_reversal()

        strategy_name, strategy_details = self.select_strategy()

        return {
            'volatility': volatility,
            'rate_of_change': roc,
            'bull_market': {
                'detected': is_bull,
                'gain': bull_gain
            },
            'bear_market': {
                'detected': is_bear,
                'decline': bear_decline
            },
            'correction': {
                'detected': is_correction,
                'pct': correction_pct
            },
            'breakout': {
                'detected': is_breakout,
                'amount': breakout_amt
            },
            'range_market': {
                'detected': is_range,
                'distance_to_support': dist_low,
                'distance_to_resistance': dist_high
            },
            'reversal': {
                'type': reversal_type,
                'strength': reversal_strength
            },
            'selected_strategy': strategy_name,
            'strategy_details': strategy_details,
            'timestamp': datetime.now().isoformat()
        }


if __name__ == "__main__":
    # Test with sample uptrend
    sample_bars = [
        {'c': 100 + (i * 0.5), 'h': 101 + (i * 0.5), 'l': 99 + (i * 0.5), 'v': 1000000}
        for i in range(100)
    ]

    analyzer = StrategySelector(sample_bars)
    result = analyzer.analyze()
    print(json.dumps(result, indent=2, default=str))
