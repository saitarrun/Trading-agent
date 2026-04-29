# Performance Tracking & Adaptive Strategy Weighting

System learns from past trades and dynamically adjusts strategy confidence and position sizing.

## Overview

Three components work together:

1. **PerformanceTracker** — Aggregates wins/losses per strategy/regime combo
2. **PositionTracker** — Records entry prices, detects exits, feeds trade results to PerformanceTracker
3. **StrategySelector** — Uses performance data to adjust confidence and selection

## Files

### `scripts/performance.py` — PerformanceTracker
Tracks cumulative performance of each strategy in each regime.

**Key Methods:**
- `record_trade(symbol, strategy, regime, entry_price, exit_price, qty, entry_time, exit_time)` — Log a closed trade
- `get_win_rate(strategy, regime)` — Win % for strategy/regime combo (default 0.5 if untested)
- `get_avg_return(strategy, regime)` — Average return for combo
- `adjust_strategy_confidence(strategy, regime, base_confidence)` — Adjust base confidence by historical performance
- `get_strategy_adjustment_multiplier(strategy, regime)` — Position size multiplier (1.0 untested, 0.7-1.2 based on performance)

**Output:**
- `journal/performance_stats.json` — Cumulative stats per strategy/regime

**Logic:**
- 3+ trades required for signal
- Win rate >60% + positive return → +0.15 confidence boost, 1.2x position size
- Win rate <40% OR negative return → -0.15 confidence reduction, 0.7x position size
- Confidence clamped 0.3-0.95

### `scripts/position_tracker.py` — PositionTracker
Tracks open position entry prices to detect exits and measure performance.

**Key Methods:**
- `record_entry(symbol, strategy, regime, entry_price, qty, entry_time)` — Log position entry
- `detect_exit(symbol, current_price, current_qty)` — Detect if position was closed or reduced
- `close_position(symbol)` — Remove from tracking after recording exit

**Output:**
- `journal/position_tracker.json` — Active position entries

**Logic:**
- Records entry price, strategy, regime at time of entry
- Compares current qty against entry qty to detect exits
- Returns (exited, exit_price) tuple for trade recording

## Integration

### In orchestrate.py

**1. Initialize trackers:**
```python
performance_tracker = PerformanceTracker()
position_tracker = PositionTracker()
```

**2. Check for exited positions (start of run_trading_routine):**
```python
for symbol, entry_data in list(position_tracker.get_all().items()):
    exited, exit_price = position_tracker.detect_exit(symbol, current_price, current_qty)
    if exited:
        performance_tracker.record_trade(...)  # Record to stats
        position_tracker.close_position(symbol)
```

**3. Pass to StrategySelector:**
```python
strategy_selector = StrategySelector(bars, regime=regime, performance_tracker=performance_tracker)
```
StrategySelector uses `adjust_strategy_confidence()` to boost/reduce confidence based on win rate.

**4. Apply position size multiplier:**
```python
strategy_mult = performance_tracker.get_strategy_adjustment_multiplier(selected_strategy, regime)
qty = int(qty * strategy_mult)
```

**5. Record entries when buying:**
```python
if action == "buy":
    position_tracker.record_entry(symbol, selected_strategy, regime, current_price, qty)
```

## Example Flow

**Day 1: Entry**
- Buy 100 AAPL @ $150 in bull regime using trend_trading
- `PositionTracker.record_entry("AAPL", "trend_trading", "bull", 150, 100)`

**Day 5: Exit**
- AAPL now @ $152, position reduced to 0
- `detect_exit()` returns (True, 152)
- `PerformanceTracker.record_trade("AAPL", "trend_trading", "bull", 150, 152, 100, ...)`
- Win! Returns +1.33%. Win rate = 1/1 = 100%.

**Day 6: Next bull trend setup**
- New trend_trading signal in bull regime
- Base confidence 0.85
- `adjust_strategy_confidence("trend_trading", "bull", 0.85)`
- Historical win rate = 100% → adjust +0.15 → **1.0 confidence**
- `get_strategy_adjustment_multiplier()` → **1.2x position size** (strong performer)
- Buy with boosted size and confidence

## Monitoring

Check performance stats:
```bash
cat journal/performance_stats.json
```

Shows win rates, avg returns, trade counts per strategy/regime:
```json
{
  "by_strategy_regime": {
    "trend_trading_bull": {
      "wins": 5, "losses": 2, "trades": 7,
      "avg_return": 0.012, "total_return": 0.084
    },
    "breakout_trading_neutral": {
      "wins": 4, "losses": 3, "trades": 7,
      "avg_return": 0.005, "total_return": 0.035
    }
  }
}
```

## Next Steps

1. Run system for 2+ weeks to accumulate trade history
2. Monitor `journal/performance_stats.json` for emerging patterns
3. Identify underperforming strategy/regime combos
4. Consider adding new strategies or tuning parameters based on data
5. Update position sizing confidence thresholds if needed

## Limitations

- Requires 3+ trades per combo for confidence adjustment (avoid overfitting)
- Win rate alone doesn't account for risk-adjusted returns (Sharpe ratio, max drawdown)
- No time decay on stats (old trades weighted equally to recent ones)
- Closed positions only — doesn't track unrealized P&L or partial exits

## Future Enhancements

- Weighted recent trades higher (decay old stats)
- Add risk-adjusted metrics (Sharpe ratio per strategy)
- Track partial exits and position adjustments
- Auto-disable strategies with <30% win rate
- A/B test parameter changes against control
