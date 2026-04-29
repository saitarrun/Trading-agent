"""Track position entry prices and detect exits to record trades."""

import json
import os
from datetime import datetime
from pathlib import Path

class PositionTracker:
    """Track open positions, detect exits, record trades to performance tracker."""

    def __init__(self, tracker_file="journal/position_tracker.json"):
        self.tracker_file = tracker_file
        self.positions = self._load_positions()

    def _load_positions(self):
        """Load existing position tracking data."""
        if os.path.exists(self.tracker_file):
            try:
                with open(self.tracker_file) as f:
                    return json.load(f)
            except:
                return {}
        return {}

    def record_entry(self, symbol, strategy, regime, entry_price, qty, entry_time=None):
        """Record position entry (or update if exists)."""
        if symbol not in self.positions:
            self.positions[symbol] = {}

        self.positions[symbol] = {
            "strategy": strategy,
            "regime": regime,
            "entry_price": entry_price,
            "qty": qty,
            "entry_time": entry_time or datetime.now().isoformat()
        }
        self._save_positions()

    def get_entry(self, symbol):
        """Get entry info for a symbol."""
        return self.positions.get(symbol)

    def detect_exit(self, symbol, current_price, current_qty):
        """Detect if position was exited.

        Returns (exited, exit_price) tuple if exited, (False, None) if still open.
        """
        entry = self.positions.get(symbol)
        if not entry:
            return False, None

        entry_qty = entry.get("qty", 0)

        # Position was reduced/closed
        if current_qty < entry_qty or current_qty == 0:
            return True, current_price

        return False, None

    def close_position(self, symbol):
        """Remove position from tracking (after recording exit)."""
        if symbol in self.positions:
            del self.positions[symbol]
            self._save_positions()

    def _save_positions(self):
        """Persist positions to disk."""
        Path(self.tracker_file).parent.mkdir(parents=True, exist_ok=True)
        with open(self.tracker_file, 'w') as f:
            json.dump(self.positions, f, indent=2)

    def get_all(self):
        """Get all tracked positions."""
        return self.positions


if __name__ == "__main__":
    tracker = PositionTracker()

    # Test
    tracker.record_entry("AAPL", "trend_trading", "bull", 150.00, 100, "2026-04-28 10:00")
    tracker.record_entry("MSFT", "breakout_trading", "neutral", 300.00, 50, "2026-04-28 10:05")

    print("Tracked positions:", tracker.get_all())
    print("AAPL entry:", tracker.get_entry("AAPL"))

    # Detect exits
    exited_aapl, exit_price = tracker.detect_exit("AAPL", 152.00, 0)  # Closed
    print(f"AAPL exited: {exited_aapl} at ${exit_price}")

    exited_msft, exit_price = tracker.detect_exit("MSFT", 305.00, 50)  # Still open
    print(f"MSFT exited: {exited_msft}")
