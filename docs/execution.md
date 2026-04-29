# Trade Execution & Decision Framework

## Pre-Trade Checklist (ALL must pass)

```
□ 1. Market is OPEN                        → get_market_status()
□ 2. API is stable (no recent errors)      → check last N calls
□ 3. Circuit breaker allows trades         → throttle_factor > 0
□ 4. Regime is not CRASH (for buy)         → regime != "crash"
□ 5. Technical signal is clear             → confidence > 0.4
□ 6. Strategy validates approach           → confidence > 0.5
□ 7. Position size ≤ regime limit          → check allocation table
□ 8. Position size ≤ symbol cap            → SPY 15%, QQQ 10%, etc
□ 9. Cash reserve maintained               → check regime target
□ 10. Stop loss not already triggered      → check position_tracker
```

**If ANY check fails → HOLD, log reason to journal.**

## Decision Tree Per Symbol

```
1. GET REGIME + CONFIDENCE
   confidence < 0.6? → Apply 0.7x uncertainty_adj

2. GET TECHNICAL SIGNAL (buy/sell/hold)
   signal == "sell" AND regime in [bear, euphoria]? → SELL
   signal == "buy"  AND regime in [bull, neutral]?  → proceed
   signal == "hold"                                 → HOLD
   signal == "sell" AND regime == "bull"?           → HOLD (conflict)

3. VALIDATE WITH STRATEGY
   confidence > 0.7?  → full position size
   0.5 < conf ≤ 0.7? → 75% position size
   confidence ≤ 0.5?  → HOLD

4. SIZE POSITION
   → Apply full multiplier stack
   → Cap at symbol max
   → Cap at regime allocation
   → Verify cash reserve OK

5. CHECK SAFETY
   → throttle_factor = SafetyManager.get_throttle()
   → if throttle == 0 → HALT (no trade)
   → if throttle == 0.5 → reduce size 50%
   → if throttle == 1.0 → proceed

6. EXECUTE
   → place_order(symbol, qty, side, limit_price)
   → position_tracker.record_entry(symbol, qty, entry_price, entry_time)
   → Log full reasoning: regime, signal, strategy conf, size calc, reason
```

## Order Placement Rules

1. **Order Type**: Limit only. NEVER market orders.
2. **Buy Limit**: Current ask × 1.002 (0.2% premium)
3. **Sell Limit**: Current bid × 0.998 (0.2% discount)
4. **Time in Force**: 
   - Regular trades: DAY
   - Stop losses: GTC (Good-til-Cancelled)
5. **Validate** before submit: `validate_order(symbol, qty, side, price)`

## Exit Conditions

- **Regime → Crash**: Immediate liquidation all non-core
- **Stop Loss**: 8% decline from entry, auto-close
- **Profit Target**: None hard-coded, strategy-driven
- **Take Profit**: Via PerformanceTracker adaptive weighting
- **Manual Exit**: Log reason to journal if initiating outside regime/stop rules

## Journal Logging (every trade or hold)

```
### {SYMBOL} @ {TIME}

**Decision**: BUY / SELL / HOLD

**Reasoning**:
- Regime: {regime} (conf: X%)
- Technical: {signal} (RSI XX, MACD status)
- Strategy: {strategy_name} (conf: XX%)
- Size: {qty} @ ${price} (X% of portfolio)
- Safety: {throttle_state} (daily loss X%, drawdown X%)

**Multipliers**:
- Regime alloc: X%
- Vol adj: X.Xx
- Trend: X.Xx
- Macro: X.Xx
- Sector: X.Xx
- Technical: X.Xx
- Strategy: X.Xx
- Safety: X.Xx
- Final: {final_qty} shares

**Execution**: {status} @ {time}
```

## Held Positions

Track entry prices in `position_tracker.json`:
```json
{
  "symbol": "NVDA",
  "qty": 10,
  "entry_price": 875.50,
  "entry_time": "2026-04-29T10:05:30-04:00",
  "regime_at_entry": "bull",
  "stop_loss_price": 805.06
}
```

Stop loss = entry × 0.92. Checked every routine. Auto-close if breached.
