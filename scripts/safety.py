import json
from datetime import datetime
from pathlib import Path

class SafetyManager:
    """Circuit breakers and drawdown limits to prevent catastrophic losses."""

    def __init__(self, max_daily_loss_pct=2.0, max_drawdown_pct=5.0, initial_capital=100000):
        self.max_daily_loss_pct = max_daily_loss_pct
        self.max_drawdown_pct = max_drawdown_pct
        self.initial_capital = initial_capital
        self.max_capital = initial_capital
        self.state_file = Path("journal/safety_state.json")
        self.load_state()

    def load_state(self):
        """Load safety state from disk."""
        if self.state_file.exists():
            with open(self.state_file, 'r') as f:
                state = json.load(f)
                self.max_capital = max(state.get("max_capital", self.initial_capital), self.initial_capital)
                self.day_start_value = state.get("day_start_value", self.initial_capital)
        else:
            self.max_capital = self.initial_capital
            self.day_start_value = self.initial_capital

    def save_state(self):
        """Save safety state to disk."""
        state = {
            "max_capital": self.max_capital,
            "day_start_value": self.day_start_value,
            "timestamp": datetime.now().isoformat()
        }
        with open(self.state_file, 'w') as f:
            json.dump(state, f, indent=2)

    def check_daily_loss(self, current_value):
        """Check if daily loss exceeds limit.

        Returns (is_safe, loss_pct, message)
        """
        loss_pct = ((self.day_start_value - current_value) / self.day_start_value) * 100

        if loss_pct > self.max_daily_loss_pct:
            return False, loss_pct, f"Daily loss {loss_pct:.2f}% exceeds limit {self.max_daily_loss_pct}%"

        return True, loss_pct, "OK"

    def check_drawdown(self, current_value):
        """Check if drawdown from peak exceeds limit.

        Returns (is_safe, drawdown_pct, message)
        """
        drawdown_pct = ((self.max_capital - current_value) / self.max_capital) * 100

        if drawdown_pct > self.max_drawdown_pct:
            return False, drawdown_pct, f"Drawdown {drawdown_pct:.2f}% exceeds limit {self.max_drawdown_pct}%"

        return True, drawdown_pct, "OK"

    def update_peak(self, current_value):
        """Update max capital if new high achieved."""
        if current_value > self.max_capital:
            self.max_capital = current_value
            self.save_state()
            return True
        return False

    def update_day_start(self, current_value):
        """Update day start value (call at start of trading day)."""
        self.day_start_value = current_value
        self.save_state()

    def get_circuit_breaker_status(self, current_value):
        """Get overall circuit breaker status.

        Returns dict with status and all checks.
        """
        daily_safe, daily_loss, daily_msg = self.check_daily_loss(current_value)
        dd_safe, dd_loss, dd_msg = self.check_drawdown(current_value)

        trading_enabled = daily_safe and dd_safe

        return {
            "trading_enabled": trading_enabled,
            "daily_loss": {
                "safe": daily_safe,
                "loss_pct": daily_loss,
                "message": daily_msg
            },
            "drawdown": {
                "safe": dd_safe,
                "drawdown_pct": dd_loss,
                "message": dd_msg
            },
            "max_capital": self.max_capital,
            "day_start_value": self.day_start_value,
            "current_value": current_value
        }

    def calculate_throttle_factor(self, current_value):
        """Calculate position size multiplier based on safety status.

        Returns 0.0 (no trading) to 1.0 (full trading).
        """
        _, daily_loss, _ = self.check_daily_loss(current_value)
        _, dd_loss, _ = self.check_drawdown(current_value)

        throttle = 1.0

        if daily_loss > self.max_daily_loss_pct * 0.75:
            throttle = max(0.0, 1.0 - (daily_loss / self.max_daily_loss_pct))

        if dd_loss > self.max_drawdown_pct * 0.75:
            throttle = min(throttle, max(0.0, 1.0 - (dd_loss / self.max_drawdown_pct)))

        return throttle

if __name__ == "__main__":
    safety = SafetyManager(max_daily_loss_pct=2.0, max_drawdown_pct=5.0)

    test_values = [100000, 99500, 98500, 98000, 97500, 101000]
    for value in test_values:
        print(f"\nCurrent value: ${value:,.0f}")
        status = safety.get_circuit_breaker_status(value)
        throttle = safety.calculate_throttle_factor(value)
        print(f"Trading enabled: {status['trading_enabled']}")
        print(f"Daily loss: {status['daily_loss']['loss_pct']:.2f}%")
        print(f"Drawdown: {status['drawdown']['drawdown_pct']:.2f}%")
        print(f"Throttle factor: {throttle:.2f}")
        safety.update_peak(value)
