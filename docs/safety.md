# Safety Systems & Circuit Breakers

## Hardcoded Limits (CANNOT BE OVERRIDDEN)

| Limit | Threshold | State | Action |
|-------|-----------|-------|--------|
| Max Daily Loss | 2% of day-start | THROTTLED | New trades 50% size |
| Max Drawdown | 5% from peak | HALTED | NO new trades, exits only |
| Both limits breached | Both hit | HALTED | Complete trading halt |
| Stop Loss | 8% decline from entry | Auto-close | Immediate sell (no override) |

## Circuit Breaker States

```
NORMAL
  ↓ daily loss 2% OR drawdown 5%
THROTTLED
  • All new positions capped at 50% normal size
  • Existing positions unchanged
  ↓ OTHER limit also breached
HALTED
  • NO new trades
  • Exits only (stop losses, taking profits)
  ↓ Reset next trading day (if both limits improve)
NORMAL
```

## Safety Check (runs before EVERY trade)

```python
safety.load_state()
safety.update_peak(current_equity)

daily_loss = (day_start - current) / day_start
drawdown = (peak - current) / peak
throttle = safety.calculate_throttle_factor()

if daily_loss > 0.02 and drawdown > 0.05:
    throttle = 0.0  # HALTED
elif daily_loss > 0.02 or drawdown > 0.05:
    throttle = 0.5  # THROTTLED
else:
    throttle = 1.0  # NORMAL

if throttle == 0:
    # HALT all new trades
elif throttle == 0.5:
    # Reduce new position size by 50%
```

## Stop Loss Protocol

For every open position, check at 9:45 AM, 10:00 AM, 12:00 PM, 4:15 PM:

```
if current_price <= entry_price × 0.92:  # 8% decline
    → place_order(symbol, qty, SELL, limit=bid*0.998)
    → Log: "STOP LOSS: {symbol} at {price}"
    → Record to PerformanceTracker
    → Do NOT re-enter same day
```

## Peak Capital Tracking

Updated every routine:
- If current_equity > peak → peak = current_equity
- Drawdown = (peak - current) / peak
- Checked against 5% limit

## Daily Reset

At market open (9:30 AM):
- Load safety_state.json from yesterday
- Record day_start_value = current_equity
- Check if circuit breaker was halted yesterday (if so, log it)
- If new trading day, reset daily_loss to 0%
