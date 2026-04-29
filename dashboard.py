import streamlit as st
import json
import os
from pathlib import Path
from datetime import datetime
import pandas as pd
import sys

sys.path.append(os.path.join(os.path.dirname(__file__), 'scripts'))

from research import get_positions, get_account
from regime import MarketRegimeDetector
from safety import SafetyManager

st.set_page_config(page_title="Trading Agent Dashboard", layout="wide")

st.title("🤖 AI Trading Agent Dashboard")

col1, col2, col3 = st.columns(3)

try:
    account = get_account()
    positions = get_positions()

    with col1:
        st.metric("Portfolio Value", f"${account['portfolio_value']:,.0f}")
        st.metric("Cash Available", f"${account['cash']:,.0f}")

    with col2:
        st.metric("Buying Power", f"${account['buying_power']:,.0f}")
        st.metric("Day Trade Count", account['daytrade_count'])

    with col3:
        st.metric("Status", account['status'])
        st.metric("Trading Blocked", "Yes" if account['trading_blocked'] else "No")

    st.divider()

    tab1, tab2, tab3, tab4 = st.tabs(["Positions", "Regime Analysis", "Safety Status", "Journal"])

    with tab1:
        st.subheader("Open Positions")
        if isinstance(positions, list) and len(positions) > 0:
            pos_data = []
            for pos in positions:
                pos_data.append({
                    "Symbol": pos['symbol'],
                    "Qty": pos['qty'],
                    "Entry Price": f"${pos['avg_fill_price']:.2f}",
                    "Current Price": f"${pos['current_price']:.2f}",
                    "P&L": f"${float(pos['unrealized_pl']):.2f}",
                    "P&L %": f"{float(pos['unrealized_plpc']):.2f}%",
                    "Market Value": f"${float(pos['market_value']):.2f}"
                })
            df = pd.DataFrame(pos_data)
            st.dataframe(df, use_container_width=True)
        else:
            st.info("No open positions")

    with tab2:
        st.subheader("Market Regime Detection")

        regime_file = Path("journal/regime_history.json")
        if regime_file.exists():
            with open(regime_file, 'r') as f:
                regime_history = json.load(f)

            latest = regime_history[-1] if regime_history else None
            if latest:
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Current Regime", latest['regime'].upper())
                with col2:
                    st.metric("Confidence", f"{latest['confidence']:.2%}")
                with col3:
                    st.metric("Last Update", latest['timestamp'])

                st.info(f"**Characteristics:**\n"
                       f"- Volatility: {latest['characteristics']['volatility']}\n"
                       f"- Direction: {latest['characteristics']['direction']}\n"
                       f"- Leverage: {latest['characteristics']['leverage']:.1f}x")

                st.line_chart(
                    pd.DataFrame(regime_history).set_index('timestamp')['confidence'],
                    title="Regime Confidence Over Time"
                )
        else:
            st.info("No regime data yet. Run morning research routine first.")

    with tab3:
        st.subheader("Safety & Risk Management")

        safety_file = Path("journal/safety_state.json")
        if safety_file.exists():
            with open(safety_file, 'r') as f:
                safety_state = json.load(f)

            safety_manager = SafetyManager()
            status = safety_manager.get_circuit_breaker_status(float(account['portfolio_value']))

            col1, col2 = st.columns(2)
            with col1:
                if status['trading_enabled']:
                    st.success("✓ Trading ENABLED")
                else:
                    st.error("✗ Trading DISABLED")

            with col2:
                throttle = safety_manager.calculate_throttle_factor(float(account['portfolio_value']))
                st.metric("Position Size Throttle", f"{throttle:.0%}")

            st.warning(
                f"Daily Loss: {status['daily_loss']['loss_pct']:.2f}% "
                f"(Limit: 2.0%) | "
                f"Drawdown: {status['drawdown']['drawdown_pct']:.2f}% "
                f"(Limit: 5.0%)"
            )

            col1, col2 = st.columns(2)
            with col1:
                st.metric("Peak Capital", f"${status['max_capital']:,.0f}")
            with col2:
                st.metric("Day Start Value", f"${status['day_start_value']:,.0f}")
        else:
            st.info("No safety data yet.")

    with tab4:
        st.subheader("Trade Journal")

        journal_dir = Path("journal")
        journal_files = sorted(journal_dir.glob("*.md"), reverse=True)

        if journal_files:
            selected_file = st.selectbox(
                "Select journal entry",
                [f.stem for f in journal_files]
            )

            if selected_file:
                file_path = journal_dir / f"{selected_file}.md"
                with open(file_path, 'r') as f:
                    content = f.read()
                st.markdown(content)
        else:
            st.info("No journal entries yet. Check back after first trading session.")

    st.divider()
    st.caption("Dashboard updates every 60 seconds. Refresh manually for latest data.")

except Exception as e:
    st.error(f"Error connecting to Alpaca API: {str(e)}")
    st.info("Ensure .env file has valid API credentials and you're connected to internet.")
