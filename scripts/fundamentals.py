"""Fundamental analysis: stock screening and valuation metrics."""

import yfinance as yf
import json
from datetime import datetime

class FundamentalAnalyzer:
    """Screen stocks based on fundamental metrics."""

    def __init__(self, symbol):
        """
        Args:
            symbol: Stock ticker (e.g., 'AAPL')
        """
        self.symbol = symbol
        self.data = {}

    def get_stock_info(self):
        """Fetch stock fundamental data from Yahoo Finance."""
        try:
            ticker = yf.Ticker(self.symbol)
            info = ticker.info

            self.data = {
                'market_cap': info.get('marketCap'),
                'pe_ratio': info.get('trailingPE'),
                'forward_pe': info.get('forwardPE'),
                'eps': info.get('trailingEps'),
                'forward_eps': info.get('forwardEps'),
                'earnings_growth': info.get('earningsGrowth'),
                'revenue_growth': info.get('revenueGrowth'),
                'profit_margin': info.get('profitMargins'),
                'debt_to_equity': info.get('debtToEquity'),
                'current_ratio': info.get('currentRatio'),
                'roe': info.get('returnOnEquity'),
                'industry': info.get('industry'),
                'sector': info.get('sector'),
                'dividend_yield': info.get('dividendYield'),
                '52_week_high': info.get('fiftyTwoWeekHigh'),
                '52_week_low': info.get('fiftyTwoWeekLow'),
                'price': info.get('currentPrice')
            }
            return self.data
        except Exception as e:
            print(f"[FUNDAMENTAL] Error fetching {self.symbol}: {e}")
            return None

    def calculate_valuation_score(self):
        """Score stock valuation (0-100, higher = better/cheaper)."""
        if not self.data or self.data.get('pe_ratio') is None:
            return 50  # Neutral if no data

        pe = self.data['pe_ratio']
        industry_avg_pe = 20  # Market average

        if pe > 0 and pe < industry_avg_pe:
            score = 75  # Undervalued
        elif pe >= industry_avg_pe and pe < industry_avg_pe * 1.5:
            score = 50  # Fair value
        else:
            score = 25  # Overvalued

        return score

    def calculate_growth_score(self):
        """Score growth metrics (0-100, higher = better)."""
        score = 50  # Default

        if self.data.get('earnings_growth') and self.data['earnings_growth'] > 0.15:
            score += 25
        elif self.data.get('earnings_growth') and self.data['earnings_growth'] < -0.05:
            score -= 15

        if self.data.get('revenue_growth') and self.data['revenue_growth'] > 0.10:
            score += 15

        return min(100, max(0, score))

    def calculate_health_score(self):
        """Score financial health (0-100, higher = better)."""
        score = 50

        # Profit margin
        if self.data.get('profit_margin'):
            if self.data['profit_margin'] > 0.20:
                score += 15
            elif self.data['profit_margin'] < 0:
                score -= 20

        # Debt to equity
        if self.data.get('debt_to_equity'):
            dte = self.data['debt_to_equity']
            if dte < 1.0:
                score += 15
            elif dte > 2.0:
                score -= 15

        # Current ratio (liquidity)
        if self.data.get('current_ratio'):
            if self.data['current_ratio'] > 1.5:
                score += 10
            elif self.data['current_ratio'] < 1.0:
                score -= 10

        # ROE
        if self.data.get('roe'):
            if self.data['roe'] > 0.15:
                score += 10

        return min(100, max(0, score))

    def calculate_overall_score(self):
        """Combined fundamental score."""
        valuation = self.calculate_valuation_score()
        growth = self.calculate_growth_score()
        health = self.calculate_health_score()

        overall = (valuation * 0.3) + (growth * 0.4) + (health * 0.3)
        return overall

    def should_add_to_watchlist(self, threshold=60):
        """Determine if stock meets fundamental criteria."""
        score = self.calculate_overall_score()
        return score > threshold

    def analyze(self):
        """Run complete fundamental analysis."""
        self.get_stock_info()

        if not self.data:
            return None

        return {
            'symbol': self.symbol,
            'sector': self.data.get('sector'),
            'industry': self.data.get('industry'),
            'price': self.data.get('price'),
            'pe_ratio': self.data.get('pe_ratio'),
            'forward_pe': self.data.get('forward_pe'),
            'eps': self.data.get('eps'),
            'forward_eps': self.data.get('forward_eps'),
            'earnings_growth': self.data.get('earnings_growth'),
            'revenue_growth': self.data.get('revenue_growth'),
            'profit_margin': self.data.get('profit_margin'),
            'debt_to_equity': self.data.get('debt_to_equity'),
            'current_ratio': self.data.get('current_ratio'),
            'roe': self.data.get('roe'),
            'dividend_yield': self.data.get('dividend_yield'),
            '52_week_high': self.data.get('52_week_high'),
            '52_week_low': self.data.get('52_week_low'),
            'valuation_score': self.calculate_valuation_score(),
            'growth_score': self.calculate_growth_score(),
            'health_score': self.calculate_health_score(),
            'overall_score': self.calculate_overall_score(),
            'qualifies': self.should_add_to_watchlist(),
            'timestamp': datetime.now().isoformat()
        }


class SectorAnalyzer:
    """Analyze sector performance for top-down allocation."""

    SECTOR_ETFS = {
        'XLK': 'Information Technology',
        'XLV': 'Healthcare',
        'XLE': 'Energy',
        'XLI': 'Industrials',
        'XLY': 'Consumer Discretionary',
        'XLP': 'Consumer Staples',
        'XLRE': 'Real Estate',
        'XLF': 'Financials',
        'XLU': 'Utilities',
        'XLRE': 'Real Estate',
        'XLB': 'Materials'
    }

    def __init__(self):
        self.sector_performance = {}

    def get_sector_returns(self, lookback_days=252):
        """Calculate returns for each sector ETF over lookback period."""
        for etf, sector_name in self.SECTOR_ETFS.items():
            try:
                ticker = yf.Ticker(etf)
                hist = ticker.history(period=f"{lookback_days}d")

                if len(hist) > 0:
                    start_price = hist['Close'].iloc[0]
                    end_price = hist['Close'].iloc[-1]
                    total_return = (end_price - start_price) / start_price

                    self.sector_performance[sector_name] = {
                        'etf': etf,
                        'return': total_return,
                        'current_price': end_price
                    }
            except Exception as e:
                print(f"[SECTOR] Error fetching {etf}: {e}")

        return self.sector_performance

    def rank_sectors(self):
        """Rank sectors by performance."""
        sorted_sectors = sorted(
            self.sector_performance.items(),
            key=lambda x: x[1]['return'],
            reverse=True
        )
        return sorted_sectors

    def get_sector_weights(self):
        """
        Calculate portfolio weight adjustments based on sector performance.
        Top sectors get higher allocation, bottom sectors get reduced.
        """
        ranked = self.rank_sectors()

        if not ranked:
            return {}

        weights = {}
        for idx, (sector, data) in enumerate(ranked):
            # Simplistic weighting: top 3 = 1.2x, middle = 1.0x, bottom 3 = 0.8x
            if idx < 3:
                weights[sector] = 1.2
            elif idx < 5:
                weights[sector] = 1.0
            else:
                weights[sector] = 0.8

        return weights

    def analyze(self):
        """Run complete sector analysis."""
        self.get_sector_returns()
        ranked = self.rank_sectors()
        weights = self.get_sector_weights()

        return {
            'sector_performance': self.sector_performance,
            'ranked_sectors': [
                {'rank': i+1, 'sector': s, 'return': d['return']}
                for i, (s, d) in enumerate(ranked)
            ],
            'sector_weights': weights,
            'timestamp': datetime.now().isoformat()
        }


if __name__ == "__main__":
    # Test fundamental analysis
    fa = FundamentalAnalyzer("AAPL")
    print("FUNDAMENTAL ANALYSIS:")
    print(json.dumps(fa.analyze(), indent=2, default=str))

    # Test sector analysis
    print("\nSECTOR ANALYSIS:")
    sa = SectorAnalyzer()
    print(json.dumps(sa.analyze(), indent=2, default=str))
