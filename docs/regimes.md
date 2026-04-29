# Market Regime Framework

HMM-based detection on volatility + trend. 5 states, auto-updated every 9:45 AM ET.

## Regime Definitions

| Regime | Vol | Trend | Actions | Color |
|--------|-----|-------|---------|-------|
| **Crash** | >3% | ↓ Down | Liquidate non-core, 95% cash, NO buys | 🔴 |
| **Bear** | 2-3% | ↓ Down | Reduce exposure, defensive, 70% cash | 🟠 |
| **Neutral** | 0.5-1.5% | → Sideways | Balanced, wait confirm, 20% cash | 🟡 |
| **Bull** | 1-2% | ↑ Up | Increase, add positions, 15% cash | 🟢 |
| **Euphoria** | >2% | ↑ Up Unsustain | Lock gains, reduce risk, 30% cash | 🔵 |

## HMM Training & Prediction

```python
detector = MarketRegimeDetector()
detector.fit(bars)                      # 200 bars, trains on volatility + trend
regime, confidence = detector.predict_regime()
uncertain = confidence < 0.6            # Apply 0.7x uncertainty_adj if true
```

## Transitions

- **Any → Crash**: Immediate liquidation, no waiting
- **Crash → Bear**: Rebuild 25% of normal size/day
- **Bear → Neutral**: Resume normal over 2-3 days
- **Neutral → Bull**: Gradual exposure increase
- **Bull → Euphoria**: Begin profit-taking
- **Euphoria → Down**: Accelerate exit

## Uncertainty Handling

If confidence < 0.6 OR flickering between states:
- Multiply all position sizes by 0.7
- Log to journal
- Hold only, no new entries
