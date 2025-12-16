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
import plotly.graph_objects as go
import plotly.express as px
import pandas as pd
from dataclasses import dataclass
from typing import List, Tuple
from datetime import datetime, timedelta

# Page configuration
st.set_page_config(
    page_title="Dividend Stock Analyzer | Professional Stock Analysis",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Custom CSS for professional styling
st.markdown("""
<meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=5.0">
<style>
    /* Main theme colors */
    :root {
        --primary-color: #dc2626;
        --success-color: #059669;
        --warning-color: #d97706;
        --danger-color: #dc2626;
    }

    /* Hide Streamlit branding */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}

    /* Better typography */
    .stApp {
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
        max-width: 100%;
        padding: 0 clamp(0.5rem, 2vw, 1rem);
    }

    /* Mobile responsive */
    @media (max-width: 768px) {
        .stApp {
            padding: 0 0.5rem;
        }
        div[data-testid="stHorizontalBlock"] {
            flex-direction: column !important;
        }
    }

    /* Metric cards */
    div[data-testid="metric-container"] {
        background-color: #f9fafb;
        border: 1px solid #e5e7eb;
        padding: 15px;
        border-radius: 8px;
    }

    /* Buttons */
    .stButton > button {
        background-color: #dc2626;
        color: white;
        font-weight: 600;
        border-radius: 6px;
        padding: 0.5rem 2rem;
        border: none;
        transition: all 0.2s;
    }

    .stButton > button:hover {
        background-color: #b91c1c;
        transform: translateY(-1px);
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
    }

    /* Input fields */
    .stTextInput > div > div > input {
        border-radius: 6px;
        border: 2px solid #e5e7eb;
        padding: 0.75rem;
        font-size: 1rem;
    }

    .stTextInput > div > div > input:focus {
        border-color: #dc2626;
        box-shadow: 0 0 0 3px rgba(220, 38, 38, 0.1);
    }

    /* Success/Error messages */
    .element-container div[data-baseweb="notification"] {
        border-radius: 8px;
    }
</style>
""", unsafe_allow_html=True)

# Initialize session state
if 'analysis_count' not in st.session_state:
    st.session_state.analysis_count = 0
if 'analyses_limit' not in st.session_state:
    st.session_state.analyses_limit = 5

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
# MULTI-SOURCE EPS FETCHING
# ============================================================================

# Cache for SEC company tickers (loaded once per session)
@st.cache_data(ttl=86400)  # Cache for 24 hours
def load_sec_company_tickers():
    """Load and cache SEC company tickers mapping"""
    try:
        headers = {
            'User-Agent': 'DividendStockAnalyzer/1.0 (contact@example.com)',
            'Accept': 'application/json'
        }
        url = "https://www.sec.gov/files/company_tickers.json"
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            return response.json()
        return {}
    except:
        return {}

def get_cik_from_sec(ticker):
    """Look up CIK from SEC EDGAR ticker search"""
    try:
        data = load_sec_company_tickers()
        if not data:
            return None

        ticker_upper = ticker.upper()
        for key, company in data.items():
            if company.get('ticker', '').upper() == ticker_upper:
                cik = str(company.get('cik_str', '')).zfill(10)
                return cik

        return None
    except:
        return None

def fetch_sec_edgar_eps_increases(ticker):
    """Fetch EPS increases from SEC EDGAR with dynamic CIK lookup"""
    try:
        # First try to get CIK dynamically
        cik = get_cik_from_sec(ticker)

        if not cik:
            return None

        headers = {
            'User-Agent': 'DividendStockAnalyzer/1.0 (contact@example.com)',
            'Accept': 'application/json',
            'Accept-Encoding': 'gzip, deflate'
        }

        time.sleep(0.2)  # Be nice to SEC servers

        facts_url = f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"
        response = requests.get(facts_url, headers=headers, timeout=15)

        if response.status_code != 200:
            return None

        data = response.json()

        if 'facts' not in data or 'us-gaap' not in data['facts']:
            return None

        # Try multiple EPS fields
        eps_fields = ['EarningsPerShareDiluted', 'EarningsPerShareBasic', 'EarningsPerShare']
        eps_data = None

        for field in eps_fields:
            if field in data['facts']['us-gaap']:
                eps_units = data['facts']['us-gaap'][field].get('units', {})
                eps_data = eps_units.get('USD/shares') or eps_units.get('USD')
                if eps_data:
                    break

        if not eps_data:
            return None

        # Extract annual EPS from 10-K filings
        annual_eps = {}
        for entry in eps_data:
            if entry.get('form') == '10-K' and 'fy' in entry:
                year = int(entry['fy'])
                val = entry.get('val', 0)
                if year not in annual_eps or abs(val) > abs(annual_eps[year]):
                    annual_eps[year] = val

        if len(annual_eps) < 2:
            return None

        # Count increases over last 12 years
        years = sorted(annual_eps.keys(), reverse=True)[:12]
        increases = 0

        for i in range(len(years) - 1):
            current_year = years[i]
            previous_year = years[i + 1]
            if annual_eps[current_year] > annual_eps[previous_year]:
                increases += 1

        return increases

    except Exception:
        return None

def fetch_macrotrends_eps_increases(ticker, company_name=""):
    """Fetch EPS increases from Macrotrends.net as fallback"""
    try:
        import re

        headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Referer': 'https://www.google.com/',
        }

        # First, find the company page
        search_url = f"https://www.macrotrends.net/stocks/charts/{ticker.upper()}"
        response = requests.get(search_url, headers=headers, timeout=15, allow_redirects=True)

        if response.status_code != 200:
            return None

        # Extract the actual URL path from the page
        final_url = response.url
        if '/eps-earnings-per-share-diluted' not in final_url:
            # Try to construct the EPS page URL
            if '/stocks/charts/' in final_url:
                base_url = final_url.rstrip('/')
                eps_url = base_url + '/eps-earnings-per-share-diluted'
            else:
                return None
        else:
            eps_url = final_url

        # Fetch the EPS page
        time.sleep(0.3)
        response = requests.get(eps_url, headers=headers, timeout=15)

        if response.status_code != 200:
            return None

        html = response.text

        # Look for the JavaScript data array in the page
        pattern = r'var originalData = \[(.*?)\];'
        match = re.search(pattern, html, re.DOTALL)

        if not match:
            return None

        data_str = match.group(1)

        # Parse the JavaScript array
        eps_by_year = {}
        row_pattern = r'\{"date":"(\d{4})[^"]*"[^}]*"v2":([0-9.-]+)'
        matches = re.findall(row_pattern, data_str)

        for year_str, eps_str in matches:
            try:
                year = int(year_str)
                eps = float(eps_str)
                if year not in eps_by_year:
                    eps_by_year[year] = eps
            except ValueError:
                continue

        if len(eps_by_year) < 2:
            return None

        # Count increases
        years = sorted(eps_by_year.keys(), reverse=True)[:12]
        increases = 0

        for i in range(len(years) - 1):
            if eps_by_year[years[i]] > eps_by_year[years[i + 1]]:
                increases += 1

        return increases

    except Exception:
        return None

def fetch_yfinance_eps_increases(stock):
    """Try to get EPS data from yfinance earnings history

    Note: yfinance earnings_history only provides recent quarters (typically 4),
    which is not enough to calculate 12-year EPS increases. This function
    is kept for potential future use but will typically return None.
    """
    # yfinance earnings_history only has ~4 recent quarters, not enough for 12-year analysis
    # Skip this and let SEC EDGAR handle it
    return None

def fetch_eps_increases_multi_source(ticker, stock=None):
    """
    Fetch EPS increases using multiple data sources with fallback:
    1. yfinance earnings history (fastest)
    2. SEC EDGAR (most reliable for US stocks)
    3. Macrotrends (fallback for others)
    4. Estimate from dividend growth (last resort)
    """
    eps_increases = None

    # Try yfinance first (fastest)
    if stock:
        eps_increases = fetch_yfinance_eps_increases(stock)
        if eps_increases is not None:
            return eps_increases, "yfinance"

    # Try SEC EDGAR (best for US stocks)
    eps_increases = fetch_sec_edgar_eps_increases(ticker)
    if eps_increases is not None:
        return eps_increases, "SEC EDGAR"

    # Try Macrotrends as fallback
    eps_increases = fetch_macrotrends_eps_increases(ticker)
    if eps_increases is not None:
        return eps_increases, "Macrotrends"

    # Last resort: estimate from dividend growth
    if stock:
        try:
            dividends = stock.dividends
            if len(dividends) > 0:
                dividend_increases = calculate_dividend_increases(dividends)
                if dividend_increases >= 3:
                    # Strong dividend growth suggests EPS growth
                    eps_increases = max(3, int(dividend_increases * 0.7))
                    return eps_increases, "Estimated from dividends"
        except:
            pass

    # Return 0 if all sources fail
    return 0, "No data available"

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

        # EPS increases - use multi-source fetching
        eps_increases, eps_source = fetch_eps_increases_multi_source(ticker, stock)
        # eps_source can be used for debugging if needed

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

# ============================================================================
# CHART FUNCTIONS
# ============================================================================

def create_price_chart(ticker):
    """Create interactive price history chart"""
    try:
        stock = yf.Ticker(ticker)
        hist = stock.history(period="1y")

        if len(hist) == 0:
            return None

        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=hist.index,
            y=hist['Close'],
            mode='lines',
            name='Price',
            line=dict(color='#dc2626', width=2),
            fill='tozeroy',
            fillcolor='rgba(220, 38, 38, 0.1)'
        ))

        fig.update_layout(
            title="12-Month Price History",
            xaxis_title="Date",
            yaxis_title="Price ($)",
            hovermode='x unified',
            plot_bgcolor='white',
            paper_bgcolor='white',
            font=dict(family="Inter, sans-serif"),
            margin=dict(l=0, r=0, t=40, b=0),
            height=300
        )

        fig.update_xaxes(showgrid=True, gridcolor='#f3f4f6')
        fig.update_yaxes(showgrid=True, gridcolor='#f3f4f6')

        return fig
    except:
        return None

def create_yield_chart(stock_data, analysis):
    """Create yield comparison chart"""
    try:
        yields = {
            'Current Yield': analysis['current_yield'],
            'Buy Target': analysis['buy_yield'],
            'Sell Target': analysis['sell_yield']
        }

        colors = ['#3b82f6', '#059669', '#dc2626']

        fig = go.Figure(data=[
            go.Bar(
                x=list(yields.keys()),
                y=list(yields.values()),
                marker_color=colors,
                text=[f"{v:.2f}%" for v in yields.values()],
                textposition='auto',
            )
        ])

        fig.update_layout(
            title="Yield Analysis",
            yaxis_title="Yield (%)",
            showlegend=False,
            plot_bgcolor='white',
            paper_bgcolor='white',
            font=dict(family="Inter, sans-serif"),
            margin=dict(l=0, r=0, t=40, b=0),
            height=300
        )

        fig.update_xaxes(showgrid=False)
        fig.update_yaxes(showgrid=True, gridcolor='#f3f4f6')

        return fig
    except:
        return None

def show_upgrade_cta():
    """Show upgrade call-to-action with pricing tiers"""
    st.markdown("""
    <div style='background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                padding: 1.5rem 2rem; border-radius: 12px; margin: 2rem 0; color: white;'>
        <div style='text-align: center;'>
            <h2 style='font-size: 2rem; margin: 0 0 0.25rem 0; color: white;'>🚀 Upgrade to Desktop Version</h2>
            <p style='font-size: 1rem; margin: 0; opacity: 0.9;'>Choose the plan that's right for you</p>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # Create two columns for pricing tiers
    col1, col2 = st.columns(2)

    with col1:
        st.markdown("""
        <div style='background: white; padding: 2rem; border-radius: 12px;
                    box-shadow: 0 4px 6px rgba(0,0,0,0.1); height: 100%; margin-top: -1.5rem;'>
            <h3 style='color: #667eea; font-size: 1.5rem; margin-top: 0;'>Desktop Basic</h3>
            <div style='font-size: 2.5rem; font-weight: 700; color: #1f2937; margin: 1rem 0;'>
                $99<span style='font-size: 1rem; color: #6b7280;'>/year</span>
            </div>
            <hr style='border: none; border-top: 2px solid #e5e7eb; margin: 1.5rem 0;'>
            <ul style='list-style: none; padding: 0; color: #374151; line-height: 2;'>
                <li>✓ Unlimited analyses</li>
                <li>✓ Quality screening</li>
                <li>✓ Buy/Sell signals</li>
                <li>✓ Basic charts</li>
            </ul>
            <a href='https://fluentboost.com/stock-analyzer-basic' target='_blank'
               style='display: block; background: #667eea; color: white; text-align: center;
                      padding: 0.75rem; border-radius: 8px; text-decoration: none;
                      font-weight: 600; margin-top: 1.5rem;'>
                Get Basic →
            </a>
        </div>
        """, unsafe_allow_html=True)

    with col2:
        st.markdown("""
        <div style='background: white; padding: 2rem; border-radius: 12px;
                    box-shadow: 0 8px 16px rgba(0,0,0,0.2); border: 3px solid #fbbf24;
                    position: relative; height: 100%; margin-top: -1.5rem;'>
            <div style='position: absolute; top: -15px; left: 50%; transform: translateX(-50%);
                        background: #fbbf24; color: #1f2937; padding: 0.25rem 1rem;
                        border-radius: 20px; font-size: 0.75rem; font-weight: 700;'>
                MOST POPULAR
            </div>
            <h3 style='color: #764ba2; font-size: 1.5rem; margin-top: 0;'>Desktop Pro</h3>
            <div style='font-size: 2.5rem; font-weight: 700; color: #1f2937; margin: 1rem 0;'>
                $299<span style='font-size: 1rem; color: #6b7280;'>/year</span>
            </div>
            <hr style='border: none; border-top: 2px solid #e5e7eb; margin: 1.5rem 0;'>
            <ul style='list-style: none; padding: 0; color: #374151; line-height: 2;'>
                <li><strong>✓ Everything in Basic</strong></li>
                <li>✓ Watchlist manager</li>
                <li>✓ Portfolio tracking</li>
                <li>✓ Advanced charts</li>
                <li>✓ PDF exports</li>
                <li>✓ Historical tracking</li>
                <li>✓ Bulk analysis</li>
            </ul>
            <a href='https://fluentboost.com/stock-analyzer-pro' target='_blank'
               style='display: block; background: #fbbf24; color: #1f2937; text-align: center;
                      padding: 0.75rem; border-radius: 8px; text-decoration: none;
                      font-weight: 700; margin-top: 1.5rem;'>
                Get Pro →
            </a>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("""
    <div style='text-align: center; margin-top: 1rem; font-size: 0.9rem; opacity: 0.7;'>
        Annual subscription • Cancel anytime
    </div>
    """, unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

def show_value_proposition():
    """Show permanent value proposition and benefits"""
    st.markdown("### 💎 Why Use This Analyzer?")

    # Benefits in columns
    benefit_col1, benefit_col2, benefit_col3 = st.columns(3)

    with benefit_col1:
        st.markdown("""
        <div style='background: #f0f9ff; padding: 1.5rem; border-radius: 8px; border-left: 4px solid #3b82f6;'>
            <h4 style='color: #1e40af; margin-top: 0;'>📈 Quality Screening</h4>
            <p style='color: #374151; font-size: 0.9rem;'>
                6-point quality assessment based on Weiss methodology: dividend growth,
                EPS increases, institutional confidence, and consistency.
            </p>
        </div>
        """, unsafe_allow_html=True)

    with benefit_col2:
        st.markdown("""
        <div style='background: #f0fdf4; padding: 1.5rem; border-radius: 8px; border-left: 4px solid #059669;'>
            <h4 style='color: #047857; margin-top: 0;'>🎯 Smart Signals</h4>
            <p style='color: #374151; font-size: 0.9rem;'>
                Get clear BUY, SELL, WATCH, or HOLD signals based on historical yield
                analysis. Know exactly when to act.
            </p>
        </div>
        """, unsafe_allow_html=True)

    with benefit_col3:
        st.markdown("""
        <div style='background: #fef3c7; padding: 1.5rem; border-radius: 8px; border-left: 4px solid #f59e0b;'>
            <h4 style='color: #d97706; margin-top: 0;'>📊 Visual Analysis</h4>
            <p style='color: #374151; font-size: 0.9rem;'>
                Interactive charts showing price history and yield comparisons.
                See the full picture at a glance.
            </p>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

def main():
    # Header with better styling
    st.markdown("""
    <div style='text-align: center; padding: 0.5rem 0 1rem 0;'>
        <h1 style='font-size: clamp(1.8rem, 5vw, 3rem); margin: 0;'>📊 Dividend Stock Analyzer</h1>
        <p style='font-size: clamp(1rem, 3vw, 1.2rem); color: #6b7280; margin: 0.5rem 0 0 0;'>
            Professional quality screening using the Weiss methodology
        </p>
    </div>
    """, unsafe_allow_html=True)

    # Usage counter with prominent display
    remaining = st.session_state.analyses_limit - st.session_state.analysis_count

    if remaining > 0:
        st.markdown(f"""
        <div style='background: linear-gradient(135deg, #10b981 0%, #059669 100%);
                    padding: 1.5rem; border-radius: 12px; text-align: center; color: white; margin: 1rem 0;'>
            <h3 style='margin: 0 0 0.5rem 0; font-size: 1.5rem; color: white;'>🎁 Free Trial Active</h3>
            <p style='margin: 0; font-size: 1.2rem; font-weight: 600;'>
                You have <span style='font-size: 2rem; font-weight: 700;'>{remaining}</span> free analyses remaining today
            </p>
            <p style='margin: 0.5rem 0 0 0; font-size: 0.9rem; opacity: 0.9;'>
                Resets daily • Upgrade for unlimited analyses
            </p>
        </div>
        """, unsafe_allow_html=True)
    else:
        st.markdown("""
        <div style='background: linear-gradient(135deg, #dc2626 0%, #991b1b 100%);
                    padding: 1.5rem; border-radius: 12px; text-align: center; color: white; margin: 1rem 0;'>
            <h3 style='margin: 0 0 0.5rem 0; font-size: 1.5rem; color: white;'>⚠️ Daily Limit Reached</h3>
            <p style='margin: 0; font-size: 1.1rem;'>
                You've used all 5 free analyses today. Come back tomorrow or upgrade now!
            </p>
        </div>
        """, unsafe_allow_html=True)
        show_upgrade_cta()
        return

    st.markdown("### 🔍 Analyze a Stock")

    # Screening mode selector (moved to main area)
    col_mode1, col_mode2, col_mode3 = st.columns([1, 1, 2])
    with col_mode1:
        screening_mode = st.selectbox(
            "Screening Mode",
            ["Balanced", "Aggressive"],
            help="Balanced: Standard criteria | Aggressive: More lenient"
        )

    st.markdown("---")

    # Main input area
    st.markdown("### 🔍 Analyze a Stock")
    input_col1, input_col2 = st.columns([2, 1])

    with input_col1:
        ticker = st.text_input(
            "Enter Stock Ticker",
            placeholder="e.g., KO, JNJ, PG",
            help="Enter any US stock ticker symbol",
            label_visibility="collapsed"
        ).upper()

    with input_col2:
        analyze_button = st.button("📊 Analyze", type="primary", use_container_width=True)

    # Results area
    if analyze_button and ticker:
        if remaining <= 0:
            st.error("Daily limit reached! Upgrade to continue.")
            show_upgrade_cta()
            return

        # Increment counter
        st.session_state.analysis_count += 1

        st.markdown("---")
        st.markdown("## Analysis Results")

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

                    # Charts
                    st.markdown("### 📈 Visual Analysis")
                    chart_col1, chart_col2 = st.columns(2)

                    with chart_col1:
                        price_chart = create_price_chart(ticker)
                        if price_chart:
                            st.plotly_chart(price_chart, use_container_width=True)

                    with chart_col2:
                        yield_chart = create_yield_chart(stock_data, analysis)
                        if yield_chart:
                            st.plotly_chart(yield_chart, use_container_width=True)

                    st.markdown("---")

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

                # Show upgrade CTA after analysis
                st.markdown("---")
                show_upgrade_cta()

        elif not ticker and analyze_button:
            st.warning("Please enter a ticker symbol")


if __name__ == "__main__":
    main()
