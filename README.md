# 24/7 AI Trading Agent with Regime Detection

Autonomous trading agent using Claude Code, Alpaca API, and Hidden Markov Models for market regime detection. Runs on paper trading (default) with regime-aware allocation and hardcoded circuit breakers.

## Architecture

**Brain (HMM Regime Detection):** Detects market state (crash, bear, neutral, bull, euphoria)
  - Auto-detects optimal states (3-7) via BIC
  - Forward algorithm only (prevents look-ahead bias)
  - Stability filter (3-bar persistence, no flickering)
  - Uncertainty detection (flags regimes with >4 changes in 20 bars)
  - Trained on 2+ years of historical data

**Allocation Engine:** Dynamically sizes positions based on regime + volatility
  - Volatility-based sizing (high vol = reduce exposure, low vol = increase)
  - Trend-aware allocation (strong trends = increase, weak = reduce)
  - Risk tolerance customization (conservative/moderate/aggressive)
  - Uncertainty discount (reduce all sizes if regime is flickering)
**Safety Net:** Circuit breakers (2% daily loss, 5% max drawdown) + throttling
**Risk Manager:** Position validation, stop-loss enforcement
**Dashboard:** Streamlit UI for monitoring

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

**Core Engine:**
- `scripts/regime.py` — HMM for crash/bear/neutral/bull/euphoria detection
- `scripts/allocation.py` — Dynamic position sizing per regime
- `scripts/safety.py` — Circuit breakers (2% daily loss, 5% drawdown)
- `scripts/backtest.py` — Walk-forward backtesting (no look-ahead bias)
- `scripts/orchestrate.py` — Main orchestration + error handling

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

## Market Regimes

| Regime | Signal | Action |
|--------|--------|--------|
| Crash | ↓ High vol | 0x leverage, 95% cash |
| Bear | ↓ Medium vol | 0.5x leverage, 70% cash |
| Neutral | ↔ Low vol | 1.0x leverage, 20% cash |
| Bull | ↑ Medium vol | 1.5x leverage, 15% cash |
| Euphoria | ↑ High vol | 1.0x leverage, 30% cash |

Agent detects via HMM on 20-day returns + intraday volatility.

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
