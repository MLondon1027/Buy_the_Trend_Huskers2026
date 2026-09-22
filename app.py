import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import json
import requests
import urllib3
from datetime import datetime, timedelta
import warnings
warnings.filterwarnings('ignore')

# Suppress SSL warnings for the GitHub request
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Page configuration
st.set_page_config(
    page_title="Buy the Trend - Momentum Strategy Dashboard",
    page_icon="📈",
    layout="wide"
)

st.title("📈 Buy the Trend - Momentum Strategy Backtesting")
st.markdown("""
This dashboard backtests a momentum strategy where you invest in the top performing stocks from the previous year, 
with **full compounding** - profits are reinvested each year. Compare this against investing in SPY (S&P 500 ETF) 
with the same compounding approach.
""")

# Load S&P 500 membership data for full universe option
@st.cache_data(ttl=86400)  # Cache for 24 hours
def get_sp500_membership():
    """Load historical S&P 500 membership data"""
    try:
        # Try to load from local file first
        try:
            with open('sp500_membership.json', 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            # If not available locally, download from GitHub with SSL verification disabled
            url = "https://raw.githubusercontent.com/joeyfife/point-in-time-sp500/main/data/membership.json"
            try:
                response = requests.get(url, timeout=10, verify=False)
                if response.status_code == 200:
                    data = response.json()
                    # Save locally for future use
                    with open('sp500_membership.json', 'w') as f:
                        json.dump(data, f)
                    return data
                else:
                    st.warning("Could not load S&P 500 membership data. Using current members only.")
                    return None
            except requests.exceptions.SSLError:
                # If SSL fails, try with a different approach or use basic current members
                st.warning("SSL certificate verification failed. Using current S&P 500 members only.")
                # Return a simple structure with current members only
                return {
                    "current": ["AAPL", "MSFT", "GOOGL", "AMZN", "META", "NVDA", "TSLA", "JPM", "V", "JNJ",
                               "WMT", "PG", "MA", "HD", "DIS", "PYPL", "ADBE", "CRM", "NFLX", "INTC"],
                    "changes": []
                }
    except Exception as e:
        st.warning(f"Error loading S&P 500 membership data: {e}. Using current members only.")
        return None

sp500_data_for_universe = get_sp500_membership()

# Sidebar for user inputs
st.sidebar.header("Strategy Parameters")

# Year selection
current_year = datetime.now().year
min_year = st.sidebar.number_input(
    "Start Year",
    min_value=1990,
    max_value=current_year - 2,
    value=2010
)

max_year = st.sidebar.number_input(
    "End Year",
    min_value=min_year + 2,
    max_value=current_year,
    value=current_year - 1
)

# Stock universe selection
st.sidebar.subheader("Stock Universe")
stock_universe_option = st.sidebar.radio(
    "Select Stock Universe",
    ["Full S&P 500 (Historical)", "S&P 500 Sample", "Popular Tech Stocks", "Healthcare", "Finance", "Oil & Gas", "Consumer Goods", "Custom List"]
)

if stock_universe_option == "Full S&P 500 (Historical)":
    # Get all unique stocks that were ever in S&P 500 during the study period
    if sp500_data_for_universe:
        all_stocks = set(sp500_data_for_universe['current'])
        # Add all stocks from changes
        for change in sp500_data_for_universe['changes']:
            if change['added']:
                all_stocks.add(change['added'])
        selected_stocks = list(all_stocks)
        st.sidebar.write(f"Using full historical S&P 500: {len(selected_stocks)} stocks")
        st.sidebar.warning("⚠️ This will fetch data for 500+ stocks and may take several minutes.")
    else:
        st.sidebar.warning("Could not load S&P 500 data. Using sample instead.")
        default_stocks = [
            "AAPL", "MSFT", "GOOGL", "AMZN", "META", "NVDA", "TSLA", "JPM", "V", "JNJ",
            "WMT", "PG", "MA", "HD", "DIS", "PYPL", "ADBE", "CRM", "NFLX", "INTC"
        ]
        selected_stocks = default_stocks
elif stock_universe_option == "S&P 500 Sample":
    # Popular S&P 500 stocks for demonstration
    default_stocks = [
        "AAPL", "MSFT", "GOOGL", "AMZN", "META", "NVDA", "TSLA", "JPM", "V", "JNJ",
        "WMT", "PG", "MA", "HD", "DIS", "PYPL", "ADBE", "CRM", "NFLX", "INTC"
    ]
    selected_stocks = default_stocks
elif stock_universe_option == "Popular Tech Stocks":
    selected_stocks = ["AAPL", "MSFT", "GOOGL", "AMZN", "META", "NVDA", "TSLA", "NFLX", "ADBE", "CRM"]
elif stock_universe_option == "Healthcare":
    selected_stocks = ["JNJ", "PFE", "UNH", "ABT", "TMO", "MRK", "LLY", "DHR", "ABCV", "MDT"]
elif stock_universe_option == "Finance":
    selected_stocks = ["JPM", "BAC", "WFC", "C", "GS", "MS", "BLK", "SCHW", "AXP", "USB"]
elif stock_universe_option == "Oil & Gas":
    selected_stocks = ["XOM", "CVX", "COP", "SLB", "EOG", "PXD", "MPC", "PSX", "VLO", "OXY"]
elif stock_universe_option == "Consumer Goods":
    selected_stocks = ["PG", "KO", "PEP", "COST", "WMT", "HD", "MCD", "NKE", "SBUX", "TGT"]
else:
    custom_stocks = st.sidebar.text_area(
        "Enter stock symbols (comma-separated)",
        "AAPL, MSFT, GOOGL, AMZN, META, NVDA, TSLA"
    )
    selected_stocks = [s.strip().upper() for s in custom_stocks.split(",") if s.strip()]

if stock_universe_option != "Full S&P 500 (Historical)":
    st.sidebar.write(f"Selected {len(selected_stocks)} stocks for analysis")

# Number of top stocks to select
num_top_stocks = st.sidebar.number_input(
    "Number of Top Stocks to Select",
    min_value=1,
    max_value=10,
    value=3,
    step=1
)

# Total investment amount
total_investment = st.sidebar.number_input(
    "Total Investment Amount ($)",
    min_value=1000,
    max_value=1000000,
    value=10000,
    step=1000
)

# Calculate investment per stock
investment_per_stock = total_investment / num_top_stocks

# Dividend inclusion toggle
include_dividends = st.sidebar.checkbox(
    "Include Dividend Returns",
    value=True,
    help="When enabled, uses 'Adj Close' prices which include dividend reinvestment. When disabled, uses 'Close' prices only. Note: yfinance data may have limitations in providing completely unadjusted data."
)

def normalize_columns(stock_data, include_dividends=True):
    """Normalize column names to handle different yfinance versions"""
    # Reset index if it's a MultiIndex to get standard columns
    if isinstance(stock_data.columns, pd.MultiIndex):
        stock_data = stock_data.copy()
        stock_data.columns = stock_data.columns.get_level_values(0)
    
    # Ensure we have the expected columns based on dividend preference
    if include_dividends:
        if 'Adj Close' not in stock_data.columns and 'Close' in stock_data.columns:
            stock_data['Adj Close'] = stock_data['Close']
    else:
        if 'Close' not in stock_data.columns and 'Adj Close' in stock_data.columns:
            stock_data['Close'] = stock_data['Adj Close']
    
    return stock_data

def get_sp500_members_for_year(sp500_data, year):
    """Get S&P 500 members for a specific year"""
    if sp500_data is None:
        return None
    
    # Start with current members
    members = set(sp500_data['current'])
    
    # Apply changes backwards from current date to the target year
    # Sort changes by date descending (most recent first)
    changes = sorted(sp500_data['changes'], key=lambda x: x['date'], reverse=True)
    
    for change in changes:
        change_date = datetime.strptime(change['date'], '%Y-%m-%d')
        
        # Only process changes that happened after the target year
        # We want to undo changes that happened after the target year
        if change_date.year <= year:
            continue
        
        # Apply the change in reverse (undo the change)
        if change['added']:
            # If it was added after our target year, remove it
            members.discard(change['added'])
        if change['removed']:
            # If it was removed after our target year, add it back
            members.add(change['removed'])
    
    return members

@st.cache_data(ttl=3600)
def get_stock_data(symbols, start_date, end_date, include_dividends=True):
    """Fetch historical stock data for given symbols"""
    data = {}
    for symbol in symbols:
        try:
            # When dividends are disabled, we need to get non-adjusted data
            # yfinance doesn't have a direct parameter for this, but we can work around it
            stock_data = yf.download(symbol, start=start_date, end=end_date, progress=False)
            if not stock_data.empty:
                # If dividends are disabled, we'll use Close prices and ignore Adj Close
                if not include_dividends:
                    # Create a copy to avoid modifying the original
                    stock_data = stock_data.copy()
                    # Remove Adj Close to force use of Close prices
                    if 'Adj Close' in stock_data.columns:
                        del stock_data['Adj Close']
                
                data[symbol] = normalize_columns(stock_data, include_dividends)
        except Exception as e:
            st.warning(f"Could not fetch data for {symbol}: {e}")
    return data

def calculate_annual_returns(stock_data, year, include_dividends=True):
    """Calculate annual return for a specific year"""
    start_date = f"{year}-01-01"
    end_date = f"{year}-12-31"
    
    try:
        year_data = stock_data.loc[start_date:end_date]
        if len(year_data) < 2:
            return None
        
        # Use appropriate price column based on dividend preference
        price_column = 'Adj Close' if include_dividends else 'Close'
        
        start_price = year_data[price_column].iloc[0]
        end_price = year_data[price_column].iloc[-1]
        annual_return = (end_price - start_price) / start_price
        return annual_return
    except:
        return None

def run_momentum_strategy(stock_data_dict, start_year, end_year, total_investment, num_top_stocks, sp500_data, include_dividends=True):
    """Run the momentum strategy backtest with compounding and S&P 500 membership filtering"""
    results = []
    
    # Calculate investment per stock
    investment_per_stock = total_investment / num_top_stocks
    
    # Initial investments
    portfolio_value = total_investment  # Total initial investment
    spy_value = total_investment  # SPY starts with same total investment
    previous_portfolio_value = total_investment  # Track previous year's value for annual return calculation
    
    # Get SPY data for comparison
    spy_data = yf.download("SPY", start=f"{start_year-1}-01-01", end=f"{end_year+1}-01-01", progress=False)
    spy_data = normalize_columns(spy_data, include_dividends)
    
    for year in range(start_year, end_year + 1):
        # Calculate returns for previous year
        prev_year = year - 1
        stock_returns = {}
        
        # Get S&P 500 members for the selection year (previous year)
        sp500_members = get_sp500_members_for_year(sp500_data, prev_year)
        
        for symbol, data in stock_data_dict.items():
            # Only consider stocks that were in S&P 500 during the selection year
            if sp500_members and symbol not in sp500_members:
                continue
                
            annual_return = calculate_annual_returns(data, prev_year, include_dividends)
            if annual_return is not None:
                stock_returns[symbol] = annual_return
        
        # Select top performing stocks
        num_stocks_to_select = min(num_top_stocks, len(stock_returns))
        if num_stocks_to_select > 0:
            top_stocks = sorted(stock_returns.items(), key=lambda x: x[1], reverse=True)[:num_stocks_to_select]
            top_symbols = [stock[0] for stock in top_stocks]
            top_returns = [stock[1] for stock in top_stocks]
        else:
            top_stocks = []
            top_symbols = []
            top_returns = []
        
        # Comprehensive debug info for first year
        if year == start_year and st.checkbox("Show Detailed Selection Process"):
            st.subheader(f"Selection Process for Year {year}")
            st.write(f"**Selection Year**: {prev_year} (used to pick stocks for {year})")
            st.write(f"**Performance Year**: {year} (calculate returns for selected stocks)")
            st.write(f"**S&P 500 Members in {prev_year}**: {len(sp500_members) if sp500_members else 'N/A'}")
            st.write(f"**Stocks with {prev_year} Data**: {len(stock_returns)}")
            st.write(f"**Top {num_stocks_to_select} Selected**: {top_symbols}")
            st.write(f"**Selection Returns ({prev_year})**:")
            for i, (symbol, ret) in enumerate(top_stocks):
                st.write(f"  {i+1}. {symbol}: {ret:.2%}")
        
        # Calculate portfolio performance for current year with compounding
        # Divide current portfolio value equally among top stocks
        investment_per_stock_this_year = portfolio_value / len(top_symbols) if top_symbols else 0
        year_portfolio_value = 0
        stock_performance = {}
        
        for symbol in top_symbols:
            if symbol in stock_data_dict:
                current_year_return = calculate_annual_returns(stock_data_dict[symbol], year, include_dividends)
                if current_year_return is not None:
                    stock_value = investment_per_stock_this_year * (1 + current_year_return)
                    year_portfolio_value += stock_value
                    stock_performance[symbol] = {
                        'return': current_year_return,
                        'value': stock_value,
                        'investment': investment_per_stock_this_year
                    }
                else:
                    year_portfolio_value += investment_per_stock_this_year
                    stock_performance[symbol] = {
                        'return': 0,
                        'value': investment_per_stock_this_year,
                        'investment': investment_per_stock_this_year
                    }
        
        # Performance debug info for first year
        if year == start_year and st.checkbox("Show Detailed Performance Process"):
            st.subheader(f"Performance Calculation for Year {year}")
            st.write(f"**Investment per Stock**: ${investment_per_stock_this_year:,.2f}")
            st.write(f"**Performance Returns ({year})**:")
            for symbol, perf in stock_performance.items():
                st.write(f"  {symbol}: {perf['return']:.2%} → ${perf['value']:,.2f}")
        
        # Debug info for first year performance
        if year == start_year and st.checkbox("Show Performance Debug Info"):
            st.write(f"Year {year}: Performance calculation")
            st.write(f"Selected stocks held during {year}:")
            for symbol, perf in stock_performance.items():
                st.write(f"  {symbol}: {perf['return']:.2%} (in {year}) - Value: ${perf['value']:,.2f}")
        
        # Update portfolio value for next year (compounding)
        portfolio_value = year_portfolio_value
        
        # Calculate annual strategy return
        annual_strategy_return = (portfolio_value - previous_portfolio_value) / previous_portfolio_value if previous_portfolio_value > 0 else 0
        
        # Calculate SPY performance for comparison with compounding
        spy_year_data = spy_data.loc[f"{year}-01-01":f"{year}-12-31"]
        spy_price_column = 'Adj Close' if include_dividends else 'Close'
        if len(spy_year_data) > 0 and spy_price_column in spy_year_data.columns:
            spy_start = spy_year_data[spy_price_column].iloc[0]
            spy_end = spy_year_data[spy_price_column].iloc[-1]
        else:
            spy_start = None
            spy_end = None
        
        if spy_start and spy_end:
            spy_return = (spy_end - spy_start) / spy_start
            spy_value = spy_value * (1 + spy_return)  # Compound the SPY investment
        else:
            spy_return = 0
            # spy_value stays the same if no data
        
        results.append({
            'year': year,
            'top_stocks': top_symbols,
            'prev_year_returns': top_returns,
            'portfolio_value': portfolio_value,
            'spy_value': spy_value,
            'spy_return': spy_return,
            'annual_strategy_return': annual_strategy_return,
            'stock_performance': stock_performance
        })
        
        # Update previous portfolio value for next year's calculation
        previous_portfolio_value = portfolio_value
    
    return results, spy_data

# Main execution
if st.button("Run Backtest"):
    with st.spinner("Fetching stock data and running backtest..."):
        # Load S&P 500 membership data
        sp500_data = get_sp500_membership()
        if sp500_data:
            st.success("Loaded historical S&P 500 membership data")
        
        # Fetch data for all years needed
        start_date = f"{min_year - 1}-01-01"
        end_date = f"{max_year}-12-31"
        
        stock_data_dict = get_stock_data(selected_stocks, start_date, end_date, include_dividends)
        
        if not stock_data_dict:
            st.error("Could not fetch stock data. Please check your internet connection and try again.")
        else:
            st.success(f"Successfully fetched data for {len(stock_data_dict)} stocks")
            
            # Debug info to show what columns are available
            if st.checkbox("Show Debug Info"):
                st.write("Data columns available for first stock:")
                first_symbol = list(stock_data_dict.keys())[0]
                st.write(f"Symbol: {first_symbol}")
                st.write("Columns:", stock_data_dict[first_symbol].columns.tolist())
                st.write("Sample data:")
                st.write(stock_data_dict[first_symbol].head())
            
            # Run backtest
            results, spy_data = run_momentum_strategy(
                stock_data_dict, 
                min_year, 
                max_year, 
                total_investment,
                num_top_stocks,
                sp500_data,
                include_dividends
            )
            
            # Display results
            st.header("Backtest Results")
            
            # Create summary metrics
            initial_investment = total_investment
            final_portfolio_value = results[-1]['portfolio_value']
            final_spy_value = results[-1]['spy_value']
            
            portfolio_total_return = (final_portfolio_value - initial_investment) / initial_investment
            spy_total_return = (final_spy_value - initial_investment) / initial_investment
            
            # Calculate CAGR
            num_years = max_year - min_year + 1
            portfolio_cagr = (final_portfolio_value / initial_investment) ** (1/num_years) - 1
            spy_cagr = (final_spy_value / initial_investment) ** (1/num_years) - 1
            
            # Display metrics
            col1, col2, col3, col4 = st.columns(4)
            
            col1.metric("Initial Investment", f"${initial_investment:,.2f}")
            col2.metric("Strategy Final Value", f"${final_portfolio_value:,.2f}", f"{portfolio_total_return:.2%}")
            col3.metric("SPY Final Value", f"${final_spy_value:,.2f}", f"{spy_total_return:.2%}")
            col4.metric("Outperformance", f"${final_portfolio_value - final_spy_value:,.2f}", f"{portfolio_total_return - spy_total_return:.2%}")
            
            # CAGR comparison
            st.subheader("Compound Annual Growth Rate (CAGR)")
            col1, col2 = st.columns(2)
            col1.metric("Strategy CAGR", f"{portfolio_cagr:.2%}")
            col2.metric("SPY CAGR", f"{spy_cagr:.2%}")
            
            # Create performance chart
            st.subheader("Portfolio Performance Over Time")
            
            years = [r['year'] for r in results]
            portfolio_values = [r['portfolio_value'] for r in results]
            spy_values = [r['spy_value'] for r in results]
            
            fig = go.Figure()
            
            fig.add_trace(go.Scatter(
                x=years,
                y=portfolio_values,
                mode='lines+markers',
                name='Momentum Strategy',
                line=dict(color='#2ecc71', width=3)
            ))
            
            fig.add_trace(go.Scatter(
                x=years,
                y=spy_values,
                mode='lines+markers',
                name='SPY Benchmark',
                line=dict(color='#3498db', width=3)
            ))
            
            fig.update_layout(
                title="Portfolio Value Comparison",
                xaxis_title="Year",
                yaxis_title="Portfolio Value ($)",
                hovermode='x unified',
                template='plotly_white',
                height=500
            )
            
            st.plotly_chart(fig, use_container_width=True)
            
            # Annual breakdown
            st.subheader("Annual Breakdown")
            
            annual_data = []
            for r in results:
                # Create a row with basic info
                row_data = {
                    'Year': r['year'],
                    'Top Stocks': ', '.join(r['top_stocks']),
                    'Portfolio Value': f"${r['portfolio_value']:,.2f}",
                    'SPY Value': f"${r['spy_value']:,.2f}",
                    'Strategy Annual Return': f"{r['annual_strategy_return']:.2%}",
                    'Strategy Cumulative Return': f"{(r['portfolio_value'] / total_investment - 1):.2%}",
                    'SPY Annual Return': f"{r['spy_return']:.2%}"
                }
                
                # Add individual stock returns for the year
                for i, symbol in enumerate(r['top_stocks']):
                    if symbol in r['stock_performance']:
                        row_data[f'{symbol} Return'] = f"{r['stock_performance'][symbol]['return']:.2%}"
                    else:
                        row_data[f'{symbol} Return'] = "N/A"
                
                annual_data.append(row_data)
            
            annual_df = pd.DataFrame(annual_data)
            st.dataframe(annual_df, use_container_width=True)
            
            # Stock selection details
            st.subheader("Stock Selection Details")
            
            for r in results:
                with st.expander(f"Year {r['year']} - Selected: {', '.join(r['top_stocks'])}"):
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        st.write("**Previous Year Performance (Selection Criteria):**")
                        for i, (symbol, ret) in enumerate(zip(r['top_stocks'], r['prev_year_returns'])):
                            st.write(f"{i+1}. {symbol}: {ret:.2%}")
                    
                    with col2:
                        st.write("**Current Year Performance:**")
                        for symbol, perf in r['stock_performance'].items():
                            investment = perf.get('investment', investment_per_stock)
                            st.write(f"{symbol}: {perf['return']:.2%} (${perf['value']:,.2f}) [Invested: ${investment:,.2f}]")

# Instructions
st.sidebar.markdown("---")
st.sidebar.markdown(f"""
### How it works:
1. At the start of each year, the strategy looks at the previous year's returns
2. It selects the top {num_top_stocks} performing stocks **from S&P 500 members only**
3. Invests equal portions of the **total portfolio value** in each stock
4. Holds for the entire year
5. **Reinvests all profits** at the start of the next year (compounding)
6. Rebalances annually with the new total portfolio value

### Historical S&P 500 Filtering:
✅ Only stocks that were actually in the S&P 500 during the selection year are considered
✅ Uses historical membership data from 1976-present
✅ Ensures accurate backtesting with survivorship bias correction

### Dividend Returns:
{'✅ Dividend returns INCLUDED (uses Adj Close prices)' if include_dividends else '❌ Dividend returns EXCLUDED (uses Close prices only)'}

### Current Settings:
- Top stocks per year: {num_top_stocks}
- Investment per stock: ${investment_per_stock:,.0f}
- Total initial investment: ${total_investment:,.0f}

### Comparison:
- Strategy: ${total_investment:,.0f} initial, fully compounded yearly
- Benchmark: ${total_investment:,.0f} initial in SPY, fully compounded yearly
- Both strategies reinvest all gains for true compound growth comparison
""")