"""Track strategy performance and adjust position sizing dynamically."""

import json
import os
from datetime import datetime
from pathlib import Path
from collections import defaultdict

class PerformanceTracker:
    """Track trade outcomes per strategy/regime combo. Adjust confidence dynamically."""

    def __init__(self, stats_file="journal/performance_stats.json"):
        self.stats_file = stats_file
        self.stats = self._load_stats()

    def _load_stats(self):
        """Load existing performance stats or initialize empty."""
        if os.path.exists(self.stats_file):
            with open(self.stats_file) as f:
                return json.load(f)
        return self._init_stats()

    def _init_stats(self):
        """Initialize empty performance tracking structure."""
        return {
            "by_strategy_regime": {},  # {"trend_bull": {"wins": 5, "losses": 2, "avg_return": 0.012, ...}}
            "by_strategy": {},  # Aggregated across all regimes
            "by_regime": {},  # Aggregated across all strategies
            "last_updated": datetime.now().isoformat()
        }

    def record_trade(self, symbol, strategy, regime, entry_price, exit_price, qty, entry_time, exit_time):
        """Record a closed trade. Calculate return and update stats."""
        if exit_price <= 0 or entry_price <= 0:
            return  # Skip invalid trades

        trade_return = (exit_price - entry_price) / entry_price
        won = 1 if trade_return > 0 else 0

        key = f"{strategy}_{regime}"

        # Initialize if first trade
        if key not in self.stats["by_strategy_regime"]:
            self.stats["by_strategy_regime"][key] = {
                "wins": 0, "losses": 0, "total_return": 0.0, "trades": 0,
                "max_return": -999, "min_return": 999
            }

        stats = self.stats["by_strategy_regime"][key]
        stats["wins"] += won
        stats["losses"] += (1 - won)
        stats["total_return"] += trade_return
        stats["trades"] += 1
        stats["max_return"] = max(stats["max_return"], trade_return)
        stats["min_return"] = min(stats["min_return"], trade_return)

        self._save_stats()

    def get_win_rate(self, strategy, regime):
        """Win rate for strategy/regime combo. Default 0.5 if no history."""
        key = f"{strategy}_{regime}"
        if key not in self.stats["by_strategy_regime"]:
            return 0.5  # Neutral default

        stats = self.stats["by_strategy_regime"][key]
        total = stats["wins"] + stats["losses"]
        if total == 0:
            return 0.5
        return stats["wins"] / total

    def get_avg_return(self, strategy, regime):
        """Average return for strategy/regime combo."""
        key = f"{strategy}_{regime}"
        if key not in self.stats["by_strategy_regime"]:
            return 0.0

        stats = self.stats["by_strategy_regime"][key]
        if stats["trades"] == 0:
            return 0.0
        return stats["total_return"] / stats["trades"]

    def adjust_strategy_confidence(self, strategy, regime, base_confidence):
        """Adjust base confidence by historical performance.

        High win rate + positive return = boost confidence
        Low win rate or negative return = reduce confidence
        New strategy = keep base confidence
        """
        win_rate = self.get_win_rate(strategy, regime)
        avg_return = self.get_avg_return(strategy, regime)

        key = f"{strategy}_{regime}"
        trade_count = self.stats["by_strategy_regime"].get(key, {}).get("trades", 0)

        if trade_count < 3:  # Need min 3 trades for signal
            return base_confidence

        # Confidence adjustment: +0.2 if win rate >60% and return >0, -0.2 if win rate <40%
        adjustment = 0.0
        if win_rate > 0.60 and avg_return > 0:
            adjustment = 0.15
        elif win_rate < 0.40 or avg_return < -0.01:
            adjustment = -0.15
        elif win_rate > 0.55:
            adjustment = 0.05

        adjusted = max(0.3, min(0.95, base_confidence + adjustment))  # Clamp 0.3-0.95
        return adjusted

    def get_strategy_adjustment_multiplier(self, strategy, regime):
        """Position size multiplier based on strategy performance.

        Strong performer (win rate >60%) → 1.2x
        Weak performer (win rate <40%) → 0.7x
        Untested → 1.0x
        """
        win_rate = self.get_win_rate(strategy, regime)
        key = f"{strategy}_{regime}"
        trade_count = self.stats["by_strategy_regime"].get(key, {}).get("trades", 0)

        if trade_count < 2:
            return 1.0  # No adjustment until history

        if win_rate > 0.60:
            return 1.2
        elif win_rate < 0.40:
            return 0.7
        elif win_rate > 0.55:
            return 1.1
        elif win_rate < 0.45:
            return 0.9
        else:
            return 1.0

    def _save_stats(self):
        """Persist stats to disk."""
        self.stats["last_updated"] = datetime.now().isoformat()
        Path(self.stats_file).parent.mkdir(parents=True, exist_ok=True)
        with open(self.stats_file, 'w') as f:
            json.dump(self.stats, f, indent=2)

    def get_summary(self):
        """Get summary of all tracked strategies."""
        summaries = []
        for key, stats in self.stats["by_strategy_regime"].items():
            if stats["trades"] == 0:
                continue
            win_rate = stats["wins"] / (stats["wins"] + stats["losses"])
            avg_return = stats["total_return"] / stats["trades"]
            summaries.append({
                "strategy_regime": key,
                "trades": stats["trades"],
                "win_rate": f"{win_rate:.1%}",
                "avg_return": f"{avg_return:.2%}",
                "total_return": f"{stats['total_return']:.2%}",
                "max_return": f"{stats['max_return']:.2%}",
                "min_return": f"{stats['min_return']:.2%}"
            })
        return summaries


if __name__ == "__main__":
    tracker = PerformanceTracker()

    # Test: record some trades
    tracker.record_trade("AAPL", "trend_trading", "bull", 150, 152, 100, "10:00", "14:30")
    tracker.record_trade("AAPL", "trend_trading", "bull", 152, 151, 100, "10:05", "14:35")
    tracker.record_trade("MSFT", "breakout_trading", "neutral", 300, 305, 50, "10:10", "14:40")

    print("Summary:")
    for s in tracker.get_summary():
        print(f"  {s}")

    print("\nConfidence adjustments:")
    print(f"  trend_trading in bull: {tracker.adjust_strategy_confidence('trend_trading', 'bull', 0.85):.2f}")
    print(f"  breakout_trading in neutral: {tracker.adjust_strategy_confidence('breakout_trading', 'neutral', 0.80):.2f}")

    print("\nPosition size multipliers:")
    print(f"  trend_trading in bull: {tracker.get_strategy_adjustment_multiplier('trend_trading', 'bull'):.2f}x")
    print(f"  breakout_trading in neutral: {tracker.get_strategy_adjustment_multiplier('breakout_trading', 'neutral'):.2f}x")
