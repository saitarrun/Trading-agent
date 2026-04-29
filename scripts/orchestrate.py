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
from macro import MacroAnalyzer
from technical import TechnicalAnalyzer
from fundamentals import FundamentalAnalyzer, SectorAnalyzer
from strategies import StrategySelector
from performance import PerformanceTracker
from position_tracker import PositionTracker

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
    """Morning routine: macro → sector → stock analysis, detect regime, log findings."""
    print("[RESEARCH] Starting morning research routine...")

    try:
        market_status = get_market_status()
        if not market_status.get("is_open"):
            print(f"[RESEARCH] Market closed. Next open: {market_status['next_open']}")
            return False

        account = get_account()
        today_date = datetime.now().strftime("%Y-%m-%d")
        journal_file = Path(f"journal/{today_date}.md")

        # MACRO ANALYSIS (Top-down start)
        print("[RESEARCH] Running macro analysis...")
        macro = MacroAnalyzer()
        macro_data = macro.analyze()
        print(f"[RESEARCH] Macro sentiment: {macro_data['macro_sentiment']} (VIX: {macro_data['vix']:.1f})")

        # SECTOR ANALYSIS
        print("[RESEARCH] Running sector analysis...")
        sector_analyzer = SectorAnalyzer()
        sector_data = sector_analyzer.analyze()
        print(f"[RESEARCH] Top sector: {sector_data['ranked_sectors'][0]['sector'] if sector_data['ranked_sectors'] else 'N/A'}")

        # STOCK-LEVEL ANALYSIS
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
                    bars_list = bars_response["bars"]
                    # Handle both dict (old API) and list (new API) formats
                    if isinstance(bars_list, dict):
                        bars_list = list(bars_list.values())
                    bars = [
                        {"c": b["c"], "h": b["h"], "l": b["l"]}
                        for b in bars_list
                    ]

                    if len(bars) >= 20:
                        # Regime detection
                        regime_detector.fit(bars)
                        regime, confidence, uncertain = regime_detector.predict_regime(bars)
                        characteristics = regime_detector.get_regime_characteristics(regime, uncertain)

                        # Technical analysis
                        tech_analyzer = TechnicalAnalyzer(bars)
                        tech_data = tech_analyzer.analyze()

                        # Strategy selection
                        strategy_selector = StrategySelector(bars)
                        strategy_data = strategy_selector.analyze()

                        # Fundamental analysis
                        fund_analyzer = FundamentalAnalyzer(symbol)
                        fund_data = fund_analyzer.analyze()

                        findings.append({
                            "symbol": symbol,
                            "regime": regime,
                            "confidence": float(confidence),
                            "uncertain": uncertain,
                            "characteristics": characteristics,
                            "technical": {
                                "rsi": tech_data['rsi'],
                                "macd_bullish": tech_data['macd']['bullish'],
                                "trend": tech_data['trend'],
                                "signal": tech_data['trade_signal']
                            },
                            "strategy": {
                                "selected": strategy_data['selected_strategy'],
                                "confidence": strategy_data['strategy_details'].get('confidence', 0)
                            },
                            "fundamental": {
                                "overall_score": fund_data['overall_score'] if fund_data else 0,
                                "qualifies": fund_data['qualifies'] if fund_data else False
                            }
                        })

                        status = "UNCERTAIN" if uncertain else "stable"
                        print(f"[RESEARCH] {symbol}: {regime} (tech: {tech_data['trade_signal']}, strategy: {strategy_data['selected_strategy']}, fund: {fund_data['overall_score']:.0f}/100)")
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
            "macro": macro_data,
            "sectors": sector_data,
            "regime": findings[0]["regime"] if findings else "neutral",
            "confidence": findings[0]["confidence"] if findings else 0.0,
            "characteristics": findings[0]["characteristics"] if findings else {}
        })

        with open(regime_history_file, 'w') as f:
            json.dump(regime_history, f, indent=2, default=str)

        journal_content = f"# Trade Journal — {today_date}\n\n"
        journal_content += "## Macro Analysis\n"
        journal_content += f"- Sentiment: {macro_data['macro_sentiment']} (score: {macro_data['macro_score']:.2f})\n"
        journal_content += f"- VIX: {macro_data['vix']:.1f}\n"
        journal_content += f"- Yield curve: {macro_data['yield_curve_status']}\n"
        journal_content += f"- Leverage multiplier: {macro_data['leverage_multiplier']:.2f}x\n"

        journal_content += "\n## Sector Analysis\n"
        for rank_item in sector_data.get('ranked_sectors', [])[:5]:
            journal_content += f"- {rank_item['rank']}. {rank_item['sector']}: {rank_item['return']:.2%}\n"

        journal_content += "\n## Stock Research\n"
        for finding in findings:
            journal_content += f"\n### {finding['symbol']}\n"
            journal_content += f"- Regime: {finding['regime']} (confidence: {finding['confidence']:.2%})\n"
            journal_content += f"- Technical: RSI {finding['technical']['rsi']:.0f}, MACD {'bullish' if finding['technical']['macd_bullish'] else 'bearish'}, Trend: {finding['technical']['trend']}\n"
            journal_content += f"- Signal: {finding['technical']['signal']} | Strategy: {finding['strategy']['selected']}\n"
            journal_content += f"- Fundamental score: {finding['fundamental']['overall_score']:.0f}/100 {'✓' if finding['fundamental']['qualifies'] else '✗'}\n"

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
    """Main trading routine: evaluate regime + macro + technical and place trades."""
    print("[TRADING] Starting trading session...")

    try:
        watchlist_path = Path("watchlist.json")
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
        macro_data = regime_data.get("macro", {})
        sector_data = regime_data.get("sectors", {})

        print(f"[TRADING] Current regime: {regime} (macro: {macro_data.get('macro_sentiment', 'unknown')})")

        allocator = PortfolioAllocator(risk_tolerance="moderate")

        # Get bars for volatility/trend calculation
        try:
            bars_response = get_bars("SPY", "1Day", limit=50)
            if "bars" in bars_response:
                bars_list = bars_response["bars"]
                if isinstance(bars_list, dict):
                    bars_list = list(bars_list.values())
                bars = [{"c": b["c"], "h": b["h"], "l": b["l"]} for b in bars_list]
            else:
                bars = None
        except:
            bars = None

        # Calculate allocation with macro + technical overlay
        macro_multiplier = macro_data.get('leverage_multiplier', 1.0)
        sector_weights = sector_data.get('sector_weights', {})

        # Get SPY technical signal for market-level confirmation
        spy_tech_signal = "hold"
        if bars:
            try:
                spy_tech = TechnicalAnalyzer(bars)
                spy_analysis = spy_tech.analyze()
                spy_tech_signal = spy_analysis['trade_signal']
            except:
                pass

        allocation = allocator.calculate_allocation(
            regime,
            current_value,
            positions if isinstance(positions, list) else [],
            bars,
            regime_data.get("uncertain", False),
            macro_multiplier=macro_multiplier,
            sector_weights=sector_weights,
            technical_signal=spy_tech_signal
        )

        print(f"[TRADING] Max position size: ${allocation['max_position_size']:,.0f}")
        print(f"[TRADING] Target cash: ${allocation['target_cash']:,.0f}")
        print(f"[TRADING] Leverage: {allocation['leverage_multiplier']:.2f}x (macro: {macro_multiplier:.2f}x, tech: {spy_tech_signal})")

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

        # Load performance tracker and position tracker
        performance_tracker = PerformanceTracker()
        position_tracker = PositionTracker()

        # Check for exited positions and record trades
        for symbol, entry_data in list(position_tracker.get_all().items()):
            existing_pos = next((p for p in (positions if isinstance(positions, list) else []) if p['symbol'] == symbol), None)
            current_qty = int(existing_pos['qty']) if existing_pos else 0

            exited, exit_price = position_tracker.detect_exit(symbol, bars[-1]['c'] if bars else 0, current_qty)
            if exited and exit_price:
                entry_price = entry_data['entry_price']
                strategy = entry_data['strategy']
                regime_at_entry = entry_data['regime']
                qty = entry_data['qty']
                performance_tracker.record_trade(symbol, strategy, regime_at_entry, entry_price, exit_price, qty, entry_data['entry_time'], datetime.now().isoformat())
                position_tracker.close_position(symbol)

        today_date = datetime.now().strftime("%Y-%m-%d")
        journal_file = Path(f"journal/{today_date}.md")

        journal_entry = f"\n## Trades Executed\n"
        journal_entry += f"| Time | Symbol | Action | Qty | Price | Reasoning |\n"
        journal_entry += f"|------|--------|--------|-----|-------|----------|\n"
        journal_entry += f"| - | - | - | - | - | No trades executed (regime: {regime}) |\n"

        # Execute trades for each watchlist symbol
        trades_executed = []
        with open(watchlist_path, 'r') as f:
            watchlist = json.load(f)

        for ticker in watchlist.get("watchlist", []):
            symbol = ticker["symbol"]

            # Get bars for this symbol
            try:
                bars_response = get_bars(symbol, "1Day", limit=50)
                if "bars" in bars_response:
                    bars_list = bars_response["bars"]
                    if isinstance(bars_list, dict):
                        bars_list = list(bars_list.values())
                    bars = [{"c": b["c"], "h": b["h"], "l": b["l"]} for b in bars_list]
                else:
                    bars = None
            except:
                bars = None

            if not bars:
                continue

            # Evaluate and execute
            trade_result = evaluate_and_trade(symbol, regime, bars, account, positions, allocator, safety, safety_status, performance_tracker, position_tracker, market_status, regime_data.get("uncertain", False))

            if trade_result:
                trades_executed.append(trade_result)
                print(f"[TRADING] {symbol}: {trade_result['action']} {trade_result.get('qty', 0)} @ ${trade_result.get('price', 0):.2f}")

        # Log trades
        journal_entry = f"\n## Trades Executed\n"
        journal_entry += f"| Time | Symbol | Action | Qty | Price | Reasoning |\n"
        journal_entry += f"|------|--------|--------|-----|-------|----------|\n"

        if trades_executed:
            for trade in trades_executed:
                if trade['action'] != 'hold':
                    journal_entry += f"| {datetime.now().strftime('%H:%M')} | {trade['symbol']} | {trade['action'].upper()} | {trade.get('qty', 0)} | ${trade.get('price', 0):.2f} | {trade.get('reason', 'N/A')} |\n"
        else:
            journal_entry += f"| - | - | - | - | - | No trades (regime: {regime}) |\n"

        with open(journal_file, 'a') as f:
            f.write(journal_entry)

        print("[TRADING] Session complete. Trades logged.")
        state.record_routine("trading", success=True)
        return True

    except Exception as e:
        print(f"[TRADING] ERROR: {e}")
        traceback.print_exc()
        state.record_routine("trading", success=False)
        return False

def evaluate_and_trade(symbol, regime, bars, account, positions, allocator, safety, safety_status, performance_tracker=None, position_tracker=None, market_status=None, uncertain=False):
    """Evaluate single symbol using regime + technical + strategy, place orders if conditions met."""
    try:
        if not market_status or not market_status.get("is_open"):
            return None

        current_price = bars[-1]["c"] if bars else None
        if not current_price:
            return None

        account_value = float(account['portfolio_value'])

        # Technical analysis
        tech_analyzer = TechnicalAnalyzer(bars)
        tech_data = tech_analyzer.analyze()
        tech_signal = tech_data['trade_signal']

        # Strategy selection with performance feedback
        strategy_selector = StrategySelector(bars, regime=regime, performance_tracker=performance_tracker)
        strategy_data = strategy_selector.analyze()
        selected_strategy = strategy_data['selected_strategy']
        base_confidence = strategy_data['strategy_details']['confidence']

        # Note: confidence may have been adjusted by performance tracker
        final_confidence = strategy_data['strategy_details'].get('confidence', base_confidence)

        # Get allocation for this regime
        allocation = allocator.calculate_allocation(
            regime,
            account_value,
            positions if isinstance(positions, list) else [],
            bars,
            uncertain,
            technical_signal=tech_signal
        )
        max_size = allocation["max_position_size"]
        leverage = allocation["leverage_multiplier"]

        # Check if position already exists
        existing_pos = next((p for p in (positions if isinstance(positions, list) else []) if p['symbol'] == symbol), None)
        current_qty = int(existing_pos['qty']) if existing_pos else 0

        # Decide action based on regime + technical confirmation + strategy
        action = None
        reason = ""

        if regime == "crash":
            action = "sell" if current_qty > 0 else None
            reason = "Crash regime - liquidate"
        elif regime == "bear":
            if tech_signal == "sell":
                action = "sell" if current_qty > 0 else None
                reason = f"Bear regime + technical sell signal"
            else:
                reason = "Bear regime - hold"
        elif regime == "euphoria":
            if current_qty > 0 and tech_signal == "sell":
                action = "sell"
                reason = "Euphoria + technical sell - take profits"
            else:
                reason = "Euphoria - reduce"
        elif regime == "bull":
            if tech_signal == "buy" and selected_strategy == "breakout_trading":
                action = "buy" if current_qty == 0 else None
                reason = f"Bull regime + breakout confirmation"
            elif tech_signal == "buy" and current_qty == 0:
                action = "buy"
                reason = f"Bull regime + {selected_strategy} signal"
        else:  # neutral
            if tech_signal == "buy" and selected_strategy in ["range_trading", "momentum_trading"]:
                action = "buy" if current_qty == 0 else None
                reason = f"Neutral with {selected_strategy} + tech buy"
            else:
                reason = f"Neutral regime - hold (strategy: {selected_strategy})"

        if not action or not safety_status['trading_enabled']:
            return {
                "symbol": symbol,
                "action": "hold",
                "qty": 0,
                "price": current_price,
                "reason": reason if reason else f"No signal (safety: {safety_status['trading_enabled']})"
            }

        # Size position
        qty = int(max_size / current_price) if max_size > 0 else 0
        if qty == 0:
            return {"symbol": symbol, "action": "hold", "qty": 0, "price": current_price, "reason": "Position size too small"}

        # Apply strategy performance multiplier (boost winning strategies, reduce losers)
        if performance_tracker:
            strategy_mult = performance_tracker.get_strategy_adjustment_multiplier(selected_strategy, regime)
            qty = int(qty * strategy_mult)

        # Apply throttle
        throttle = safety.calculate_throttle_factor(account_value)
        qty = int(qty * throttle)

        if action == "sell" and current_qty > 0:
            sell_qty = current_qty
            limit_price = current_price * 0.99
            from trade import place_order, validate_order
            if not validate_order(symbol, sell_qty, "sell", current_price, account_value, positions if isinstance(positions, list) else []):
                return {"symbol": symbol, "action": "hold", "qty": 0, "price": current_price, "reason": "Order validation failed"}
            result = place_order(symbol, sell_qty, "sell", limit_price)
            return {
                "symbol": symbol,
                "action": "sell",
                "qty": sell_qty,
                "price": limit_price,
                "reason": reason,
                "order_result": result
            }
        elif action == "buy" and qty > 0:
            limit_price = current_price * 1.001
            from trade import place_order, validate_order
            if not validate_order(symbol, qty, "buy", current_price, account_value, positions if isinstance(positions, list) else []):
                return {"symbol": symbol, "action": "hold", "qty": 0, "price": current_price, "reason": "Order validation failed"}
            result = place_order(symbol, qty, "buy", limit_price)

            # Record entry in position tracker for exit detection
            if position_tracker:
                position_tracker.record_entry(symbol, selected_strategy, regime, current_price, qty)

            return {
                "symbol": symbol,
                "action": "buy",
                "qty": qty,
                "price": limit_price,
                "reason": reason,
                "order_result": result
            }

        return {"symbol": symbol, "action": "hold", "qty": 0, "price": current_price, "reason": reason}

    except Exception as e:
        print(f"[TRADING] Error evaluating {symbol}: {e}")
        return {"symbol": symbol, "action": "error", "error": str(e)}

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
    last_research_hour = -1
    last_trading_hour = -1
    last_eod_hour = -1

    while True:
        iteration += 1
        now = datetime.now()
        print(f"\n[LOOP] Iteration {iteration} at {now.isoformat()}")

        try:
            if not state.is_healthy():
                print(f"[LOOP] System unhealthy. Error count: {state.error_count}. Shutting down.")
                break

            market_status = get_market_status()

            # B5 FIX: Time-based dispatch of routines
            if market_status.get("is_open"):
                print(f"[LOOP] Market is open. Checking scheduled routines...")

                # 9:45 AM ET: Run research
                if now.hour == 9 and now.minute >= 45 and last_research_hour != now.hour:
                    print("[LOOP] Running research routine (9:45 AM)...")
                    run_research_routine(state)
                    last_research_hour = now.hour

                # 10:00 AM ET: Run trading
                if now.hour == 10 and now.minute >= 0 and last_trading_hour != now.hour:
                    print("[LOOP] Running trading routine (10:00 AM)...")
                    run_trading_routine(state)
                    last_trading_hour = now.hour

                # 12:00 PM ET: Midday check
                if now.hour == 12 and now.minute >= 0:
                    account = get_account()
                    safety = SafetyManager(initial_capital=float(account['portfolio_value']))
                    safety_status = safety.get_circuit_breaker_status(float(account['portfolio_value']))
                    if not safety_status['trading_enabled']:
                        throttle = safety.calculate_throttle_factor(float(account['portfolio_value']))
                        print(f"[LOOP] Midday check: Circuit breaker active. Throttle: {throttle:.0%}")
                    else:
                        print("[LOOP] Midday check: System nominal.")

                # 4:15 PM ET: Run EOD
                if now.hour == 16 and now.minute >= 15 and last_eod_hour != now.hour:
                    print("[LOOP] Running EOD routine (4:15 PM)...")
                    run_eod_routine(state)
                    last_eod_hour = now.hour
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
