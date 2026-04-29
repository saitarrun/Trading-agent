"""Macroeconomic analysis for portfolio-level leverage adjustment."""

import yfinance as yf
import numpy as np
from datetime import datetime, timedelta
import json

class MacroAnalyzer:
    """Top-level macro conditions affecting leverage."""

    def __init__(self):
        self.vix_level = None
        self.yield_curve_status = None
        self.fed_funds = None
        self.macro_score = 0.0  # -1 to 1 scale
        self.macro_sentiment = "neutral"

    def get_vix(self):
        """Fetch VIX (volatility index)."""
        try:
            vix = yf.download("^VIX", period="1d", progress=False)
            if vix is not None and len(vix) > 0:
                self.vix_level = float(vix["Close"].iloc[-1])
                return self.vix_level
        except Exception as e:
            print(f"[MACRO] VIX fetch failed: {e}")
        return None

    def get_yield_curve(self):
        """Check yield curve inversion (10Y - 2Y)."""
        try:
            # Fetch 10-year and 2-year Treasury yields
            tnx = yf.download("^TNX", period="1d", progress=False)  # 10-year
            tlt = yf.download("SHY", period="1d", progress=False)   # Short-term (proxy for 2-year)

            if tnx is not None and tlt is not None and len(tnx) > 0 and len(tlt) > 0:
                yield_10y = float(tnx["Close"].iloc[-1])
                yield_2y = float(tlt["Close"].iloc[-1])

                curve_diff = yield_10y - yield_2y
                self.yield_curve_status = "inverted" if curve_diff < 0 else "normal"
                return curve_diff, self.yield_curve_status
        except Exception as e:
            print(f"[MACRO] Yield curve fetch failed: {e}")

        return 0, "unknown"

    def get_fed_funds_rate(self):
        """Get current Fed Funds rate proxy (via 3-month T-bill)."""
        try:
            irx = yf.download("^IRX", period="1d", progress=False)  # 13-week T-bill
            if irx is not None and len(irx) > 0:
                self.fed_funds = float(irx["Close"].iloc[-1])
                return self.fed_funds
        except Exception as e:
            print(f"[MACRO] Fed funds fetch failed: {e}")
        return None

    def calculate_macro_score(self):
        """
        Calculate macro sentiment score (-1 to 1).
        -1 = very bearish (high VIX, inverted curve, high rates)
        0 = neutral
        1 = very bullish (low VIX, normal curve, moderate rates)
        """
        score = 0.0
        weights = 0

        # VIX component (-1 to 1 scale)
        if self.vix_level is not None:
            vix_score = -min(self.vix_level / 50, 1.0)  # High VIX = negative
            vix_score = max(vix_score, -1.0)
            score += vix_score * 0.4
            weights += 0.4

        # Yield curve component
        if self.yield_curve_status == "inverted":
            score -= 0.3
            weights += 0.3
        elif self.yield_curve_status == "normal":
            score += 0.15
            weights += 0.3

        # Fed funds component (very high rates = bearish)
        if self.fed_funds is not None:
            rates_score = -min(self.fed_funds / 8, 1.0)  # 8% = max negative
            score += rates_score * 0.3
            weights += 0.3

        if weights > 0:
            self.macro_score = score / weights
        else:
            self.macro_score = 0.0

        # Classify sentiment
        if self.macro_score < -0.3:
            self.macro_sentiment = "bearish"
        elif self.macro_score > 0.3:
            self.macro_sentiment = "bullish"
        else:
            self.macro_sentiment = "neutral"

        return self.macro_score, self.macro_sentiment

    def get_macro_leverage_multiplier(self):
        """
        Return leverage adjustment multiplier based on macro conditions.
        Bearish macro (inverted curve, high VIX) → reduce leverage
        Bullish macro (low VIX, normal curve) → increase leverage
        """
        self.calculate_macro_score()

        # Map score to leverage multiplier
        # Score -1 → 0.5x (half leverage in bad macro)
        # Score 0 → 1.0x (normal leverage)
        # Score 1 → 1.5x (increased leverage in good macro)
        multiplier = 1.0 + (self.macro_score * 0.5)
        multiplier = max(0.5, min(1.5, multiplier))

        return multiplier

    def analyze(self):
        """Run full macro analysis."""
        self.get_vix()
        curve_diff, curve_status = self.get_yield_curve()
        self.get_fed_funds_rate()
        macro_score, sentiment = self.calculate_macro_score()

        return {
            "vix": self.vix_level,
            "yield_curve_diff": curve_diff,
            "yield_curve_status": curve_status,
            "fed_funds_rate": self.fed_funds,
            "macro_score": macro_score,
            "macro_sentiment": sentiment,
            "leverage_multiplier": self.get_macro_leverage_multiplier(),
            "timestamp": datetime.now().isoformat()
        }


if __name__ == "__main__":
    analyzer = MacroAnalyzer()
    result = analyzer.analyze()
    print(json.dumps(result, indent=2))
