import json
import numpy as np
from regime import MarketRegimeDetector

class PortfolioAllocator:
    """Dynamic portfolio allocation based on market regime and volatility.

    Features:
    - Volatility-based position sizing (reduce in turbulent markets)
    - Dynamic adjustments per regime
    - Customizable risk tolerance
    - Trend-aware allocation (increase in strong trends, reduce in uncertain)
    """

    def __init__(self, base_cash_reserve=0.20, risk_tolerance="moderate"):
        """Initialize allocator with risk tolerance profile.

        risk_tolerance: "conservative" (low), "moderate" (default), "aggressive" (high)
        """
        self.base_cash_reserve = base_cash_reserve
        self.risk_tolerance = risk_tolerance

        # Base allocations (modified by volatility)
        self.regime_allocations = {
            "crash": {
                "position_size_pct": 0.01,
                "max_leverage": 0.0,
                "cash_reserve": 0.95,
                "action": "reduce_all",
                "volatility_mult": 0.5  # Reduce further in crash
            },
            "bear": {
                "position_size_pct": 0.03,
                "max_leverage": 0.5,
                "cash_reserve": 0.70,
                "action": "reduce_most",
                "volatility_mult": 0.8
            },
            "neutral": {
                "position_size_pct": 0.05,
                "max_leverage": 1.0,
                "cash_reserve": 0.20,
                "action": "hold",
                "volatility_mult": 1.0
            },
            "bull": {
                "position_size_pct": 0.08,
                "max_leverage": 1.5,
                "cash_reserve": 0.15,
                "action": "increase_exposure",
                "volatility_mult": 1.1  # Increase in stable uptrend
            },
            "euphoria": {
                "position_size_pct": 0.05,
                "max_leverage": 1.0,
                "cash_reserve": 0.30,
                "action": "reduce_risk",
                "volatility_mult": 0.7  # Reduce in unsustainable rally
            }
        }

        # Risk tolerance multipliers
        self.risk_multipliers = {
            "conservative": 0.6,   # 40% less aggressive
            "moderate": 1.0,       # Baseline
            "aggressive": 1.4      # 40% more aggressive
        }

    def calculate_volatility_adjustment(self, bars, window=20):
        """Calculate volatility as a proportion of recent price action.

        High volatility = reduce position sizes
        Low volatility = maintain/increase position sizes
        Returns multiplier 0.5-1.5
        """
        if len(bars) < window:
            return 1.0

        recent_closes = np.array([b['c'] for b in bars[-window:]])
        returns = np.diff(recent_closes) / recent_closes[:-1]
        volatility = np.std(returns)

        # Map volatility to multiplier: high vol = lower multiplier
        # ~1% daily vol = normal (1.0x), >2% = reduced (0.6x), <0.5% = increased (1.2x)
        if volatility > 0.02:
            return 0.6
        elif volatility > 0.015:
            return 0.8
        elif volatility < 0.005:
            return 1.2
        else:
            return 1.0

    def calculate_trend_strength(self, bars, window=20):
        """Measure trend strength via slope of moving average.

        Strong trend (confidence) = increase exposure
        Weak trend (uncertainty) = reduce exposure
        Returns multiplier 0.7-1.3
        """
        if len(bars) < window * 2:
            return 1.0

        recent_closes = np.array([b['c'] for b in bars[-window:]])
        ma = np.mean(recent_closes)
        current_price = recent_closes[-1]

        # Distance from MA as % of price
        distance_pct = (current_price - ma) / ma

        if abs(distance_pct) > 0.03:  # >3% from MA = strong trend
            return 1.2 if distance_pct > 0 else 0.8
        elif abs(distance_pct) > 0.01:  # 1-3% = moderate trend
            return 1.1 if distance_pct > 0 else 0.9
        else:  # <1% from MA = weak/uncertain
            return 0.85

    def calculate_allocation(self, regime, account_value, current_positions=None, bars=None, uncertain=False, macro_multiplier=1.0, sector_weights=None, technical_signal=None):
        """Calculate ideal portfolio allocation for regime + volatility + macro + sector + technical.

        Args:
            regime: Current market regime
            account_value: Current portfolio value
            current_positions: List of open positions
            bars: Historical bars for volatility calculation
            uncertain: Flag if regime is flickering
            macro_multiplier: Macro leverage adjustment (0.5-1.5)
            sector_weights: Dict of sector weights
            technical_signal: Technical trade signal (buy/sell/hold)

        Returns dict with dynamic allocation adjusted for:
        - Market volatility
        - Trend strength
        - Risk tolerance
        - Regime uncertainty
        - Macro conditions (VIX, yield curve, rates)
        - Sector performance overlay
        - Technical confirmation
        """
        if current_positions is None:
            current_positions = []
        if sector_weights is None:
            sector_weights = {}

        allocation = self.regime_allocations.get(regime, self.regime_allocations["neutral"])

        # Calculate adjustments
        volatility_adj = self.calculate_volatility_adjustment(bars) if bars else 1.0
        trend_adj = self.calculate_trend_strength(bars) if bars else 1.0
        risk_adj = self.risk_multipliers.get(self.risk_tolerance, 1.0)
        uncertainty_adj = 0.7 if uncertain else 1.0  # Reduce if regime uncertain
        macro_adj = macro_multiplier  # Macro overlay (bearish macro reduces leverage)

        # Technical signal adjustment
        technical_adj = 1.0
        if technical_signal == "buy":
            technical_adj = 1.2
        elif technical_signal == "sell":
            technical_adj = 0.6
        # "hold" keeps technical_adj at 1.0

        # Combine all adjustments (macro is portfolio-wide, technical is more tactical)
        total_adjustment = volatility_adj * trend_adj * risk_adj * uncertainty_adj * macro_adj * technical_adj

        # Apply to base allocation
        position_size_pct = allocation["position_size_pct"] * total_adjustment
        leverage = allocation["max_leverage"] * total_adjustment

        max_position_size = account_value * position_size_pct
        target_cash = account_value * allocation["cash_reserve"]
        current_invested = sum(p.get("market_value", 0) for p in current_positions)
        investable_capital = account_value - target_cash

        return {
            "regime": regime,
            "account_value": account_value,
            "max_position_size": max_position_size,
            "target_cash": target_cash,
            "investable_capital": investable_capital,
            "leverage_multiplier": leverage,
            "current_invested": current_invested,
            "suggested_action": allocation["action"],
            "cash_buffer": account_value - current_invested,
            "adjustments": {
                "volatility": volatility_adj,
                "trend": trend_adj,
                "risk_tolerance": risk_adj,
                "uncertainty": uncertainty_adj,
                "macro": macro_adj,
                "technical": technical_adj,
                "total": total_adjustment
            },
            "sector_weights": sector_weights,
            "technical_signal": technical_signal
        }

    def should_reduce_positions(self, regime):
        """Check if current regime requires position reduction."""
        action = self.regime_allocations.get(regime, {}).get("action", "hold")
        return action in ["reduce_all", "reduce_most", "reduce_risk"]

    def position_sizing_for_regime(self, regime, account_value, num_positions, bars=None, uncertain=False):
        """Calculate position size given regime, volatility, and number of holdings."""
        allocation = self.regime_allocations.get(regime, self.regime_allocations["neutral"])
        volatility_adj = self.calculate_volatility_adjustment(bars) if bars else 1.0
        uncertainty_adj = 0.7 if uncertain else 1.0
        risk_adj = self.risk_multipliers.get(self.risk_tolerance, 1.0)

        per_position = (allocation["position_size_pct"] * volatility_adj * uncertainty_adj * risk_adj) / max(num_positions, 1)
        return account_value * per_position

if __name__ == "__main__":
    allocator = PortfolioAllocator()

    test_scenarios = [
        ("crash", 100000, []),
        ("bear", 100000, [{"symbol": "SPY", "qty": 50, "market_value": 26000}]),
        ("neutral", 100000, []),
        ("bull", 100000, []),
        ("euphoria", 100000, [{"symbol": "NVDA", "qty": 20, "market_value": 15000}])
    ]

    for regime, account_value, positions in test_scenarios:
        allocation = allocator.calculate_allocation(regime, account_value, positions)
        print(f"\n{regime.upper()}:")
        print(json.dumps(allocation, indent=2))
