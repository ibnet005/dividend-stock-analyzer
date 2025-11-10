# 📊 Dividend Stock Analyzer

A comprehensive dividend-focused value investing tool using quality screening and yield analysis, based on the Weiss methodology.

## 🎯 Features

### Six Quality Criteria Assessment
1. **Dividend Increases** - Track 12-year dividend growth history
2. **Shares Outstanding** - Ensure adequate market capitalization
3. **Institutional Holders** - Verify institutional confidence
4. **EPS Increases** - Monitor earnings growth over 12 years
5. **Consecutive Dividend Years** - Measure dividend consistency
6. **Dividend Status** - Optional aristocrat/king classification

### Data Sources
- **Yahoo Finance** - Real-time stock data, dividends, institutional holders
- **SEC EDGAR** - Official EPS data for US stocks (free, unlimited)
- **Macrotrends** - Fallback EPS data for international stocks

### Valuation Analysis
- Yield-based buy/sell signals
- Historical yield analysis (5-year)
- Clear recommendations: BUY / SELL / WATCH / HOLD

## 📦 Two Versions Available

### 1. Desktop App (Tkinter)
Full-featured desktop application with:
- Advanced charting and visualization
- Watchlist management
- Batch analysis
- Historical data export

**Run:** `python3 weiss_stock_analyzer.py`

### 2. Web App (Streamlit)
Modern web interface with:
- Clean, responsive design
- Real-time analysis
- Mobile-friendly
- Easy sharing

**Run:** `streamlit run streamlit_app.py`

## 🚀 Quick Start

### Desktop App

```bash
# Install dependencies
pip3 install yfinance requests matplotlib

# Run the app
python3 weiss_stock_analyzer.py
```

### Web App

```bash
# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run the web app
streamlit run streamlit_app.py
```

The web app will open in your browser at http://localhost:8501

## 🌐 Deploy to Streamlit Cloud (Free)

### Step 1: Prepare Your Repository

1. Create a new GitHub repository
2. Upload these files:
   ```
   streamlit_app.py
   requirements.txt
   README.md
   ```

### Step 2: Deploy on Streamlit Cloud

1. Go to https://share.streamlit.io
2. Click **"New app"**
3. Connect your GitHub account
4. Select your repository
5. Set main file: `streamlit_app.py`
6. Click **"Deploy"**

Your app will be live at: `https://[your-app-name].streamlit.app`

### Step 3: Configure Settings (Optional)

In Streamlit Cloud dashboard:
- Set custom subdomain
- Configure secrets (if using API keys)
- Monitor usage and analytics

## 📋 Regional Support

The analyzer supports multiple currencies and exchanges:

- **USD** - NYSE, NASDAQ, AMEX (US stocks)
- **GBP** - LSE (UK stocks)
- **CAD** - TSX (Canadian stocks)
- **EUR** - Euronext Paris, Frankfurt, Amsterdam
- **JPY** - Tokyo Stock Exchange

## 🔧 Screening Modes

### Balanced Mode (Default)
Standard practical criteria aligned with IQ Trends methodology:
- 5+ dividend increases (12 years)
- 5M+ shares outstanding
- 80+ institutional holders
- 5+ EPS increases (12 years)
- 10+ consecutive dividend years

### Aggressive Mode
More lenient criteria for finding additional opportunities:
- 3+ dividend increases
- Reduced share requirements
- 50+ institutional holders
- 4+ EPS increases
- 10+ consecutive dividend years (minimum floor)

## 💡 Usage Tips

### Desktop App
1. Enter ticker symbol (e.g., AAPL, KO, JNJ)
2. Click "Fetch Data" to auto-populate fields
3. Verify/adjust data if needed
4. Click "Analyze" for full assessment
5. Review quality criteria and valuation signals

### Web App
1. Enter ticker symbol
2. Select screening mode
3. Click "Analyze Stock"
4. Review results and recommendations
5. Follow action items for investment decisions

## 📊 Understanding Results

### Quality Assessment
- ✅ **PASSED** - Meets all quality criteria
- ❌ **FAILED** - Does not meet minimum standards

### Valuation Signals
- 🟢 **BUY** - Stock is undervalued (yield ≥ 80% of historical high)
- 🟡 **WATCH** - Approaching buy zone (yield ≥ 70% of historical high)
- 🔵 **HOLD** - Fairly valued
- 🔴 **SELL** - Overvalued (yield ≤ 120% of historical low)

### Investment Ratings
- **A+/A** - Quality stock in BUY zone (excellent opportunity)
- **B+/B** - Quality stock in WATCH zone (monitor)
- **C+/C** - Quality stock in HOLD zone (fairly valued)
- **D/D-** - Quality stock in SELL zone (overvalued)
- **F** - Failed quality criteria (not investable)

## ⚠️ Disclaimer

This tool is for informational and educational purposes only and does not constitute investment advice. You are solely responsible for your investment decisions. Past performance does not guarantee future results. Always conduct your own due diligence and consult with a licensed financial advisor before investing.

## 🛠️ Technical Details

### Dependencies
- **yfinance** - Stock data fetching
- **requests** - SEC EDGAR API calls
- **pandas** - Data manipulation
- **streamlit** - Web framework (web version)
- **tkinter** - GUI framework (desktop version)
- **matplotlib** - Charting (desktop version)

### Data Caching
- EPS data is cached to reduce API calls
- Cache file: `eps_cache.json`
- Cached data expires based on freshness

### Rate Limiting
- SEC EDGAR: 0.5 second delays between requests
- Yahoo Finance: Respects API rate limits
- Macrotrends: Polite scraping with delays

## 📝 File Structure

```
Stock Picker/
├── weiss_stock_analyzer.py    # Desktop app (Tkinter)
├── streamlit_app.py            # Web app (Streamlit)
├── requirements.txt            # Python dependencies
├── README.md                   # This file
├── eps_cache.json             # EPS data cache (auto-generated)
└── venv/                      # Virtual environment (local only)
```

## 🔄 Updates & Maintenance

### Keeping Data Fresh
- EPS data: Re-fetch after quarterly earnings
- Dividend data: Updates automatically from Yahoo Finance
- Stock prices: Real-time from Yahoo Finance

### Troubleshooting

**EPS Data Not Available:**
- Check if stock is US-based (SEC EDGAR only covers US)
- Verify ticker is in hardcoded CIK list
- Manually enter EPS data using provided links

**Stock Not Found:**
- Verify ticker format (e.g., BP.L for UK, RY.TO for Canada)
- Check spelling and exchange suffix
- Ensure stock is publicly traded

**Slow Performance:**
- Clear EPS cache file
- Check internet connection
- Reduce number of concurrent requests

## 🤝 Contributing

This is a personal investment tool. Feel free to fork and customize for your needs.

## 📧 Support

For issues or questions about deployment, consult:
- Streamlit docs: https://docs.streamlit.io
- GitHub issues for this repository

## 📜 License

This tool is provided as-is for personal use. Not for commercial redistribution.

---

**Built with ❤️ for dividend investors**
