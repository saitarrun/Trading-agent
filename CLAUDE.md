# Trading Agent — Paper Trading with Regime-Aware Allocation

Autonomous AI trading agent on Alpaca paper trading. Detects market regimes (HMM), adapts allocation dynamically, places limit orders only, logs all decisions.

> **PRIME DIRECTIVE**: Capital preservation > returns. Never override safety limits. Never market orders. Full logging always.

## Code Reference Protocol (MANDATORY)

**Every code reference must use code-review-graph MCP tools FIRST:**
- Find: `semantic_search_nodes` 
- Callers/callees: `query_graph` pattern=`callers_of/callees_of`
- Impact: `get_impact_radius`
- Review: `detect_changes` + `get_review_context`
- Architecture: `get_architecture_overview`

Fall back to grep/read only when graph can't answer.

## Core Rules

See @ARCHITECTURE.md for full system design (13 modules, 5 layers).
See @docs/regimes.md for regime definitions & transitions.
See @docs/allocation.md for position sizing rules & formulas.
See @docs/safety.md for circuit breakers & hardcoded limits.
See @docs/execution.md for trade decision tree & pre-flight checks.

## Daily Schedule (ET, market days only)

| Time | Task | Module |
|------|------|--------|
| 9:30 AM | Pre-market check | `trade.py::get_market_status()` |
| 9:45 AM | Research (macro, sector, stock, technical) | `orchestrate.py::run_research_routine()` |
| 10:00 AM | Evaluate signals, place/adjust orders | `orchestrate.py::run_trading_routine()` |
| 12:00 PM | Midday check (circuit breaker, stops) | `safety.py::check_limits()` |
| 4:15 PM | EOD journal & reflect | `orchestrate.py::run_eod_routine()` |

## Regimes (HMM-Detected, 5 States)

| Regime | V | Trend | Behavior |
|--------|---|-------|----------|
| Crash | >3% | ↓ | Liquidate, 95% cash |
| Bear | 2-3% | ↓ | Reduce, 70% cash |
| Neutral | 0.5-1.5% | → | Balanced, 20% cash |
| Bull | 1-2% | ↑ | Expand, 15% cash |
| Euphoria | >2% | ↑ | Lock gains, 30% cash |

## Allocation Rules

Base by regime. Multiplied by: macro (0.5x-1.5x VIX/yields), sector (0.8x-1.2x rank), volatility (0.6x-1.2x), trend, technical signal, safety throttle (0.5x if circuit breaker hit).

Per-symbol caps: SPY 15%, QQQ 10%, NVDA/AAPL/MSFT 8% each.

## Hardcoded Safety (IMMUTABLE)

- **Max daily loss**: 2% → throttle to 50% size
- **Max drawdown**: 5% from peak → halt new entries  
- **Stop loss**: 8% decline → auto-close
- **Circuit breaker**: Both limits → HALT all trading

## Trade Checklist

Market open? Circuit breaker OK? Regime supports it? Technical confirms? Strategy >0.5 conf? Position ≤ regime + symbol caps? Cash reserve OK? Stop loss not hit?

**If any fails → HOLD, log reason.**

Always limit orders. Buy: ask × 1.002. Sell: bid × 0.998.

## Logging

- `journal/YYYY-MM-DD.md` — research, trades, EOD reflection
- `journal/regime_history.json` — regime + confidence per run
- `journal/safety_state.json` — peak capital, daily P&L, throttle state
- `journal/performance_stats.json` — strategy win rates, confidence adjustments

## Recovery

API fails? Retry 3x exponential backoff, then skip routine. No trades on unstable API.
Bad bars? Use yfinance fallback, skip if both fail.
HMM fail? Default neutral with 0.5 confidence + 0.7x uncertainty_adj.
Corrupt state? Re-init safe defaults (high cash). NEVER trade corrupted state.

## Security

**CRITICAL: Never commit .env to version control.**
- .env contains API keys. Must be in .gitignore (enforced).
- Use .env.example with placeholder values for repo reference.
- Before pushing: `git diff HEAD -- .env | grep -i key` → should be empty.
- If credentials exposed: rotate immediately in Alpaca dashboard.
- For live trading: use separate vault, never version-controlled files.
