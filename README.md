# AI Trading Agent: Macro → Sector → Stock → Technical → Execution

Autonomous regime-aware trading agent with comprehensive multi-layer analysis pipeline.

**Macro Analysis** (portfolio-level overlay): VIX, yield curve, Fed funds → leverage multiplier (0.5x-1.5x)
**Sector Analysis** (allocation weighting): Sector ETF performance → weights per sector (0.8x-1.2x)
**Technical Analysis** (trade signals): RSI, MACD, support/resistance, Fibonacci, moving averages
**Strategy Selection** (confirmation): Trend, range, breakout, reversal, momentum trading
**Fundamental Screening** (stock quality): P/E, EPS growth, profitability, debt levels
**Regime Detection** (HMM): Market state (crash/bear/neutral/bull/euphoria) → base allocation
**Execution** (orders): Position sizing × macro × sector × technical → limit order placement
**Safety Limits** (circuit breakers): 2% daily loss, 5% max drawdown → throttling/halt

## Setup

1. **Create .env file from template:**
   ```bash
   cp .env.example .env
   ```
   Add your Alpaca paper trading API credentials.

2. **Install dependencies:**
   ```bash
   source venv/bin/activate
   pip install -r requirements.txt
   ```

3. **Initialize system:**
   ```bash
   python scripts/orchestrate.py init
   ```
   Verifies API connection, market status, configurations.

4. **Configure Claude Code routines:**
   - The `.claude/routines.json` file defines three scheduled tasks
   - 9:45 AM: Morning research (regime detection + market data)
   - 10:00 AM: Trading session (allocation + execution)
   - 4:15 PM: End-of-day journal (finalize logs)

## Files

**Multi-Layer Analysis:**
- `scripts/macro.py` — VIX, yield curve, Fed funds → leverage multiplier (0.5x-1.5x)
- `scripts/sector.py` (in fundamentals.py) — Sector ETF returns → allocation weights
- `scripts/technical.py` — RSI, MACD, support/resistance, Fibonacci, moving averages
- `scripts/strategies.py` — Strategy selection (trend, range, breakout, reversal, momentum)
- `scripts/fundamentals.py` — Stock screening (P/E, EPS, profitability, debt, ROE)

**Core Engine:**
- `scripts/regime.py` — HMM regime detection (crash/bear/neutral/bull/euphoria)
- `scripts/allocation.py` — Position sizing (regime × volatility × trend × macro × sector × technical)
- `scripts/safety.py` — Circuit breakers (2% daily loss, 5% drawdown)
- `scripts/backtest.py` — Walk-forward backtesting
- `scripts/orchestrate.py` — Main orchestration (research → trading → EOD)

**Data & Trading:**
- `scripts/research.py` — Market data fetching (bars, news, account)
- `scripts/trade.py` — Order placement + market status checks

**Configuration:**
- `CLAUDE.md` — Agent instructions, regime rules, safety limits
- `watchlist.json` — Symbols, allocation limits per position
- `.claude/routines.json` — Scheduled task config
- `.claude/settings.json` — Claude Code project settings

**Monitoring:**
- `dashboard.py` — Streamlit UI (positions, regime, safety, journal)
- `journal/` — Trade logs, regime history, safety state

## Running

**System initialization:**
```bash
python scripts/orchestrate.py init
```

**Individual routines (manual test):**
```bash
python scripts/orchestrate.py research
python scripts/orchestrate.py trading
python scripts/orchestrate.py eod
```

**Main execution loop (5-minute bars):**
```bash
python scripts/orchestrate.py loop 300
```
Runs continuously, checks regime/safety every 5 min.

**Data tools (debugging):**
```bash
python scripts/research.py account
python scripts/research.py bars AAPL
python scripts/trade.py status
```

**Dashboard:**
```bash
streamlit run dashboard.py
```
Opens UI at `localhost:8501` showing positions, regime, safety status, trade journal.

## Market Regimes (HMM-Detected)

| Regime | Signal | Base Leverage | Cash Reserve |
|--------|--------|---|---|
| Crash | ↓ High vol, downtrend | 0.0x | 95% |
| Bear | ↓ Medium vol, downtrend | 0.5x | 70% |
| Neutral | ↔ Low vol, sideways | 1.0x | 20% |
| Bull | ↑ Medium vol, uptrend | 1.5x | 15% |
| Euphoria | ↑ High vol, unsustainable | 1.0x | 30% |

Detected via HMM on 20-day returns + intraday volatility (3-7 auto-selected states).

## Trading Strategies (Adaptive)

Agent selects strategy based on market conditions:

| Strategy | Trigger | Entry | Exit | Best For |
|----------|---------|-------|------|----------|
| **Trend Trading** | Bull + strong uptrend | Dips to MA support | Trend break | 20%+ sustained moves |
| **Breakout Trading** | Consolidation + low vol | Close above resistance | Below breakout | Volatility expansion |
| **Range Trading** | Sideways (neutral) | At support | At resistance | Choppy, low-vol markets |
| **Reversal Trading** | Bottom/top reversal detected | Confirm reversal pattern | Opposite reversal | Mean-reverting bounces |
| **Momentum Trading** | ROC >1% despite pullback | Dips in strong trend | Overbought (RSI >70) | Add to winning positions |

Technical confirmation (RSI <70 for buy, >30 for sell) + macro overlay (reduce size in bearish macro).

## Macro Overlay (Portfolio-Level)

Adjusts leverage based on macro conditions:

| Condition | Leverage Multiplier | Rationale |
|-----------|---|---|
| VIX >30, inverted curve, high rates | 0.5x | Risk-off environment |
| VIX 15-20, normal curve, moderate rates | 1.0x | Neutral macro |
| VIX <15, normal curve, stable rates | 1.5x | Risk-on environment |

Applied to all positions equally. Reduces risk in bearish macro, increases in bullish.

## Safety Rules (Hardcoded)

- **Max daily loss**: 2% of opening value → position throttle activates
- **Max drawdown**: 5% from peak → new trades limited
- **Stop loss**: 8% below entry → force close
- **Circuit breaker**: Both limits breach → halt trading
- **Error resilience**: >5 consecutive errors → shutdown (prevents cascading failures)

## Important

- **Paper trading only** — Start with `APCA_BASE_URL=https://paper-api.alpaca.markets`
- **Live trading prep** — Validate 2+ weeks of paper trading before switching to live keys
- **Regime-based sizing** — Position limits adjust dynamically, not static 5%
- **All decisions logged** — `journal/YYYY-MM-DD.md` contains full reasoning chain
- **State persistence** — `journal/orchestrator_state.json` tracks errors, enables recovery

## Monitoring

- **Daily logs:** `journal/YYYY-MM-DD.md` — research, trades, EOD summary
- **Regime history:** `journal/regime_history.json` — regime + confidence over time
- **Safety state:** `journal/safety_state.json` — peak capital, daily P&L, throttle
- **Error tracking:** `journal/orchestrator_state.json` — error count, last successful run
- **Dashboard:** Streamlit UI updates every 60 seconds

## Backtesting

Walk-forward test (avoids look-ahead bias):
```bash
python scripts/backtest.py
```

Trains on 60 days, tests on 20 days, rolling window. Returns Sharpe ratio, total return, drawdown.

## Troubleshooting

**API connection fails:**
```bash
python scripts/research.py account
```
If this fails, check `.env` credentials and internet connection.

**Market closed error:**
Market-dependent routines skip automatically. Check next open time in status output.

**Circuit breaker active:**
Check `journal/safety_state.json` for daily loss % and drawdown %. Wait until reset or reduce portfolio exposure.

**Component sync fails:**
Run `python scripts/orchestrate.py init` to reinitialize all systems.

## Costs

- **Claude inference**: ~$5-10/month for 3 daily sessions
- **Alpaca**: Free for stocks, some crypto fees
- **Hosting** (if remote): ~$5-10/month for light VPS

Streamlit dashboard runs locally or free at streamlit.io.
