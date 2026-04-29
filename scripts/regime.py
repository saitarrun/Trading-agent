import numpy as np
from hmmlearn import hmm
import json
from datetime import datetime
from collections import deque
import os
from dotenv import load_dotenv

load_dotenv()

class MarketRegimeDetector:
    """Hidden Markov Model for market regime detection with stability filtering.

    Features:
    - Automatic regime selection (3-7 optimal states)
    - Forward algorithm only (no look-ahead bias)
    - Stability filter (3-bar persistence requirement)
    - Uncertainty detection (>4 regime changes in 20 bars)
    - Trained on 2+ years of data
    """

    REGIME_LABELS = ["crash", "bear", "neutral", "bull", "euphoria"]

    def __init__(self, n_states=None, stability_bars=3, max_regime_changes=4):
        self.n_states = n_states  # Auto-detect if None
        self.model = None
        self.scaler_mean = None
        self.scaler_std = None
        self.fitted = False
        self.stability_bars = stability_bars  # Require regime to persist N bars
        self.max_regime_changes = max_regime_changes  # Flag uncertainty if >N changes in 20 bars
        self.regime_history = deque(maxlen=20)  # Track last 20 regime predictions

    def _prepare_features(self, returns, volatility):
        """Normalize returns and volatility."""
        features = np.column_stack([returns, volatility])

        if self.scaler_mean is None:
            self.scaler_mean = features.mean(axis=0)
            self.scaler_std = features.std(axis=0) + 1e-6

        normalized = (features - self.scaler_mean) / self.scaler_std
        return normalized

    def _select_optimal_states(self, X, min_states=3, max_states=7):
        """Auto-detect optimal number of regimes using BIC.

        Tests 3-7 states and selects best fit.
        Returns optimal n_states.
        """
        best_score = -np.inf
        best_n = min_states

        for n in range(min_states, max_states + 1):
            try:
                model = hmm.GaussianHMM(n_components=n, covariance_type="full", n_iter=1000)
                model.fit(X)
                score = -model.bic(X)  # BIC is lower-is-better; negate for comparison

                if score > best_score:
                    best_score = score
                    best_n = n
            except:
                continue

        return best_n

    def fit(self, bars):
        """Fit HMM on historical bars (ideally 2+ years).

        Args:
            bars: List of dicts with 'c' (close) and 'h', 'l' (high, low)
        """
        # H7 FIX: Reset scaler for each fit to avoid state leakage across symbols
        self.scaler_mean = None
        self.scaler_std = None

        if len(bars) < 252:  # ~1 year of trading days
            print(f"Warning: Only {len(bars)} bars; recommend 252+ (1 year) or 504+ (2 years)")

        closes = np.array([b['c'] for b in bars])
        returns = np.diff(closes) / closes[:-1]

        highs = np.array([b['h'] for b in bars[1:]])
        lows = np.array([b['l'] for b in bars[1:]])
        volatility = (highs - lows) / closes[:-1]

        X = self._prepare_features(returns, volatility)

        # H6 FIX: Force n_states=5 to match REGIME_LABELS
        if self.n_states is None:
            self.n_states = 5
            print(f"Using fixed 5 regimes (crash, bear, neutral, bull, euphoria)")

        self.model = hmm.GaussianHMM(
            n_components=self.n_states,
            covariance_type="full",
            n_iter=1000
        )
        self.model.fit(X)
        self.fitted = True

    def _apply_stability_filter(self, raw_regime):
        """Apply 3-bar persistence filter.

        Regime only changes if new regime persists for stability_bars.
        Returns filtered regime.
        """
        self.regime_history.append(raw_regime)

        if len(self.regime_history) < self.stability_bars:
            return raw_regime

        # Check if last N bars are the same
        last_n = list(self.regime_history)[-self.stability_bars:]
        if len(set(last_n)) == 1:
            return raw_regime  # All match, return new regime

        # Not stable yet, return previous stable regime
        return self.regime_history[-self.stability_bars - 1] if len(self.regime_history) > self.stability_bars else self.regime_history[0]

    def _check_uncertainty(self):
        """Detect regime flickering.

        Returns True if >max_regime_changes in last 20 bars (uncertainty).
        """
        if len(self.regime_history) < 20:
            return False

        history = list(self.regime_history)
        changes = sum(1 for i in range(1, len(history)) if history[i] != history[i-1])

        return changes > self.max_regime_changes

    def predict_regime(self, bars):
        """Predict current regime with stability filter (forward algorithm only).

        Returns (regime, confidence, uncertainty_flag)
        """
        if not self.fitted or len(bars) < 2:
            return "neutral", 0.0, False

        closes = np.array([b['c'] for b in bars])
        returns = np.diff(closes) / closes[:-1]

        highs = np.array([b['h'] for b in bars[1:]])
        lows = np.array([b['l'] for b in bars[1:]])
        volatility = (highs - lows) / closes[:-1]

        X = self._prepare_features(returns, volatility)

        # Use forward algorithm (score_samples) to avoid look-ahead bias
        logprob, posteriors = self.model.score_samples(X)
        raw_state = posteriors[-1].argmax()
        raw_confidence = posteriors[-1][raw_state]

        # Map state to regime label
        raw_regime = self.REGIME_LABELS[raw_state % len(self.REGIME_LABELS)]

        # Apply stability filter
        stable_regime = self._apply_stability_filter(raw_regime)

        # Check for uncertainty
        uncertain = self._check_uncertainty()

        return stable_regime, float(raw_confidence), uncertain

    def get_regime_characteristics(self, regime, uncertain=False):
        """Get expected volatility and direction for regime."""
        characteristics = {
            "crash": {"volatility": "high", "direction": "down", "leverage": 0.0},
            "bear": {"volatility": "medium", "direction": "down", "leverage": 0.5},
            "neutral": {"volatility": "low", "direction": "flat", "leverage": 1.0},
            "bull": {"volatility": "medium", "direction": "up", "leverage": 1.5},
            "euphoria": {"volatility": "high", "direction": "up", "leverage": 1.0},
        }

        char = characteristics.get(regime, characteristics["neutral"])

        # Reduce leverage if uncertain
        if uncertain:
            char["leverage"] *= 0.5
            char["note"] = "Regime uncertain - position size reduced"

        return char

if __name__ == "__main__":
    from research import get_bars

    detector = MarketRegimeDetector(n_states=5)

    bars = get_bars("SPY", "1Day", limit=100)
    if "bars" in bars:
        bar_data = [{"c": b["c"], "h": b["h"], "l": b["l"]} for b in bars["bars"].values()]
        detector.fit(bar_data)
        regime, confidence = detector.predict_regime(bar_data)
        characteristics = detector.get_regime_characteristics(regime)

        print(json.dumps({
            "regime": regime,
            "confidence": float(confidence),
            "characteristics": characteristics
        }, indent=2))
