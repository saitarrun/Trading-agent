import numpy as np
import json
from datetime import datetime, timedelta
from regime import MarketRegimeDetector
from allocation import PortfolioAllocator

class WalkForwardBacktester:
    """Walk-forward backtesting engine (avoids look-ahead bias).

    Splits data into:
    - Training window: fit regime model
    - Test window: evaluate strategy performance
    """

    def __init__(self, train_window_days=60, test_window_days=20):
        self.train_window_days = train_window_days
        self.test_window_days = test_window_days
        self.regime_detector = MarketRegimeDetector()
        self.allocator = PortfolioAllocator()

    def split_data(self, bars, split_date):
        """Split bars into train (before split) and test (after split)."""
        train = [b for b in bars if b['t'] < split_date]
        test = [b for b in bars if b['t'] >= split_date]
        return train, test

    def backtest_period(self, bars, symbol="SPY"):
        """Run walk-forward backtest on bars.

        Returns dict with performance metrics.
        """
        if len(bars) < self.train_window_days + self.test_window_days:
            return {"error": "Insufficient data"}

        results = []
        starting_capital = 100000
        current_capital = starting_capital

        split_idx = self.train_window_days
        while split_idx + self.test_window_days <= len(bars):
            split_date = bars[split_idx]['t']

            train_bars, test_bars = self.split_data(bars, split_date)

            self.regime_detector.fit(train_bars)

            period_result = {
                "split_date": split_date,
                "train_bars": len(train_bars),
                "test_bars": len(test_bars),
                "trades": []
            }

            period_pnl = 0
            for test_bar in test_bars:
                test_window = [b for b in test_bars if b['t'] <= test_bar['t']]

                regime, confidence = self.regime_detector.predict_regime(test_window)
                characteristics = self.regime_detector.get_regime_characteristics(regime)

                allocation = self.allocator.calculate_allocation(
                    regime, current_capital
                )

                if characteristics['direction'] == 'up':
                    pnl = current_capital * 0.001
                elif characteristics['direction'] == 'down':
                    pnl = -current_capital * 0.001
                else:
                    pnl = 0

                pnl_pct = (pnl / current_capital) * 100
                current_capital += pnl
                period_pnl += pnl

                period_result["trades"].append({
                    "date": test_bar['t'],
                    "regime": regime,
                    "confidence": float(confidence),
                    "pnl": pnl,
                    "capital": current_capital
                })

            result_return = (period_pnl / (starting_capital if split_idx == 0 else current_capital - period_pnl)) * 100
            period_result["return_pct"] = result_return

            results.append(period_result)
            split_idx += self.test_window_days

        total_return = ((current_capital - starting_capital) / starting_capital) * 100
        total_trades = sum(len(r["trades"]) for r in results)

        return {
            "symbol": symbol,
            "starting_capital": starting_capital,
            "ending_capital": current_capital,
            "total_return_pct": total_return,
            "num_periods": len(results),
            "avg_period_return_pct": np.mean([r["return_pct"] for r in results]),
            "sharpe_ratio": self._calculate_sharpe([r["return_pct"] for r in results]),
            "periods": results
        }

    def _calculate_sharpe(self, returns, risk_free_rate=0.02):
        """Simple Sharpe ratio calculation."""
        if len(returns) == 0:
            return 0.0

        returns_arr = np.array(returns)
        excess_return = np.mean(returns_arr) - risk_free_rate
        volatility = np.std(returns_arr)

        if volatility == 0:
            return 0.0

        return (excess_return / volatility) * np.sqrt(252)

if __name__ == "__main__":
    from research import get_bars

    bars_response = get_bars("SPY", "1Day", limit=150)

    if "bars" in bars_response:
        bars = [
            {
                "t": t,
                "c": b["c"],
                "h": b["h"],
                "l": b["l"],
                "o": b["o"]
            }
            for t, b in sorted(bars_response["bars"].items())
        ]

        backtester = WalkForwardBacktester(train_window_days=60, test_window_days=20)
        results = backtester.backtest_period(bars, symbol="SPY")

        print(json.dumps({
            "symbol": results["symbol"],
            "starting_capital": results["starting_capital"],
            "ending_capital": results["ending_capital"],
            "total_return_pct": results["total_return_pct"],
            "sharpe_ratio": results["sharpe_ratio"],
            "num_periods": results["num_periods"]
        }, indent=2))
