# Trading Agent Architecture: Macro → Sector → Stock → Technical → Execute

Complete three-layer analysis pipeline with adaptive trading strategies.

## System Architecture

```
MACRO ANALYSIS (Portfolio-wide overlay)
├── VIX levels
├── Yield curve (10Y-2Y spread)
├── Fed funds rate
└── Leverage multiplier (0.5x - 1.5x)
    ↓
SECTOR ANALYSIS (Allocation weighting)
├── Sector ETF returns (XLK, XLV, XLE, etc.)
├── Performance ranking
└── Sector weights (0.8x - 1.2x per sector)
    ↓
STOCK ANALYSIS (Per-ticker evaluation)
├── Regime Detection (HMM)
├── Technical Analysis
│   ├── RSI (overbought/oversold)
│   ├── MACD (momentum)
│   ├── Support/Resistance levels
│   ├── Fibonacci retracements
│   └── Moving averages
├── Strategy Selection
│   ├── Trend trading
│   ├── Range trading
│   ├── Breakout trading
│   ├── Reversal trading
│   └── Momentum trading
├── Fundamental Analysis
│   ├── P/E ratio, forward P/E
│   ├── EPS growth
│   ├── Profit margin
│   ├── Debt/Equity ratio
│   └── ROE, current ratio
    ↓
EXECUTION
├── Regime-based position sizing
├── Technical confirmation (RSI, MACD, trend)
├── Strategy validation (breakout momentum, reversal strength)
├── Macro throttle (reduce in bearish macro)
├── Safety circuit breakers
└── Limit order placement
```

## Core Modules

### 1. `macro.py` — MacroAnalyzer
Portfolio-level risk adjustment.

**Inputs:** Market data (VIX, yields, Fed funds)
**Outputs:**
- `macro_score`: -1 (bearish) to +1 (bullish)
- `macro_sentiment`: "bearish" | "neutral" | "bullish"
- `leverage_multiplier`: 0.5x - 1.5x

**Logic:**
- High VIX (>30) → reduce leverage (bearish macro)
- Inverted yield curve → reduce leverage
- High rates (>5%) → reduce leverage
- Low VIX (<15) + normal curve → increase leverage

**Usage:**
```python
macro = MacroAnalyzer()
data = macro.analyze()
leverage_mult = data['leverage_multiplier']  # Apply to all positions
```

---

### 2. `sector.py` — SectorAnalyzer (in fundamentals.py)
Sector performance overlay for allocation.

**Inputs:** Sector ETF prices (XLK, XLV, XLE, XLI, XLY, XLP, XLRE, XLF, XLU, XLB)
**Outputs:**
- Ranked sectors (top → bottom performers)
- Sector weights (0.8x - 1.2x)

**Logic:**
- Top 3 sectors by YTD return → 1.2x weight
- Middle sectors → 1.0x weight
- Bottom 3 sectors → 0.8x weight

**Usage:**
```python
sector = SectorAnalyzer()
data = sector.analyze()
weights = data['sector_weights']  # Apply to stock allocations in those sectors
```

---

### 3. `technical.py` — TechnicalAnalyzer
Stock-level technical indicators and signals.

**Inputs:** OHLCV bars
**Outputs:**
- `rsi`: 0-100 (overbought >70, oversold <30)
- `macd`: Line, signal, histogram, bullish/bearish
- `support_resistance`: Current levels and distances
- `fibonacci_levels`: Retracement targets
- `trend`: "uptrend" | "downtrend" | "sideways"
- `overbought_oversold`: "overbought" | "oversold" | "neutral"
- `trade_signal`: "buy" | "sell" | "hold"

**Trade Signal Logic:**
- MACD bullish + RSI <70 + uptrend → BUY
- RSI <30 (oversold) + reversal confirmation → BUY
- MACD bearish + RSI >70 (overbought) → SELL
- Downtrend + overbought → SELL
- Indeterminate → HOLD

**Usage:**
```python
tech = TechnicalAnalyzer(bars)
data = tech.analyze()
signal = data['trade_signal']  # Confirm regime-based action
rsi = data['rsi']
```

---

### 4. `strategies.py` — StrategySelector
Market-condition-aware trading strategy selection.

**Inputs:** OHLCV bars
**Outputs:**
- `selected_strategy`: Strategy name
- `volatility`: Historical volatility
- `rate_of_change`: ROC(12) in %
- `bull_market` / `bear_market`: Detected? Magnitude
- `correction`: Detected? Percent from peak
- `breakout`: Detected? Distance above resistance
- `range_market`: Detected? Distance from support/resistance
- `reversal`: Type (bottom/top) and strength

**Strategy Mechanics:**

**Trend Trading** (Bull without correction)
- Entry: On dips within trend (technical buy + trend confirmation)
- Exit: Break of trend
- Confidence: High if ROC >2%

**Breakout Trading** (Breakout from consolidation)
- Entry: Close above resistance after low volatility
- Exit: Pullback below breakout level
- Confidence: 85% (requires volatility <5%)

**Range Trading** (Oscillating between support/resistance)
- Entry: At support, exit at resistance
- Sizing: Smaller positions (risk = resistance - support)
- Confidence: 80% if volatility <4%

**Reversal Trading** (Bottom or top reversal)
- Entry: After reversal confirmation
- Exit: Opposite reversal or stop loss
- Confidence: 70-75% depending on strength

**Momentum Trading** (Strong momentum despite pullback)
- Entry: Dips in strong uptrend (ROC >1%)
- Exit: Trend break or overbought RSI
- Confidence: 75%

**Usage:**
```python
strategy = StrategySelector(bars)
data = strategy.analyze()
strategy_name = data['selected_strategy']
confidence = data['strategy_details']['confidence']
```

---

### 5. `fundamentals.py` — FundamentalAnalyzer & SectorAnalyzer
Stock screening and valuation.

**FundamentalAnalyzer Inputs:** Stock ticker
**Outputs:**
- P/E ratio, forward P/E, EPS, EPS growth
- Profit margin, debt/equity, ROE, current ratio
- Scores:
  - `valuation_score` (0-100): P/E vs industry
  - `growth_score` (0-100): EPS & revenue growth
  - `health_score` (0-100): Profitability & liquidity
  - `overall_score` (0-100): Weighted average
  - `qualifies` (bool): True if score >60

**Logic:**
- Valuation: Lower P/E = higher score
- Growth: >15% earnings growth = +25 points
- Health: Profit margin >20% + D/E <1.0 = +25 points

**Usage:**
```python
fund = FundamentalAnalyzer("AAPL")
data = fund.analyze()
overall_score = data['overall_score']  # Screen in/out stocks
if data['qualifies']:
    # Add to core positions
```

---

### 6. `allocation.py` — PortfolioAllocator (Updated)
Dynamic position sizing with multi-layer adjustments.

**Inputs:**
- `regime`: Detected regime ("crash", "bear", "neutral", "bull", "euphoria")
- `account_value`: Current portfolio value
- `current_positions`: Open positions
- `bars`: Historical bars for volatility/trend
- `uncertain`: Regime uncertainty flag
- `macro_multiplier`: Leverage adjustment from macro (0.5x - 1.5x)
- `sector_weights`: Sector allocation adjustments
- `technical_signal`: "buy" | "sell" | "hold"

**Outputs:**
- `max_position_size`: $ position size cap
- `target_cash`: Desired cash reserve
- `leverage_multiplier`: Combined leverage factor
- `adjustments`: Breakdown of all multipliers

**Multiplier Stack:**
```
base_leverage (regime)
  × volatility_adj (market turbulence)
  × trend_adj (trend strength)
  × risk_tolerance (conservative/moderate/aggressive)
  × uncertainty_adj (regime flickering)
  × macro_adj (macro conditions)
  × technical_adj (signal-based tactical)
  = final_leverage
```

**Example:**
```
Bull regime (1.5x base)
  × volatility_adj (0.8, market choppy)
  × trend_adj (1.1, strong uptrend)
  × macro_adj (1.2, bullish macro)
  × technical_adj (1.2, technical buy)
  = 1.5 × 0.8 × 1.1 × 1.2 × 1.2 ≈ 1.9x leverage
```

---

### 7. `regime.py` — MarketRegimeDetector (Unchanged)
Hidden Markov Model regime detection.

**Outputs:**
- `regime`: "crash" | "bear" | "neutral" | "bull" | "euphoria"
- `confidence`: Probability (0-1)
- `uncertain`: True if regime flickering

---

### 8. `orchestrate.py` — Main Execution
Ties all layers together.

**Research Routine (9:45 AM ET):**
1. Macro analysis → log VIX, yields, leverage multiplier
2. Sector analysis → log sector rankings and weights
3. For each stock:
   - Fetch bars
   - HMM regime detection
   - Technical analysis (RSI, MACD, support/resistance, Fibonacci)
   - Strategy selection
   - Fundamental screening
   - Log all findings to journal

**Trading Routine (10:00 AM ET):**
1. Load macro and sector data from research
2. For each stock:
   - Regime detection
   - Technical analysis → buy/sell/hold signal
   - Strategy selection → validate approach
   - Position sizing:
     - Regime-based position size
     - Apply macro leverage multiplier
     - Apply sector weight
     - Apply technical adjustment
   - Execute if:
     - Regime supports trade
     - Technical signal confirms
     - Strategy validates approach
     - Safety limits allow

**EOD Routine (4:15 PM ET):**
1. Log final portfolio value
2. Update peak/starting capital for safety limits
3. Archive day's journal

---

## Trade Execution Decision Tree

```
For each stock:

1. CHECK REGIME
   ├─ Crash → SELL all, hold cash
   ├─ Bear → SELL on weakness (tech sell + downtrend)
   ├─ Neutral → Wait for confirmation (tech signal + strategy)
   ├─ Bull → BUY on strength (tech buy + breakout/trend/momentum)
   └─ Euphoria → TAKE PROFITS (tech sell + overbought)

2. GET TECHNICAL SIGNAL
   ├─ Buy (MACD bullish, RSI <70, uptrend)
   ├─ Sell (MACD bearish, RSI >70, downtrend)
   └─ Hold (Indeterminate)

3. VALIDATE WITH STRATEGY
   ├─ Trend trading: Confirm trend, check pullback support
   ├─ Breakout: Confirm low volatility + volume
   ├─ Range: Confirm support/resistance persistence
   ├─ Reversal: Confirm reversal pattern + Fibonacci level
   └─ Momentum: Confirm ROC > threshold

4. SIZE POSITION
   base_position = regime_allocation × account_value
   × macro_multiplier (macro conditions)
   × technical_multiplier (buy=1.2, sell=0.6, hold=1.0)
   × sector_weight (top sector=1.2, bottom=0.8)
   × safety_throttle (circuit breaker)

5. EXECUTE
   ├─ Validate safety limits
   ├─ Place limit order (within 0.2% of market)
   ├─ Log reasoning to journal
   └─ Monitor position
```

---

## Key Parameters

### Regime Allocations (per CLAUDE.md)
| Regime | Position Size | Leverage | Cash Reserve |
|--------|---|---|---|
| Crash | 1% | 0.0x | 95% |
| Bear | 3% | 0.5x | 70% |
| Neutral | 5% | 1.0x | 20% |
| Bull | 8% | 1.5x | 15% |
| Euphoria | 5% | 1.0x | 30% |

### Technical Thresholds
- RSI overbought: >70
- RSI oversold: <30
- Trend threshold: ±2% from moving average
- Support/resistance lookback: 20 bars
- Volatility normal: 0.5%-1.5% daily

### Volatility Adjustments
- High vol (>2% daily) → 0.6x position
- Medium vol (1.5-2%) → 0.8x position
- Normal vol (0.5-1.5%) → 1.0x position
- Low vol (<0.5%) → 1.2x position

### Safety Limits (per CLAUDE.md)
- Max daily loss: 2% of starting value → throttle 50%
- Max drawdown: 5% from peak → reduce new entries 50%
- Breach both → no new trades (circuit breaker)

---

## Data Flow Example

**Morning (9:45 AM):**
```json
{
  "macro": {
    "vix": 18.5,
    "yield_curve": "normal",
    "fed_funds": 4.5,
    "macro_sentiment": "bullish",
    "leverage_multiplier": 1.3
  },
  "sectors": {
    "ranked": [
      {"rank": 1, "sector": "Technology", "return": 0.08},
      {"rank": 2, "sector": "Healthcare", "return": 0.05}
    ],
    "weights": {
      "Technology": 1.2,
      "Healthcare": 1.0,
      "Energy": 0.8
    }
  },
  "stocks": {
    "NVDA": {
      "regime": "bull",
      "confidence": 0.92,
      "technical": {
        "rsi": 55,
        "macd_bullish": true,
        "trend": "uptrend",
        "signal": "buy"
      },
      "strategy": {
        "selected": "breakout_trading",
        "confidence": 0.85
      },
      "fundamental": {
        "overall_score": 72,
        "qualifies": true
      }
    }
  }
}
```

**Trading (10:00 AM):**
```
Evaluate NVDA:
- Regime: Bull (base 1.5x leverage)
- Volatility: 0.8% (0.8x adj)
- Trend: strong uptrend (1.1x adj)
- Risk tolerance: moderate (1.0x)
- Macro: bullish (1.3x adj)
- Technical: buy signal (1.2x adj)
→ Final leverage: 1.5 × 0.8 × 1.1 × 1.0 × 1.3 × 1.2 = 2.06x

Max position size: $100k × 8% × 2.06 = $16,480
→ BUY 100 shares @ $164.80 limit

Journal: "Breakout buy - bull regime, tech buy signal, low volatility, bullish macro"
```

---

## Logging & Monitoring

All decisions logged to `journal/YYYY-MM-DD.md`:
- **Macro Analysis**: VIX, yield curve, leverage multiplier
- **Sector Analysis**: Top/bottom performers, weights
- **Stock Research**: Regime, technical, strategy, fundamentals
- **Trades Executed**: Symbol, action, qty, price, reasoning

Example:
```markdown
# Trade Journal — 2026-04-28

## Macro Analysis
- Sentiment: bullish (score: 0.35)
- VIX: 18.5
- Yield curve: normal (0.2%)
- Leverage multiplier: 1.3x

## Sector Analysis
1. Technology: +8.2%
2. Healthcare: +5.1%
...

## Stock Research

### NVDA
- Regime: bull (confidence: 92%)
- Technical: RSI 55, MACD bullish, Trend uptrend
- Signal: buy | Strategy: breakout_trading
- Fundamental: 72/100 ✓

## Trades Executed
| Time | Symbol | Action | Qty | Price | Reasoning |
|------|--------|--------|-----|-------|-----------|
| 10:05 | NVDA | BUY | 100 | $164.80 | Breakout buy - bull regime, tech buy, low vol |
| 10:12 | SPY | HOLD | 0 | $472.50 | Neutral regime, no confirm signal |
```

---

## Testing & Optimization

Run research-only (no trading):
```bash
python orchestrate.py research
```

Backtest with walk-forward validation:
```bash
python backtest.py  # Existing script
```

Simulate trades without execution:
```python
# Modify orchestrate.py, comment out place_order()
```

---

## Notes

- **Macro is portfolio-level**: VIX/yield curve affect ALL positions equally
- **Sector is allocation-level**: Performance weights within sector buckets
- **Technical is trade-level**: Per-stock entry/exit signals
- **Strategy is confirmation**: Validates that conditions align with approach
- **Fundamentals are screening**: Avoid weak businesses, focus on quality

All multipliers compound, so order matters:
```
1.5 × 0.8 × 1.1 × 1.3 × 1.2 = 2.06x
(0.5 × base benefit from lower position size in choppy market)
```

Calibrate parameters in allocation.py and regime.py based on backtest results.
