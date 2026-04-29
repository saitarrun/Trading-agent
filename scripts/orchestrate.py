#!/usr/bin/env python3
"""Main orchestration engine. Ties regime, allocation, and safety together."""

import json
import sys
import time
import traceback
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

from research import get_bars, get_account, get_positions
from regime import MarketRegimeDetector
from allocation import PortfolioAllocator
from safety import SafetyManager
from trade import get_market_status

class OrchestratorState:
    """Tracks system state for resilience and error handling."""

    def __init__(self):
        self.state_file = Path("journal/orchestrator_state.json")
        self.last_research = None
        self.last_trading = None
        self.last_eod = None
        self.error_count = 0
        self.api_healthy = True
        self.load_state()

    def load_state(self):
        """Load previous state from disk."""
        if self.state_file.exists():
            try:
                with open(self.state_file, 'r') as f:
                    state = json.load(f)
                    self.last_research = state.get("last_research")
                    self.last_trading = state.get("last_trading")
                    self.last_eod = state.get("last_eod")
                    self.error_count = state.get("error_count", 0)
            except Exception as e:
                print(f"[STATE] Warning: Could not load state: {e}")

    def save_state(self):
        """Save state to disk for recovery."""
        state = {
            "last_research": self.last_research,
            "last_trading": self.last_trading,
            "last_eod": self.last_eod,
            "error_count": self.error_count,
            "timestamp": datetime.now().isoformat()
        }
        with open(self.state_file, 'w') as f:
            json.dump(state, f, indent=2)

    def record_routine(self, routine_name, success):
        """Record routine execution."""
        if routine_name == "research":
            self.last_research = datetime.now().isoformat() if success else None
        elif routine_name == "trading":
            self.last_trading = datetime.now().isoformat() if success else None
        elif routine_name == "eod":
            self.last_eod = datetime.now().isoformat() if success else None

        if not success:
            self.error_count += 1
        else:
            self.error_count = max(0, self.error_count - 1)

        self.save_state()

    def is_healthy(self):
        """Check if system is in healthy state."""
        return self.error_count < 5 and self.api_healthy

def initialize_system():
    """Startup: Verify configs, API connection, market status."""
    print("[INIT] Starting system initialization...")

    try:
        env_vars = ['APCA_API_KEY_ID', 'APCA_API_SECRET_KEY', 'APCA_BASE_URL']
        for var in env_vars:
            if not __import__('os').getenv(var):
                print(f"[INIT] ERROR: Missing environment variable {var}")
                return False

        print("[INIT] ✓ Configuration loaded")

        try:
            account = get_account()
            print(f"[INIT] ✓ Alpaca API connection verified (Account: {account.get('account_number')})")
        except Exception as e:
            print(f"[INIT] ERROR: Cannot connect to Alpaca API: {e}")
            return False

        try:
            market_status = get_market_status()
            is_open = market_status.get("is_open", False)
            status_msg = "OPEN" if is_open else "CLOSED"
            next_open = market_status.get("next_open", "unknown")
            print(f"[INIT] ✓ Market status: {status_msg} (next open: {next_open})")
        except Exception as e:
            print(f"[INIT] ERROR: Cannot fetch market status: {e}")
            return False

        watchlist_path = Path("watchlist.json")
        if not watchlist_path.exists():
            print(f"[INIT] ERROR: watchlist.json not found")
            return False
        print(f"[INIT] ✓ Watchlist loaded")

        journal_dir = Path("journal")
        journal_dir.mkdir(exist_ok=True)
        print(f"[INIT] ✓ Journal directory ready")

        print("[INIT] System ready. All components initialized.")
        return True

    except Exception as e:
        print(f"[INIT] FATAL ERROR: {e}")
        traceback.print_exc()
        return False

def sync_components():
    """Verify all components are initialized and ready."""
    print("[SYNC] Syncing components...")

    try:
        regime_detector = MarketRegimeDetector()
        print("[SYNC] ✓ Regime detector ready")

        allocator = PortfolioAllocator()
        print("[SYNC] ✓ Allocator ready")

        safety = SafetyManager()
        print("[SYNC] ✓ Safety manager ready")

        account = get_account()
        current_value = float(account.get('portfolio_value', 0))
        if current_value <= 0:
            print(f"[SYNC] WARNING: Invalid portfolio value: {current_value}")
            return False

        print(f"[SYNC] ✓ Portfolio value: ${current_value:,.0f}")
        print("[SYNC] All components synced and healthy.")
        return True

    except Exception as e:
        print(f"[SYNC] ERROR: Component sync failed: {e}")
        traceback.print_exc()
        return False

def run_research_routine(state):
    """Morning routine: fetch data, detect regime, log findings."""
    print("[RESEARCH] Starting morning research routine...")

    try:
        market_status = get_market_status()
        if not market_status.get("is_open"):
            print(f"[RESEARCH] Market closed. Next open: {market_status['next_open']}")
            return False

        account = get_account()
        today_date = datetime.now().strftime("%Y-%m-%d")
        journal_file = Path(f"journal/{today_date}.md")

        regime_detector = MarketRegimeDetector()
        findings = []

        watchlist_path = Path("watchlist.json")
        with open(watchlist_path, 'r') as f:
            watchlist = json.load(f)

        for ticker in watchlist.get("watchlist", []):
            symbol = ticker["symbol"]
            try:
                bars_response = get_bars(symbol, "1Day", limit=100)
                if "bars" in bars_response:
                    bars = [
                        {"c": b["c"], "h": b["h"], "l": b["l"]}
                        for b in bars_response["bars"].values()
                    ]

                    if len(bars) >= 20:
                        regime_detector.fit(bars)
                        regime, confidence, uncertain = regime_detector.predict_regime(bars)
                        characteristics = regime_detector.get_regime_characteristics(regime, uncertain)

                        findings.append({
                            "symbol": symbol,
                            "regime": regime,
                            "confidence": float(confidence),
                            "uncertain": uncertain,
                            "characteristics": characteristics
                        })

                        status = "UNCERTAIN" if uncertain else "stable"
                        print(f"[RESEARCH] {symbol}: {regime} (confidence: {confidence:.2%}, {status})")
            except Exception as e:
                print(f"[RESEARCH] Error processing {symbol}: {e}")

        regime_history_file = Path("journal/regime_history.json")
        regime_history = []
        if regime_history_file.exists():
            with open(regime_history_file, 'r') as f:
                regime_history = json.load(f)

        regime_history.append({
            "timestamp": datetime.now().isoformat(),
            "findings": findings,
            "regime": findings[0]["regime"] if findings else "neutral",
            "confidence": findings[0]["confidence"] if findings else 0.0,
            "characteristics": findings[0]["characteristics"] if findings else {}
        })

        with open(regime_history_file, 'w') as f:
            json.dump(regime_history, f, indent=2)

        journal_content = f"# Trade Journal — {today_date}\n\n"
        journal_content += "## Market Research\n"
        for finding in findings:
            journal_content += f"\n### {finding['symbol']}\n"
            journal_content += f"- Regime: {finding['regime']} (confidence: {finding['confidence']:.2%})\n"
            journal_content += f"- Volatility: {finding['characteristics']['volatility']}\n"
            journal_content += f"- Direction: {finding['characteristics']['direction']}\n"

        with open(journal_file, 'w') as f:
            f.write(journal_content)

        print(f"[RESEARCH] Findings logged to {journal_file}")
        state.record_routine("research", success=True)
        return True

    except Exception as e:
        print(f"[RESEARCH] ERROR: {e}")
        traceback.print_exc()
        state.record_routine("research", success=False)
        return False

def run_trading_routine(state):
    """Main trading routine: evaluate regime and place trades."""
    print("[TRADING] Starting trading session...")

    try:
        market_status = get_market_status()
        if not market_status.get("is_open"):
            print("[TRADING] Market closed, skipping trades.")
            return False

        account = get_account()
        positions = get_positions()
        current_value = float(account['portfolio_value'])

        regime_history_file = Path("journal/regime_history.json")
        regime_data = {}
        if regime_history_file.exists():
            with open(regime_history_file, 'r') as f:
                regime_history = json.load(f)
                regime_data = regime_history[-1] if regime_history else {}

        regime = regime_data.get("regime", "neutral")
        print(f"[TRADING] Current regime: {regime}")

        allocator = PortfolioAllocator(risk_tolerance="moderate")

        # Get bars for volatility/trend calculation
        try:
            bars_response = get_bars("SPY", "1Day", limit=50)
            bars = [{"c": b["c"], "h": b["h"], "l": b["l"]} for b in bars_response["bars"].values()] if "bars" in bars_response else None
        except:
            bars = None

        allocation = allocator.calculate_allocation(regime, current_value, positions if isinstance(positions, list) else [], bars, regime_data.get("uncertain", False))

        print(f"[TRADING] Max position size: ${allocation['max_position_size']:,.0f}")
        print(f"[TRADING] Target cash: ${allocation['target_cash']:,.0f}")
        print(f"[TRADING] Leverage: {allocation['leverage_multiplier']}x")

        safety = SafetyManager(initial_capital=current_value)
        safety_status = safety.get_circuit_breaker_status(current_value)

        print(f"[TRADING] Safety status: {'ENABLED' if safety_status['trading_enabled'] else 'DISABLED'}")
        print(f"[TRADING] Daily loss: {safety_status['daily_loss']['loss_pct']:.2f}%")
        print(f"[TRADING] Drawdown: {safety_status['drawdown']['drawdown_pct']:.2f}%")

        if not safety_status['trading_enabled']:
            throttle = safety.calculate_throttle_factor(current_value)
            print(f"[TRADING] Position throttle factor: {throttle:.2%}")

            if throttle == 0.0:
                print("[TRADING] CIRCUIT BREAKER ACTIVE - NO NEW TRADES")
                return False

        today_date = datetime.now().strftime("%Y-%m-%d")
        journal_file = Path(f"journal/{today_date}.md")

        journal_entry = f"\n## Trades Executed\n"
        journal_entry += f"| Time | Symbol | Action | Qty | Price | Reasoning |\n"
        journal_entry += f"|------|--------|--------|-----|-------|----------|\n"
        journal_entry += f"| - | - | - | - | - | No trades executed (regime: {regime}) |\n"

        with open(journal_file, 'a') as f:
            f.write(journal_entry)

        print("[TRADING] Session complete. Journal updated.")
        state.record_routine("trading", success=True)
        return True

    except Exception as e:
        print(f"[TRADING] ERROR: {e}")
        traceback.print_exc()
        state.record_routine("trading", success=False)
        return False

def run_eod_routine(state):
    """End-of-day routine: finalize journal and update state."""
    print("[EOD] Starting end-of-day routine...")

    try:
        account = get_account()
        current_value = float(account['portfolio_value'])

        safety = SafetyManager(initial_capital=current_value)
        safety.update_day_start(current_value)
        safety.update_peak(current_value)

        today_date = datetime.now().strftime("%Y-%m-%d")
        journal_file = Path(f"journal/{today_date}.md")

        eod_entry = f"\n## End-of-Day Summary\n"
        eod_entry += f"- Portfolio value: ${current_value:,.0f}\n"
        eod_entry += f"- Cash: ${float(account['cash']):,.0f}\n"
        eod_entry += f"- Status: Complete\n"

        with open(journal_file, 'a') as f:
            f.write(eod_entry)

        print(f"[EOD] Journal finalized at {journal_file}")
        state.record_routine("eod", success=True)
        return True

    except Exception as e:
        print(f"[EOD] ERROR: {e}")
        traceback.print_exc()
        state.record_routine("eod", success=False)
        return False

def run_main_loop(interval_seconds=300):
    """Main execution loop: runs on 5-minute bars (300 seconds).

    Continuously:
    1. Check market status
    2. Evaluate regime
    3. Check safety limits
    4. Trigger trades if conditions met
    """
    print(f"[LOOP] Starting main execution loop (interval: {interval_seconds}s)...")

    state = OrchestratorState()

    if not initialize_system():
        print("[LOOP] System initialization failed. Exiting.")
        return False

    if not sync_components():
        print("[LOOP] Component sync failed. Exiting.")
        return False

    iteration = 0
    while True:
        iteration += 1
        print(f"\n[LOOP] Iteration {iteration} at {datetime.now().isoformat()}")

        try:
            if not state.is_healthy():
                print(f"[LOOP] System unhealthy. Error count: {state.error_count}. Shutting down.")
                break

            market_status = get_market_status()
            if market_status.get("is_open"):
                print(f"[LOOP] Market is open. Checking regime and positions...")

                regime_history_file = Path("journal/regime_history.json")
                if regime_history_file.exists():
                    with open(regime_history_file, 'r') as f:
                        regime_history = json.load(f)
                        latest_regime = regime_history[-1].get("regime", "neutral") if regime_history else "neutral"
                else:
                    latest_regime = "neutral"

                account = get_account()
                safety = SafetyManager(initial_capital=float(account['portfolio_value']))
                safety_status = safety.get_circuit_breaker_status(float(account['portfolio_value']))

                if not safety_status['trading_enabled']:
                    print(f"[LOOP] Circuit breaker active. Throttle: {safety.calculate_throttle_factor(float(account['portfolio_value'])):.0%}")
            else:
                print(f"[LOOP] Market closed until {market_status.get('next_open')}")

            print(f"[LOOP] Sleeping for {interval_seconds}s until next check...")
            time.sleep(interval_seconds)

        except KeyboardInterrupt:
            print("[LOOP] Interrupted by user. Shutting down gracefully.")
            break
        except Exception as e:
            print(f"[LOOP] ERROR in main loop: {e}")
            traceback.print_exc()
            time.sleep(interval_seconds)

    print("[LOOP] Main loop exited.")
    return True

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python orchestrate.py [init|research|trading|eod|loop]")
        sys.exit(1)

    state = OrchestratorState()
    routine = sys.argv[1]

    if routine == "init":
        success = initialize_system() and sync_components()
    elif routine == "research":
        success = run_research_routine(state)
    elif routine == "trading":
        success = run_trading_routine(state)
    elif routine == "eod":
        success = run_eod_routine(state)
    elif routine == "loop":
        interval = int(sys.argv[2]) if len(sys.argv) > 2 else 300
        success = run_main_loop(interval)
    else:
        print(f"Unknown routine: {routine}")
        sys.exit(1)

    sys.exit(0 if success else 1)
