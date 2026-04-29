# Position Sizing & Allocation

## Regime-Based Base Allocations

| Regime | Max % Per Trade | Leverage | Cash Reserve | New Entry? |
|--------|----------|----------|-------------|-----------|
| Crash | 1% | 0x | 95% | ❌ NO |
| Bear | 3% | 0.5x | 70% | ⚠️ Defensive |
| Neutral | 5% | 1x | 20% | ✅ Confirmed |
| Bull | 8% | 1.5x | 15% | ✅ Aggressive |
| Euphoria | 5% | 1x | 30% | ⚠️ Reduce |

## Position Size Multiplier Stack

```
final_size = base_allocation × account_equity
  × volatility_adj       (0.6x if vol >2%, 1.2x if vol <0.5%, 1.0x normal)
  × trend_strength       (0.8x down, 1.2x up, 1.0x sideways)
  × uncertainty_adj      (0.7x if regime uncertain)
  × macro_mult           (0.5x-1.5x from VIX/yields/rates)
  × sector_weight        (0.8x-1.2x from top/bottom ranking)
  × technical_signal     (1.2x buy, 0.6x sell, 1.0x hold)
  × strategy_confidence  (0.7x-1.2x from recent performance)
  × safety_throttle      (0.5x if circuit breaker hit, 1.0x normal)
```

## Per-Symbol Caps (Watchlist)

No position can exceed:
- SPY: 15% of portfolio
- QQQ: 10%
- NVDA: 8%
- AAPL: 8%
- MSFT: 8%

Enforced AFTER all multipliers calculated. Size is capped to the lower of (calculated size, symbol max).

## Volatility Adjustments

| Daily Change | Multiplier |
|-------------|-----------|
| >2% (extreme) | 0.6x |
| 1.5-2% (high) | 0.8x |
| 0.5-1.5% (normal) | 1.0x |
| <0.5% (low) | 1.2x |

## Multi-Layer Analysis Order

1. **Macro** (`macro.py`) — VIX, yield curve, fed funds → leverage_mult (0.5x-1.5x)
2. **Sector** (`fundamentals.py`) — Rank sector ETFs → sector_weight (0.8x-1.2x)
3. **Regime** (`regime.py`) — HMM detect → base_allocation per regime table
4. **Technical** (`technical.py`) — RSI, MACD, trend, support/resistance → signal (buy/sell/hold)
5. **Strategy** (`strategies.py`) — Pick best strategy (trend, range, breakout, reversal, momentum)
6. **Fundamental** (`fundamentals.py`) — P/E, EPS, profitability, debt → score (0-100)

All layers feed into final position size via multiplier stack.

## Adaptive Weighting (from PerformanceTracker)

After 3+ trades per strategy/regime combo:

| Result | Confidence Adj | Size Mult |
|--------|---------|----------|
| Win% >60%, +return | +0.15 | 1.2x |
| Win% 40-60% | 0 | 1.0x |
| Win% <40%, -return | -0.15 | 0.7x |

Confidence clamped [0.30, 0.95].
