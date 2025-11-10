"""
Dividend Stock Analyzer - Web Version
A web-based dividend-focused value investing tool using quality screening and yield analysis
"""

import streamlit as st
import yfinance as yf
import requests
import time
import json
import os
from dataclasses import dataclass
from typing import List, Tuple
from datetime import datetime

# Page configuration
st.set_page_config(
    page_title="Dividend Stock Analyzer",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ============================================================================
# REGIONAL CRITERIA & CONFIGURATION
# ============================================================================

REGIONAL_CRITERIA = {
    "USD": {
        "dividend_increases_min": 5,
        "shares_outstanding_min": 5.0,
        "institutional_holders_min": 5,  # Yahoo Finance only returns top 10 holders
        "eps_increases_min": 4,  # Realistic - even great companies have down years
        "consecutive_dividend_min": 10,
        "required_status": [],
        "description": "Practical criteria for US dividend stocks"
    },
    "GBP": {
        "dividend_increases_min": 5,
        "shares_outstanding_min": 50.0,
        "institutional_holders_min": 5,  # Yahoo Finance only returns top 10 holders
        "eps_increases_min": 4,  # Realistic - even great companies have down years
        "consecutive_dividend_min": 10,
        "required_status": [],
        "description": "Practical criteria for UK dividend stocks"
    },
    "CAD": {
        "dividend_increases_min": 5,
        "shares_outstanding_min": 10.0,
        "institutional_holders_min": 5,  # Yahoo Finance only returns top 10 holders
        "eps_increases_min": 4,  # Realistic - even great companies have down years
        "consecutive_dividend_min": 10,
        "required_status": [],
        "description": "Practical criteria for Canadian dividend stocks"
    }
}

def get_regional_criteria(currency: str, screening_mode: str = "Balanced") -> dict:
    """Get criteria thresholds based on currency and screening mode"""
    base_criteria = REGIONAL_CRITERIA.get(currency, REGIONAL_CRITERIA["USD"])

    if screening_mode == "Aggressive":
        return {
            "dividend_increases_min": max(base_criteria["dividend_increases_min"] - 2, 3),
            "shares_outstanding_min": base_criteria["shares_outstanding_min"] * 0.4,
            "institutional_holders_min": max(base_criteria["institutional_holders_min"] - 2, 3),
            "eps_increases_min": max(base_criteria["eps_increases_min"] - 2, 3),
            "consecutive_dividend_min": max(base_criteria["consecutive_dividend_min"] - 5, 5),
            "required_status": [],
            "description": f"{base_criteria['description']} (Aggressive)"
        }
    else:
        return base_criteria.copy()

@dataclass
class StockData:
    """Data structure for stock information"""
    ticker: str
    company_name: str
    current_price: float
    annual_dividend: float
    historical_high_yield: float
    historical_low_yield: float
    currency: str = "USD"
    dividend_increases_12y: int = 0
    shares_outstanding_millions: float = 0.0
    institutional_holders: int = 0
    eps_increases_12y: int = 0
    consecutive_dividend_years: int = 0
    dividend_aristocrat_status: str = "None"

# ============================================================================
# SEC EDGAR EPS FETCHING
# ============================================================================

def fetch_sec_edgar_eps_increases(ticker):
    """Fetch EPS increases from SEC EDGAR (FREE, UNLIMITED, US stocks only)"""
    try:
        COMMON_CIKS = {
            'AAPL': '0000320193', 'MSFT': '0000789019', 'GOOGL': '0001652044',
            'AMZN': '0001018724', 'NVDA': '0001045810', 'META': '0001326801',
            'TSLA': '0001318605', 'V': '0001403161', 'JNJ': '0000200406',
            'WMT': '0000104169', 'JPM': '0000019617', 'PG': '0000080424',
            'MA': '0001141391', 'HD': '0000354950', 'CVX': '0000093410',
            'LLY': '0000059478', 'ABBV': '0001551152', 'MRK': '0000310158',
            'KO': '0000021344', 'PEP': '0000077476', 'COST': '0000909832',
            'NKE': '0000320187', 'DIS': '0001744489', 'CSCO': '0000858877',
            'INTC': '0000050863', 'NFLX': '0001065280', 'BA': '0000012927',
            'T': '0000732717', 'VZ': '0000732712', 'PFE': '0000078003'
        }

        cik = COMMON_CIKS.get(ticker.upper())

        if not cik:
            return None

        headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
            'Accept': 'application/json',
            'Accept-Encoding': 'gzip, deflate'
        }

        time.sleep(0.5)

        facts_url = f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"
        response = requests.get(facts_url, headers=headers, timeout=15)

        if response.status_code != 200:
            return None

        data = response.json()

        if 'facts' not in data or 'us-gaap' not in data['facts']:
            return None

        eps_data = data['facts']['us-gaap'].get('EarningsPerShareDiluted', {}).get('units', {}).get('USD/shares', [])

        if not eps_data:
            return None

        annual_eps = {}
        for entry in eps_data:
            if entry.get('form') == '10-K' and 'fy' in entry:
                year = int(entry['fy'])
                val = entry.get('val', 0)
                if year not in annual_eps or abs(val) > abs(annual_eps[year]):
                    annual_eps[year] = val

        if len(annual_eps) < 2:
            return None

        years = sorted(annual_eps.keys(), reverse=True)[:12]
        increases = 0

        for i in range(len(years) - 1):
            current_year = years[i]
            previous_year = years[i + 1]

            if annual_eps[current_year] > annual_eps[previous_year]:
                increases += 1

        return increases

    except Exception as e:
        st.write(f"SEC EDGAR error: {str(e)}")
        return None

# ============================================================================
# STOCK DATA FETCHING
# ============================================================================

@st.cache_data(ttl=3600)
def fetch_stock_data(ticker):
    """Fetch stock data from Yahoo Finance"""
    try:
        stock = yf.Ticker(ticker)
        info = stock.info

        # Basic info
        current_price = info.get('currentPrice', info.get('regularMarketPrice', 0))
        annual_dividend = info.get('dividendRate', 0)
        shares_outstanding = info.get('sharesOutstanding', 0) / 1_000_000

        # Institutional holders
        institutional_holders = len(stock.institutional_holders) if hasattr(stock, 'institutional_holders') and stock.institutional_holders is not None else 0

        # Dividend history
        dividends = stock.dividends
        dividend_increases = calculate_dividend_increases(dividends)
        consecutive_years = calculate_consecutive_dividend_years(dividends)

        # Historical yields
        hist_high_yield, hist_low_yield = calculate_historical_yields(stock, current_price, annual_dividend)

        # EPS increases
        eps_increases = fetch_sec_edgar_eps_increases(ticker)
        if eps_increases is None:
            eps_increases = 0

        # Dividend status
        dividend_status = determine_dividend_status(consecutive_years)

        return {
            'ticker': ticker,
            'company_name': info.get('longName', ticker),
            'current_price': current_price,
            'annual_dividend': annual_dividend,
            'shares_outstanding': shares_outstanding,
            'institutional_holders': institutional_holders,
            'dividend_increases': dividend_increases,
            'consecutive_years': consecutive_years,
            'hist_high_yield': hist_high_yield,
            'hist_low_yield': hist_low_yield,
            'eps_increases': eps_increases,
            'dividend_status': dividend_status,
            'currency': info.get('currency', 'USD')
        }
    except Exception as e:
        st.error(f"Error fetching data for {ticker}: {str(e)}")
        return None

def calculate_dividend_increases(dividends):
    """Calculate number of dividend increases in last 12 years"""
    try:
        if len(dividends) == 0:
            return 0

        current_year = datetime.now().year
        years_to_check = list(range(current_year - 12, current_year))

        annual_dividends = {}
        for date, div in dividends.items():
            year = date.year
            if year in years_to_check:
                annual_dividends[year] = annual_dividends.get(year, 0) + div

        increases = 0
        sorted_years = sorted(annual_dividends.keys())

        for i in range(1, len(sorted_years)):
            if annual_dividends[sorted_years[i]] > annual_dividends[sorted_years[i-1]]:
                increases += 1

        return increases
    except:
        return 0

def calculate_consecutive_dividend_years(dividends):
    """Calculate consecutive years of dividend payments"""
    try:
        if len(dividends) == 0:
            return 0

        current_year = datetime.now().year
        annual_dividends = {}

        for date, div in dividends.items():
            year = date.year
            annual_dividends[year] = annual_dividends.get(year, 0) + div

        consecutive = 0
        year = current_year - 1

        while year in annual_dividends and annual_dividends[year] > 0:
            consecutive += 1
            year -= 1

        return consecutive
    except:
        return 0

def calculate_historical_yields(stock, current_price, annual_dividend):
    """Calculate historical high and low yields"""
    try:
        hist = stock.history(period="5y")
        if len(hist) == 0 or annual_dividend == 0:
            return 0.0, 0.0

        prices = hist['Close']
        yields = [(annual_dividend / price) * 100 for price in prices if price > 0]

        if len(yields) > 0:
            return max(yields), min(yields)
        return 0.0, 0.0
    except:
        return 0.0, 0.0

def determine_dividend_status(consecutive_years):
    """Determine dividend aristocrat status"""
    if consecutive_years >= 50:
        return "Dividend King"
    elif consecutive_years >= 25:
        return "Dividend Aristocrat"
    elif consecutive_years >= 10:
        return "Dividend Achiever"
    elif consecutive_years >= 5:
        return "Dividend Contender"
    else:
        return "None"

# ============================================================================
# ANALYSIS ENGINE
# ============================================================================

def analyze_stock(stock_data, screening_mode="Balanced"):
    """Analyze stock quality and valuation"""
    criteria = get_regional_criteria(stock_data['currency'], screening_mode)

    # Check quality criteria
    passed_criteria = []
    failed_criteria = []

    # 1. Dividend Increases
    if stock_data['dividend_increases'] >= criteria['dividend_increases_min']:
        passed_criteria.append("Dividend Increases")
    else:
        failed_criteria.append(f"Dividend Increases: {stock_data['dividend_increases']}/{criteria['dividend_increases_min']} required")

    # 2. Shares Outstanding
    if stock_data['shares_outstanding'] >= criteria['shares_outstanding_min']:
        passed_criteria.append("Shares Outstanding")
    else:
        failed_criteria.append(f"Shares Outstanding: {stock_data['shares_outstanding']:.1f}M/{criteria['shares_outstanding_min']}M required")

    # 3. Institutional Holders
    if stock_data['institutional_holders'] >= criteria['institutional_holders_min']:
        passed_criteria.append("Institutional Holders")
    else:
        failed_criteria.append(f"Institutional Holders: {stock_data['institutional_holders']}/{criteria['institutional_holders_min']} required")

    # 4. EPS Increases
    if stock_data['eps_increases'] >= criteria['eps_increases_min']:
        passed_criteria.append("EPS Increases")
    else:
        failed_criteria.append(f"EPS Increases: {stock_data['eps_increases']}/{criteria['eps_increases_min']} required")

    # 5. Consecutive Dividend Years
    if stock_data['consecutive_years'] >= criteria['consecutive_dividend_min']:
        passed_criteria.append("Consecutive Dividend Years")
    else:
        failed_criteria.append(f"Consecutive Dividend Years: {stock_data['consecutive_years']}/{criteria['consecutive_dividend_min']} required")

    # 6. Dividend Status (optional)
    passed_criteria.append("Dividend Status (Optional)")

    quality_ok = len(failed_criteria) == 0

    # Valuation analysis
    current_yield = (stock_data['annual_dividend'] / stock_data['current_price']) * 100 if stock_data['current_price'] > 0 else 0

    buy_yield = stock_data['hist_high_yield'] * 0.80
    watch_yield = stock_data['hist_high_yield'] * 0.70
    sell_yield = stock_data['hist_low_yield'] * 1.20

    if current_yield >= buy_yield:
        recommendation = "BUY"
        zone = "Buy Zone"
    elif current_yield >= watch_yield:
        recommendation = "WATCH"
        zone = "Watch Zone"
    elif current_yield <= sell_yield:
        recommendation = "SELL"
        zone = "Sell Zone"
    else:
        recommendation = "HOLD"
        zone = "Hold Zone"

    if not quality_ok:
        recommendation = "DOES NOT QUALIFY"
        zone = "Failed Quality"

    return {
        'quality_ok': quality_ok,
        'passed_criteria': passed_criteria,
        'failed_criteria': failed_criteria,
        'current_yield': current_yield,
        'buy_yield': buy_yield,
        'watch_yield': watch_yield,
        'sell_yield': sell_yield,
        'recommendation': recommendation,
        'zone': zone,
        'criteria': criteria
    }

# ============================================================================
# STREAMLIT UI
# ============================================================================

def main():
    # Header
    st.title("📊 Dividend Stock Analyzer")
    st.markdown("Quality dividend screening using the Weiss methodology")

    # Sidebar
    with st.sidebar:
        st.header("Settings")

        screening_mode = st.radio(
            "Screening Mode",
            ["Balanced", "Aggressive"],
            help="Balanced: Standard criteria | Aggressive: More lenient criteria"
        )

        st.markdown("---")
        st.markdown("### About")
        st.markdown("""
        This tool analyzes dividend stocks using six quality criteria:
        1. Dividend Increases (12y)
        2. Shares Outstanding
        3. Institutional Holders
        4. EPS Increases (12y)
        5. Consecutive Dividend Years
        6. Dividend Status
        """)

    # Main content
    col1, col2 = st.columns([1, 2])

    with col1:
        st.subheader("Stock Input")
        ticker = st.text_input(
            "Enter Ticker Symbol",
            placeholder="e.g., AAPL, JNJ, KO",
            help="Enter a stock ticker symbol"
        ).upper()

        analyze_button = st.button("🔍 Analyze Stock", type="primary", use_container_width=True)

    with col2:
        st.subheader("Analysis Results")

        if analyze_button and ticker:
            with st.spinner(f"Fetching data for {ticker}..."):
                stock_data = fetch_stock_data(ticker)

            if stock_data:
                # Display company info
                st.markdown(f"### {stock_data['company_name']} ({stock_data['ticker']})")

                metric_col1, metric_col2, metric_col3, metric_col4 = st.columns(4)

                with metric_col1:
                    st.metric("Current Price", f"${stock_data['current_price']:.2f}")

                with metric_col2:
                    st.metric("Annual Dividend", f"${stock_data['annual_dividend']:.2f}")

                with metric_col3:
                    current_yield = (stock_data['annual_dividend'] / stock_data['current_price']) * 100 if stock_data['current_price'] > 0 else 0
                    st.metric("Current Yield", f"{current_yield:.2f}%")

                with metric_col4:
                    st.metric("Consecutive Years", stock_data['consecutive_years'])

                # Analyze
                analysis = analyze_stock(stock_data, screening_mode)

                st.markdown("---")

                # Quality Criteria Results
                st.markdown("### Quality Criteria Assessment")

                if analysis['quality_ok']:
                    st.success("✅ **PASSED ALL QUALITY CRITERIA**")
                else:
                    st.error("❌ **FAILED QUALITY SCREENING**")

                # Show detailed criteria
                criteria_col1, criteria_col2 = st.columns(2)

                with criteria_col1:
                    st.markdown("**✓ Passed Criteria:**")
                    for criterion in analysis['passed_criteria']:
                        st.markdown(f"- {criterion}")

                with criteria_col2:
                    if analysis['failed_criteria']:
                        st.markdown("**✗ Failed Criteria:**")
                        for criterion in analysis['failed_criteria']:
                            st.markdown(f"- {criterion}")

                st.markdown("---")

                # Valuation Analysis
                if analysis['quality_ok']:
                    st.markdown("### Valuation Analysis")

                    val_col1, val_col2, val_col3 = st.columns(3)

                    with val_col1:
                        st.metric("Current Yield", f"{analysis['current_yield']:.2f}%")

                    with val_col2:
                        st.metric("Buy Yield Target", f"{analysis['buy_yield']:.2f}%")

                    with val_col3:
                        st.metric("Sell Yield Target", f"{analysis['sell_yield']:.2f}%")

                    # Recommendation
                    if analysis['recommendation'] == "BUY":
                        st.success(f"### 🟢 {analysis['recommendation']}")
                        st.markdown("**Action Items:**")
                        st.markdown("- ✓ Consider initiating or adding to position")
                        st.markdown("- ✓ Verify fundamentals haven't deteriorated")
                        st.markdown("- ✓ Check recent news and earnings")
                    elif analysis['recommendation'] == "SELL":
                        st.error(f"### 🔴 {analysis['recommendation']}")
                        st.markdown("**Action Items:**")
                        st.markdown("- • Consider taking profits if you own shares")
                        st.markdown("- • Stock is likely overvalued")
                    elif analysis['recommendation'] == "WATCH":
                        st.warning(f"### 🟡 {analysis['recommendation']}")
                        st.markdown("**Action Items:**")
                        st.markdown("- 👁 Add to watchlist")
                        st.markdown("- 👁 Monitor for further price decline")
                    else:
                        st.info(f"### 🔵 {analysis['recommendation']}")
                        st.markdown("**Action Items:**")
                        st.markdown("- • Hold current position if you own shares")
                        st.markdown("- • Not an optimal entry or exit point")

                # Disclaimer
                st.markdown("---")
                st.warning("""
                ⚠️ **INVESTMENT DISCLAIMER**

                This analysis is for informational purposes only and does not constitute investment advice.
                You are solely responsible for your investment decisions. Past performance does not guarantee
                future results. Always conduct your own due diligence and consult with a licensed financial
                advisor before investing.
                """)

        elif not ticker and analyze_button:
            st.warning("Please enter a ticker symbol")

if __name__ == "__main__":
    main()
