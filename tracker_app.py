# MKK Investment Tracker — v1.9.5
# - Supports multiple portfolios (e.g., IRA, Roth) per user with isolated data
# - Portfolio selector dropdown to switch between portfolios
# - Add Holding: Dynamic Total Invested calculation with auto-calculated message on tab-out
# - Form layout: Ticker → Shares → Price → Total Invested (auto-calc) → Dividends
# - Version bumped to 1.9.5 for multi-portfolio support

import json, os, re, shutil, sys
from datetime import datetime, date
from typing import Dict, Any
import streamlit as st, yfinance as yf, pandas as pd, numpy as np
import bcrypt

APP_NAME = "MKK Investment Tracker"
st.set_page_config(page_title=APP_NAME, page_icon="💠", layout="wide")

# Custom CSS for polished look and feel
st.markdown("""
    <style>
    body {
        font-family: 'Roboto', sans-serif;
    }
    .stButton>button {
        background-color: #1f77b4;
        color: white;
        border-radius: 8px;
        padding: 8px 16px;
        transition: background-color 0.3s;
    }
    .stButton>button:hover {
        background-color: #145a87;
    }
    .stDataFrame {
        border: 1px solid #e0e0e0;
        border-radius: 8px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }
    .stTextInput>input {
        border-radius: 6px;
        padding: 6px;
        border: 1px solid #d0d0d0;
    }
    .stSelectbox select {
        border-radius: 6px;
        padding: 6px;
    }
    .metric-container {
        padding: 10px;
        margin: 5px 0;
    }
    .stTabs [role="tab"] {
        padding: 8px 16px;
        border-radius: 6px 6px 0 0;
        margin-right: 5px;
    }
    .stTabs [role="tab"][aria-selected="true"] {
        background-color: #f0f2f6;
    }
    .calculated-field {
        background-color: #f0f8ff;
    }
    </style>
""", unsafe_allow_html=True)

# User authentication and portfolio storage
USERS_FILE = "users.json"
def load_users():
    if os.path.exists(USERS_FILE):
        try:
            with open(USERS_FILE, "r") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def save_users(users):
    try:
        with open(USERS_FILE, "w") as f:
            json.dump(users, f, indent=2)
    except Exception as e:
        st.warning(f"Failed to save users to {USERS_FILE}: {e}")

def save_portfolio():
    if "user_id" in st.session_state and st.session_state["user_id"]:
        try:
            data_file = f"portfolio_{st.session_state['user_id']}.json"
            with open(data_file, "w") as f:
                json.dump(st.session_state["DATA"], f, indent=2)
        except Exception as e:
            st.warning(f"Failed to save portfolio to {data_file}: {e}")

def load_portfolio():
    if "user_id" in st.session_state and st.session_state["user_id"]:
        data_file = f"portfolio_{st.session_state['user_id']}.json"
        if os.path.exists(data_file):
            try:
                with open(data_file, "r") as f:
                    data = json.load(f)
                    data.setdefault("portfolios", {
                        "IRA": {
                            "holdings": {},
                            "cash_uninvested": 0.0,
                            "settings": {"currency": "USD", "auto_price": True},
                            "last_prices": {},
                            "last_updated": None
                        },
                        "Roth": {
                            "holdings": {},
                            "cash_uninvested": 0.0,
                            "settings": {"currency": "USD", "auto_price": True},
                            "last_prices": {},
                            "last_updated": None
                        }
                    })
                    data["version"] = "1.9.5"
                    for portfolio in data["portfolios"].values():
                        portfolio.setdefault("holdings", {})
                        portfolio.setdefault("cash_uninvested", 0.0)
                        portfolio.setdefault("settings", {"currency": "USD", "auto_price": True})
                        portfolio.setdefault("last_prices", {})
                        portfolio.setdefault("last_updated", None)
                        for rec in portfolio.get("holdings", {}).values():
                            rec.setdefault("purchase_price", None)
                            rec.setdefault("dividends_collected", 0.0)
                            rec.setdefault("last_div_amount", 0.0)
                            rec.setdefault("last_div_date", "")
                            rec.setdefault("summary", "")
                    return data
            except Exception as e:
                st.warning(f"Failed to load portfolio from {data_file}: {e}")
    return {
        "portfolios": {
            "IRA": {
                "holdings": {},
                "cash_uninvested": 0.0,
                "settings": {"currency": "USD", "auto_price": True},
                "last_prices": {},
                "last_updated": None
            },
            "Roth": {
                "holdings": {},
                "cash_uninvested": 0.0,
                "settings": {"currency": "USD", "auto_price": True},
                "last_prices": {},
                "last_updated": None
            }
        },
        "version": "1.9.5"
    }

# Login form
if "user_id" not in st.session_state or not st.session_state["user_id"]:
    st.title("Login to MKK Investment Tracker")
    st.markdown("Enter your username and password to access your portfolio, or register a new account.")
    users = load_users()
    
    with st.form(key="login_form"):
        col1, col2 = st.columns(2)
        username = col1.text_input("Username", placeholder="e.g., john123")
        password = col2.text_input("Password", type="password", placeholder="Enter your password")
        col3, col4 = st.columns(2)
        login_button = col3.form_submit_button("Login")
        register_button = col4.form_submit_button("Register")
    
    if login_button:
        if not username or not password:
            st.error("Please enter both username and password.")
        elif username in users:
            hashed_password = users[username].encode('utf-8')
            if bcrypt.checkpw(password.encode('utf-8'), hashed_password):
                st.session_state["user_id"] = username
                st.session_state["DATA"] = load_portfolio()
                st.session_state["selected_portfolio"] = "IRA"  # Default to IRA
                st.success(f"Logged in as {username}!")
                st.rerun()
            else:
                st.error("Incorrect password.")
        else:
            st.error("Username not found. Please register.")
    
    if register_button:
        if not username or not password:
            st.error("Please enter both username and password.")
        elif username in users:
            st.error("Username already exists. Choose another or login.")
        else:
            hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
            users[username] = hashed_password.decode('utf-8')
            save_users(users)
            st.session_state["user_id"] = username
            st.session_state["DATA"] = load_portfolio()
            st.session_state["selected_portfolio"] = "IRA"
            st.success(f"Registered and logged in as {username}!")
            st.rerun()
else:
    st.markdown(f"Logged in as: **{st.session_state['user_id']}**")
    st.warning("Portfolio data is saved automatically to 'portfolio_<username>.json' in the app directory. Use the 'Backup' tab for manual JSON downloads or to restore from a different file.", icon="ℹ️")

    if "DATA" not in st.session_state:
        st.session_state["DATA"] = load_portfolio()
    if "selected_portfolio" not in st.session_state:
        st.session_state["selected_portfolio"] = "IRA"

    # Portfolio selector
    st.selectbox(
        "Select Portfolio",
        options=list(st.session_state["DATA"]["portfolios"].keys()),
        index=list(st.session_state["DATA"]["portfolios"].keys()).index(st.session_state["selected_portfolio"]),
        key="portfolio_selector",
        on_change=lambda: st.rerun()
    )

    def money_to_float(text: str) -> float:
        if text is None: return 0.0
        s = str(text).strip().replace(',', '').replace('$', '')
        try: return float(s) if s else 0.0
        except: return 0.0

    def money_str(x: float) -> str:
        if x is None or not np.isfinite(x): return ""
        return f"${x:,.2f}"

    def shares_to_float(text: str) -> float:
        if text is None: return 0.0
        s = str(text).strip().replace(',', ' ').replace('\u00a0', ' ').strip()
        s = re.sub(r'\s+', '', s)
        try: return float(s) if s else 0.0
        except: return 0.0

    @st.cache_data(show_spinner=False)
    def fetch_price(ticker: str) -> float:
        try:
            t = yf.Ticker(ticker)
            price = t.fast_info.get('lastPrice', float('nan'))
            if np.isnan(price):
                hist = t.history(period="5d", interval="1d")
                if hist is None or hist.empty: return float("nan")
                price = float(hist["Close"].dropna().iloc[-1])
            return price
        except Exception:
            return float("nan")

    @st.cache_data(show_spinner=False)
    def fetch_name_and_summary(ticker: str):
        try:
            tk = yf.Ticker(ticker)
            info = tk.info or {}
            name = info.get("longName") or info.get("shortName") or info.get("symbol") or ticker
            summary = info.get("longBusinessSummary") or info.get("description") or ""
            if summary: summary = (summary[:500] + "…") if len(summary) > 500 else summary
            return name, summary
        except Exception: return ticker, ""

    @st.cache_data(show_spinner=False)
    def fetch_dividend_frequency(ticker: str) -> str:
        try:
            t = yf.Ticker(ticker)
            div = t.dividends
            if div is None or len(div) < 3: return "Irregular/None"
            dates = pd.to_datetime(div.index).sort_values()
            cutoff = pd.Timestamp.utcnow() - pd.Timedelta(days=3*365)
            dates = dates[dates >= cutoff]
            if len(dates) < 3: return "Irregular/None"
            diffs = (dates[1:] - dates[:-1]).days.values
            if len(diffs) == 0: return "Irregular/None"
            med = float(np.median(diffs))
            if med <= 9: return "Weekly"
            if med <= 45: return "Monthly"
            if med <= 115: return "Quarterly"
            if med <= 220: return "Semiannual"
            if med <= 400: return "Annual"
            return "Irregular/None"
        except Exception:
            return "Irregular/None"

    st.title(f"MKK Investment Tracker - {st.session_state['selected_portfolio']}")
    tab_port, tab_add, tab_edit, tab_div, tab_trueada, tab_migrate, tab_backup, tab_settings = st.tabs([
        "Portfolio", "Add Holding", "Edit Holdings", "Dividends", "True ADA", "Migration", "Backup", "Settings"
    ])

    with tab_settings:
        st.subheader("Settings", divider="gray")
        portfolio_data = st.session_state["DATA"]["portfolios"][st.session_state["selected_portfolio"]]
        portfolio_data["settings"]["currency"] = st.selectbox(
            "Currency (display only)",
            ["USD", "EUR", "GBP", "JPY", "CAD"],
            index=["USD", "EUR", "GBP", "JPY", "CAD"].index(portfolio_data["settings"].get("currency", "USD")),
            key=f"currency_{st.session_state['selected_portfolio']}"
        )
        portfolio_data["settings"]["auto_price"] = st.checkbox(
            "Auto-update prices from the internet",
            value=portfolio_data["settings"].get("auto_price", True),
            key=f"auto_price_{st.session_state['selected_portfolio']}"
        )
        if st.button("🔄 Update all prices now"):
            fetch_price.clear()
            updated = 0
            for tkr, rec in portfolio_data["holdings"].items():
                p = fetch_price(tkr)
                if np.isfinite(p):
                    portfolio_data["last_prices"][tkr] = p
                    updated += 1
            portfolio_data["last_updated"] = datetime.now().isoformat(timespec="seconds")
            save_portfolio()
            st.success(f"Updated {updated} tickers.")
        st.markdown("---")
        st.subheader("Portfolio Management", divider="gray")
        new_portfolio_name = st.text_input("Create New Portfolio", placeholder="e.g., Taxable")
        if st.button("Create Portfolio"):
            if new_portfolio_name and new_portfolio_name not in st.session_state["DATA"]["portfolios"]:
                st.session_state["DATA"]["portfolios"][new_portfolio_name] = {
                    "holdings": {},
                    "cash_uninvested": 0.0,
                    "settings": {"currency": "USD", "auto_price": True},
                    "last_prices": {},
                    "last_updated": None
                }
                save_portfolio()
                st.success(f"Created portfolio: {new_portfolio_name}")
                st.rerun()
            elif new_portfolio_name in st.session_state["DATA"]["portfolios"]:
                st.error("Portfolio name already exists.")
            else:
                st.error("Enter a portfolio name.")
        st.markdown("---")
        st.subheader("User Management", divider="gray")
        st.write(f"Current user: **{st.session_state['user_id']}**")
        if st.button("Switch User"):
            st.session_state.pop("user_id", None)
            st.session_state.pop("DATA", None)
            st.session_state.pop("selected_portfolio", None)
            st.rerun()

    with tab_port:
        portfolio_data = st.session_state["DATA"]["portfolios"][st.session_state["selected_portfolio"]]
        if not portfolio_data["holdings"]:
            st.info(f"No holdings yet in {st.session_state['selected_portfolio']}. Add your first position in **Add Holding**.")
        else:
            if st.button("🔄 Refresh Prices"):
                fetch_price.clear()
                updated = 0
                for tkr, rec in portfolio_data["holdings"].items():
                    p = fetch_price(tkr)
                    if np.isfinite(p):
                        portfolio_data["last_prices"][tkr] = p
                        updated += 1
                portfolio_data["last_updated"] = datetime.now().isoformat(timespec="seconds")
                save_portfolio()
                st.success(f"Refreshed {updated} tickers.")
            
            rows = []
            total_invested = 0.0
            total_value = 0.0
            total_div = 0.0
            for tkr, rec in sorted(portfolio_data["holdings"].items()):
                shares = float(rec.get("shares", 0))
                invested = float(rec.get("total_invested", 0))
                price = fetch_price(tkr) if portfolio_data["settings"].get("auto_price", True) else float('nan')
                if np.isnan(price): price = float(portfolio_data["last_prices"].get(tkr, np.nan))
                market_value = shares * price if np.isfinite(price) else np.nan
                divs = float(rec.get("dividends_collected", 0.0))
                total_val = (market_value + divs) if np.isfinite(market_value) else np.nan
                overall_return = (market_value - invested if np.isfinite(market_value) else 0.0) + divs
                ret_pct = (overall_return / invested * 100.0) if invested > 0 else np.nan
                payout = fetch_dividend_frequency(tkr)
                true_ada = ((invested - divs) / shares) if shares > 0 else np.nan

                rows.append({
                    "Ticker": tkr,
                    "Payout Freq": payout,
                    "Shares": round(shares, 6),
                    "Purchase Price": rec.get("purchase_price", np.nan),
                    "Total Invested": invested,
                    "Price Now": price if np.isfinite(price) else np.nan,
                    "Current Value": market_value if np.isfinite(market_value) else np.nan,
                    "Dividends Collected": divs,
                    "Total Value $": total_val,
                    "True ADA": true_ada,
                    "Overall Return $": overall_return if np.isfinite(overall_return) else np.nan,
                    "Overall Return %": ret_pct if np.isfinite(ret_pct) else np.nan
                })

                if np.isfinite(market_value): total_value += market_value
                total_invested += invested
                total_div += divs

            order = ["Ticker", "Payout Freq", "Shares", "Purchase Price", "Total Invested", "Price Now", "Current Value", "Dividends Collected", "Total Value $", "True ADA", "Overall Return $", "Overall Return %"]
            df = pd.DataFrame(rows)[order]

            money_cols = ["Purchase Price", "Total Invested", "Price Now", "Current Value", "Dividends Collected", "Total Value $", "True ADA", "Overall Return $"]
            pct_cols = ["Overall Return %"]

            def fmt_money(v): return "" if pd.isna(v) else f"${float(v):,.2f}"
            def fmt_pct(v): return "" if pd.isna(v) else f"{float(v):,.2f}%"
            def color_returns(v):
                try: x = float(v)
                except Exception: return ""
                if not np.isfinite(x): return ""
                if x > 0: return "color:#16a34a;"
                if x < 0: return "color:#dc2626;"
                return ""
            stripe_css = [{'selector': 'tbody tr:nth-child(odd)', 'props': 'background-color: rgba(0,0,0,0.03);'}]

            styler = (df.style
                      .format({**{c: fmt_money for c in money_cols}, **{c: fmt_pct for c in pct_cols}})
                      .map(color_returns, subset=["Overall Return $", "Overall Return %"])
                      .set_properties(subset=money_cols + pct_cols, **{"text-align": "right"})
                      .set_table_styles(stripe_css)
                      )

            try:
                st.dataframe(styler, use_container_width=True, height=620, hide_index=True)
            except TypeError:
                try:
                    st.dataframe(styler.hide(axis="index"), use_container_width=True, height=620)
                except Exception:
                    df_display = df.copy()
                    st.dataframe(df_display, use_container_width=True, height=620)

            st.markdown("<div style='margin-top: 20px;'></div>", unsafe_allow_html=True)
            overall_return = total_value + portfolio_data["cash_uninvested"] + total_div - total_invested
            overall_return_pct = (overall_return / total_invested * 100.0) if total_invested > 0 else np.nan
            return_color = "#16a34a" if overall_return > 0 else "#dc2626" if overall_return < 0 else "inherit"
            cols = st.columns(5)
            cols[0].metric("Total Invested", f"${total_invested:,.2f}")
            cols[1].metric("Current Value", f"${total_value:,.2f}" if np.isfinite(total_value) else "—")
            with cols[2]:
                st.metric("Cash Available", f"${portfolio_data['cash_uninvested']:,.2f}")
                new_cash_text = st.text_input("Update Cash Available", value=money_str(portfolio_data["cash_uninvested"]), key=f"port_cash_{st.session_state['selected_portfolio']}", placeholder="$0.00")
                new_cash = money_to_float(new_cash_text)
                if new_cash != portfolio_data["cash_uninvested"]:
                    portfolio_data["cash_uninvested"] = new_cash
                    portfolio_data["last_updated"] = datetime.now().isoformat(timespec="seconds")
                    save_portfolio()
                    st.rerun()
            cols[3].metric("Total Value", f"${total_value + portfolio_data['cash_uninvested'] + total_div:,.2f}" if np.isfinite(total_value) else "—")
            with cols[4]:
                st.markdown(f"<span style='color:{return_color}; font-size:1.1em;'>Overall Return</span>", unsafe_allow_html=True)
                st.markdown(f"<span style='color:{return_color}; font-size:1.5em;'>{money_str(overall_return)}</span>", unsafe_allow_html=True)
                st.markdown(f"<span style='color:{return_color}; font-size:1.2em;'>{overall_return_pct:.2f}%</span>" if np.isfinite(overall_return_pct) else "—", unsafe_allow_html=True)

    with tab_add:
        st.subheader(f"Add New Holding - {st.session_state['selected_portfolio']}", divider="gray")
        portfolio_data = st.session_state["DATA"]["portfolios"][st.session_state["selected_portfolio"]]
        
        # Initialize session state for form inputs
        if f"add_ticker_{st.session_state['selected_portfolio']}" not in st.session_state:
            st.session_state[f"add_ticker_{st.session_state['selected_portfolio']}"] = ""
        if f"add_shares_{st.session_state['selected_portfolio']}" not in st.session_state:
            st.session_state[f"add_shares_{st.session_state['selected_portfolio']}"] = ""
        if f"add_price_{st.session_state['selected_portfolio']}" not in st.session_state:
            st.session_state[f"add_price_{st.session_state['selected_portfolio']}"] = ""
        if f"add_divs_{st.session_state['selected_portfolio']}" not in st.session_state:
            st.session_state[f"add_divs_{st.session_state['selected_portfolio']}"] = ""
        if f"add_last_amt_{st.session_state['selected_portfolio']}" not in st.session_state:
            st.session_state[f"add_last_amt_{st.session_state['selected_portfolio']}"] = ""
        if f"add_last_date_{st.session_state['selected_portfolio']}" not in st.session_state:
            st.session_state[f"add_last_date_{st.session_state['selected_portfolio']}"] = None
        
        with st.form(key=f"add_form_{st.session_state['selected_portfolio']}"):
            ticker = st.text_input("Ticker Symbol", value=st.session_state[f"add_ticker_{st.session_state['selected_portfolio']}"], key=f"add_ticker_input_{st.session_state['selected_portfolio']}", placeholder="e.g., AAPL")
            shares_text = st.text_input("Shares Quantity", value=st.session_state[f"add_shares_{st.session_state['selected_portfolio']}"], key=f"add_shares_input_{st.session_state['selected_portfolio']}", placeholder="0.000000")
            price_text = st.text_input("$ Purchase Price per Share", value=st.session_state[f"add_price_{st.session_state['selected_portfolio']}"], key=f"add_price_input_{st.session_state['selected_portfolio']}", placeholder="$0.00")
            
            # Calculate total invested dynamically
            shares = shares_to_float(shares_text)
            price = money_to_float(price_text)
            calculated_total = shares * price if shares > 0 and price > 0 else 0.0
            
            # Store previous values to detect changes
            prev_shares = st.session_state.get(f"prev_add_shares_{st.session_state['selected_portfolio']}", "")
            prev_price = st.session_state.get(f"prev_add_price_{st.session_state['selected_portfolio']}", "")
            show_calc_message = False
            
            # Check if either shares or price changed
            if shares_text != prev_shares or price_text != prev_price:
                show_calc_message = calculated_total > 0
                st.session_state[f"prev_add_shares_{st.session_state['selected_portfolio']}"] = shares_text
                st.session_state[f"prev_add_price_{st.session_state['selected_portfolio']}"] = price_text
            
            total_text = st.text_input(
                "$ Total Invested",
                value=money_str(calculated_total) if calculated_total > 0 else "",
                key=f"add_invested_input_{st.session_state['selected_portfolio']}",
                placeholder="$0.00",
                help="Auto-calculated as Shares × Price (can be manually overridden)"
            )
            
            dividends = st.text_input("$ Dividends Collected (optional)", value=st.session_state[f"add_divs_{st.session_state['selected_portfolio']}"], key=f"add_divs_input_{st.session_state['selected_portfolio']}", placeholder="$0.00")
            last_div_amt = st.text_input("Last Dividend Amount (optional)", value=st.session_state[f"add_last_amt_{st.session_state['selected_portfolio']}"], key=f"add_last_amt_input_{st.session_state['selected_portfolio']}", placeholder="$0.00")
            last_div_date = st.date_input("Last Dividend Date (optional)", value=st.session_state[f"add_last_date_{st.session_state['selected_portfolio']}"], key=f"add_last_date_input_{st.session_state['selected_portfolio']}")
            
            if show_calc_message:
                st.info(f"💡 Auto-calculated: {shares:.6f} shares × ${price:.2f} = **${calculated_total:,.2f}**")
            
            submitted = st.form_submit_button("➕ Add Holding")
        
        # Update session state
        st.session_state[f"add_ticker_{st.session_state['selected_portfolio']}"] = ticker
        st.session_state[f"add_shares_{st.session_state['selected_portfolio']}"] = shares_text
        st.session_state[f"add_price_{st.session_state['selected_portfolio']}"] = price_text
        st.session_state[f"add_divs_{st.session_state['selected_portfolio']}"] = dividends
        st.session_state[f"add_last_amt_{st.session_state['selected_portfolio']}"] = last_div_amt
        st.session_state[f"add_last_date_{st.session_state['selected_portfolio']}"] = last_div_date
        
        if submitted:
            tkr = ticker.strip().upper()
            if not tkr:
                st.error("Ticker required.")
            elif tkr in portfolio_data["holdings"]:
                st.error(f"{tkr} already exists in {st.session_state['selected_portfolio']}. Use Edit tab to modify.")
            else:
                sh = shares_to_float(shares_text)
                pp = money_to_float(price_text)
                inv = money_to_float(total_text)
                div = money_to_float(dividends)
                lda = money_to_float(last_div_amt)
                ldd = last_div_date.isoformat() if last_div_date else ""
                
                if sh <= 0:
                    st.error("Shares must be positive.")
                else:
                    calc_invested = inv if inv > 0 else calculated_total
                    if calc_invested == 0 and portfolio_data["settings"].get("auto_price", True):
                        curr_price = fetch_price(tkr)
                        if np.isfinite(curr_price):
                            calc_invested = sh * curr_price
                    name, summary = fetch_name_and_summary(tkr)
                    rec = {
                        "name": name,
                        "shares": float(sh),
                        "purchase_price": float(pp) if pp > 0 else None,
                        "total_invested": float(calc_invested),
                        "dividends_collected": float(div),
                        "last_div_amount": float(lda),
                        "last_div_date": ldd,
                        "summary": summary,
                    }
                    portfolio_data["holdings"][tkr] = rec
                    if np.isfinite(pp) and pp > 0:
                        portfolio_data["last_prices"][tkr] = pp
                    portfolio_data["last_updated"] = datetime.now().isoformat(timespec="seconds")
                    save_portfolio()
                    st.success(f"Added {tkr} with {sh:.6f} shares to {st.session_state['selected_portfolio']}.")
                    st.session_state[f"add_ticker_{st.session_state['selected_portfolio']}"] = ""
                    st.session_state[f"add_shares_{st.session_state['selected_portfolio']}"] = ""
                    st.session_state[f"add_price_{st.session_state['selected_portfolio']}"] = ""
                    st.session_state[f"add_divs_{st.session_state['selected_portfolio']}"] = ""
                    st.session_state[f"add_last_amt_{st.session_state['selected_portfolio']}"] = ""
                    st.session_state[f"add_last_date_{st.session_state['selected_portfolio']}"] = None
                    st.session_state.pop(f"prev_add_shares_{st.session_state['selected_portfolio']}", None)
                    st.session_state.pop(f"prev_add_price_{st.session_state['selected_portfolio']}", None)
                    st.rerun()

    with tab_edit:
        st.subheader(f"Edit or Delete Holding - {st.session_state['selected_portfolio']}", divider="gray")
        portfolio_data = st.session_state["DATA"]["portfolios"][st.session_state["selected_portfolio"]]
        if not portfolio_data["holdings"]:
            st.info(f"Add a holding first to {st.session_state['selected_portfolio']}.")
        else:
            sel = st.selectbox("Select Ticker", options=sorted(list(portfolio_data["holdings"].keys())), key=f"edit_select_{st.session_state['selected_portfolio']}")
            if sel:
                rec = portfolio_data["holdings"][sel]
                with st.form(key=f"edit_form_{sel}_{st.session_state['selected_portfolio']}"):
                    col1, col2 = st.columns(2)
                    shares_text = st.text_input("Shares", value=f"{rec.get('shares', 0):.6f}", key=f"edit_shares_text_{sel}_{st.session_state['selected_portfolio']}")
                    purchase_price_text = st.text_input("Purchase Price per Share (optional)", value=money_str(rec.get("purchase_price", 0.0)), key=f"edit_price_text_{sel}_{st.session_state['selected_portfolio']}", placeholder="$0.00")
                    total_invested_text = st.text_input("Total Invested (optional, overrides shares * price)", value=money_str(rec.get("total_invested", 0.0)), key=f"edit_invested_text_{sel}_{st.session_state['selected_portfolio']}", placeholder="$0.00")
                    dividends_text = st.text_input("Dividends Collected", value=money_str(rec.get("dividends_collected", 0.0)), key=f"edit_divs_text_{sel}_{st.session_state['selected_portfolio']}", placeholder="$0.00")
                    last_div_amt_text = st.text_input("Last Dividend Amount", value=money_str(rec.get("last_div_amount", 0.0)), key=f"edit_last_amt_text_{sel}_{st.session_state['selected_portfolio']}", placeholder="$0.00")
                    last_div_date = col1.date_input("Last Dividend Date", value=date.fromisoformat(rec.get("last_div_date")) if rec.get("last_div_date") else None, key=f"edit_last_date_{sel}_{st.session_state['selected_portfolio']}")
                    submitted = st.form_submit_button("💾 Save Changes")
                
                if submitted:
                    shares = shares_to_float(shares_text)
                    purchase_price = money_to_float(purchase_price_text)
                    total_invested = money_to_float(total_invested_text)
                    dividends = money_to_float(dividends_text)
                    last_div_amt = money_to_float(last_div_amt_text)
                    calc_invested = total_invested if total_invested > 0 else (shares * purchase_price if purchase_price > 0 else rec.get("total_invested", 0.0))
                    if calc_invested == 0 and portfolio_data["settings"].get("auto_price", True):
                        curr_price = fetch_price(sel)
                        if np.isfinite(curr_price):
                            calc_invested = shares * curr_price
                    _, summary = fetch_name_and_summary(sel)
                    rec = {
                        "name": rec.get("name", sel),
                        "shares": float(shares),
                        "purchase_price": float(purchase_price) if purchase_price > 0 else None,
                        "total_invested": float(calc_invested),
                        "dividends_collected": float(dividends),
                        "last_div_amount": float(last_div_amt),
                        "last_div_date": last_div_date.isoformat() if last_div_date else "",
                        "summary": summary,
                    }
                    portfolio_data["holdings"][sel] = rec
                    if np.isfinite(purchase_price) and purchase_price > 0:
                        portfolio_data["last_prices"][sel] = purchase_price
                    portfolio_data["last_updated"] = datetime.now().isoformat(timespec="seconds")
                    save_portfolio()
                    st.success(f"Updated {sel} in {st.session_state['selected_portfolio']}")
                    st.rerun()

                st.markdown("---")
                st.subheader("Danger zone", divider="gray")
                st.warning(f"Delete **{sel}** permanently from {st.session_state['selected_portfolio']}. This cannot be undone.", icon="⚠️")
                with st.form(key=f"delete_form_{sel}_{st.session_state['selected_portfolio']}"):
                    st.write("Type the ticker to confirm deletion:")
                    confirm = st.text_input("", key=f"delete_confirm_{sel}_{st.session_state['selected_portfolio']}", placeholder=sel)
                    confirm_cb = st.checkbox("I understand this action is permanent.", key=f"delete_confirm_cb_{sel}_{st.session_state['selected_portfolio']}")
                    delete_submitted = st.form_submit_button(f"🗑️ Delete {sel}")
                if delete_submitted:
                    if (confirm.strip().upper() == sel.strip().upper()) and confirm_cb:
                        if sel in portfolio_data["holdings"]:
                            portfolio_data["holdings"].pop(sel, None)
                            portfolio_data["last_updated"] = datetime.now().isoformat(timespec="seconds")
                            save_portfolio()
                            st.success(f"Deleted {sel} from {st.session_state['selected_portfolio']}.")
                            st.rerun()
                    else:
                        st.error("Confirmation failed. Please type the ticker exactly and check the box.")

    with tab_div:
        st.subheader(f"Quick Dividend Entry - {st.session_state['selected_portfolio']}", divider="gray")
        portfolio_data = st.session_state["DATA"]["portfolios"][st.session_state["selected_portfolio"]]
        if not portfolio_data["holdings"]:
            st.info(f"Add a holding first to {st.session_state['selected_portfolio']}.")
        else:
            tickers = sorted(list(portfolio_data["holdings"].keys()))
            col1, col2, col3, col4 = st.columns([1, 1, 1, 1])
            sel = col1.selectbox("Ticker", options=tickers, key=f"div_select_{st.session_state['selected_portfolio']}")
            dflt_date = date.today()
            dt = col2.date_input("Dividend date", value=dflt_date, key=f"div_date_{sel}_{st.session_state['selected_portfolio']}")
            amt = col3.text_input("Dividend amount to add", value="$0.00", key=f"div_amt_{sel}_{st.session_state['selected_portfolio']}")
            def _money_to_float(s):
                s = str(s).strip().replace(',', '').replace('$', '')
                try: return float(s) if s else 0.0
                except: return 0.0
            if col4.button("Add dividend"):
                add_val = _money_to_float(amt)
                portfolio_data["holdings"][sel]["dividends_collected"] = float(portfolio_data["holdings"][sel].get("dividends_collected", 0.0)) + add_val
                portfolio_data["holdings"][sel]["last_div_amount"] = add_val
                try:
                    portfolio_data["holdings"][sel]["last_div_date"] = dt.isoformat()
                except Exception:
                    portfolio_data["holdings"][sel]["last_div_date"] = str(dt)
                portfolio_data["last_updated"] = datetime.now().isoformat(timespec="seconds")
                save_portfolio()
                st.success(f"Added {money_str(add_val)} dividend to {sel} for {dt} in {st.session_state['selected_portfolio']}.")
                st.rerun()

            rows = []
            total = 0.0
            for tkr, rec in sorted(portfolio_data["holdings"].items()):
                d = float(rec.get("dividends_collected", 0.0))
                last_amt = float(rec.get("last_div_amount", 0.0))
                last_dt = rec.get("last_div_date", "")
                rows.append({"Ticker": tkr,
                             "Dividends Collected": d,
                             "Last Dividend $": last_amt,
                             "Last Dividend Date": last_dt})
                total += d
            df_div = pd.DataFrame(rows).reset_index(drop=True)
            df_div["Dividends Collected"] = df_div["Dividends Collected"].apply(lambda v: f"${float(v):,.2f}")
            df_div["Last Dividend $"] = df_div["Last Dividend $"].apply(lambda v: f"${float(v):,.2f}" if v else "")
            try:
                st.dataframe(df_div.style.set_table_styles([{'selector': 'tbody tr:nth-child(odd)', 'props': 'background-color: rgba(0,0,0,0.03);'}]), use_container_width=True, height=360, hide_index=True)
            except TypeError:
                try:
                    st.dataframe(df_div.style.hide(axis="index").set_table_styles([{'selector': 'tbody tr:nth-child(odd)', 'props': 'background-color: rgba(0,0,0,0.03);'}]), use_container_width=True, height=360)
                except Exception:
                    st.dataframe(df_div, use_container_width=True, height=360)
            st.metric("Total Dividends Collected", money_str(total))

    with tab_trueada:
        st.subheader(f"True Adjusted Dividend Average (True ADA) - {st.session_state['selected_portfolio']}", divider="gray")
        portfolio_data = st.session_state["DATA"]["portfolios"][st.session_state["selected_portfolio"]]
        if not portfolio_data["holdings"]:
            st.info(f"Add a holding first to calculate True ADA in {st.session_state['selected_portfolio']}.")
        else:
            rows = []
            sum_shares = 0.0
            sum_invested = 0.0
            sum_div = 0.0
            total_value = 0.0
            for tkr, rec in sorted(portfolio_data["holdings"].items()):
                shares = float(rec.get("shares", 0.0))
                invested = float(rec.get("total_invested", 0.0))
                divs = float(rec.get("dividends_collected", 0.0))
                true_ada = (invested - divs) / shares if shares > 0 else np.nan
                price = fetch_price(tkr) if portfolio_data["settings"].get("auto_price", True) else float('nan')
                if np.isnan(price): price = float(portfolio_data["last_prices"].get(tkr, np.nan))
                market_value = shares * price if np.isfinite(price) else np.nan
                vs_true_pct = ((price - true_ada) / true_ada * 100.0) if (shares > 0 and np.isfinite(price) and np.isfinite(true_ada) and true_ada != 0) else np.nan
                rows.append({
                    "Ticker": tkr,
                    "Shares": round(shares, 6),
                    "Total Invested": invested,
                    "Dividends Collected": divs,
                    "True ADA": true_ada,
                    "Current Price": price if np.isfinite(price) else np.nan,
                    "Return vs True ADA %": vs_true_pct
                })
                sum_shares += shares
                sum_invested += invested
                sum_div += divs
                if np.isfinite(market_value): total_value += market_value

            df = pd.DataFrame(rows)
            df_display = df.copy()
            for c in ["Total Invested", "Dividends Collected", "True ADA", "Current Price"]:
                df_display[c] = df_display[c].apply(lambda v: "" if pd.isna(v) else f"${float(v):,.2f}")
            def fmt_pct(v): return "" if pd.isna(v) else f"{float(v):,.2f}%"
            df_display["Return vs True ADA %"] = df_display["Return vs True ADA %"].apply(fmt_pct)

            def color_pct(v):
                try: x = float(str(v).replace('%', ''))
                except: return ""
                if not np.isfinite(x): return ""
                if x > 0: return "color:#16a34a;"
                if x < 0: return "color:#dc2626;"
                return ""

            styler = (df_display.style
                      .map(color_pct, subset=["Return vs True ADA %"])
                      .set_properties(subset=["Total Invested", "Dividends Collected", "True ADA", "Current Price", "Return vs True ADA %"], **{"text-align": "right"})
                      .set_table_styles([{'selector': 'tbody tr:nth-child(odd)', 'props': 'background-color: rgba(0,0,0,0.03);'}])
                      )

            try:
                st.dataframe(styler, use_container_width=True, height=520, hide_index=True)
            except TypeError:
                try:
                    st.dataframe(styler.hide(axis="index"), use_container_width=True, height=520)
                except Exception:
                    st.dataframe(df_display, use_container_width=True, height=520)

            if sum_shares > 0:
                avg_cost_portfolio = (sum_invested / sum_shares)
                true_ada_portfolio = ((sum_invested - sum_div) / sum_shares)
                improvement_pct = ((avg_cost_portfolio - true_ada_portfolio) / avg_cost_portfolio * 100.0) if avg_cost_portfolio > 0 else np.nan
            else:
                avg_cost_portfolio = np.nan
                true_ada_portfolio = np.nan
                improvement_pct = np.nan

            c1, c2, c3, c4, c5 = st.columns(5)
            c1.metric("Total Dividends Collected", f"${sum_div:,.2f}")
            c2.metric("Total Value", money_str(total_value + portfolio_data["cash_uninvested"]) if np.isfinite(total_value) else "—")
            c3.metric("Unadjusted Avg Cost (Portfolio)", f"${avg_cost_portfolio:,.2f}" if np.isfinite(avg_cost_portfolio) else "—")
            c4.metric("True ADA (Portfolio)", f"${true_ada_portfolio:,.2f}" if np.isfinite(true_ada_portfolio) else "—")
            c5.metric("Adjusted Basis Improvement", f"{improvement_pct:.2f}%" if np.isfinite(improvement_pct) else "—")

    with tab_migrate:
        st.subheader(f"Migrate from older version - {st.session_state['selected_portfolio']}", divider="gray")
        st.caption(f"Import/merge a previous `portfolio_data.json` into {st.session_state['selected_portfolio']} without losing your data.")
        upl = st.file_uploader("Choose previous JSON file", type=["json"], key=f"migrate_uploader_{st.session_state['selected_portfolio']}")
        merge_mode = st.radio("Merge strategy", ["Add new tickers only", "Overwrite existing tickers with incoming data"], key=f"merge_mode_{st.session_state['selected_portfolio']}")
        if upl is not None and st.button("Merge now"):
            try:
                incoming = json.load(upl)
                portfolio_data = st.session_state["DATA"]["portfolios"][st.session_state["selected_portfolio"]]
                inc_holdings = incoming.get("holdings", {})
                added = 0
                updated = 0
                for tkr, rec in inc_holdings.items():
                    rec.setdefault("last_div_amount", 0.0)
                    rec.setdefault("last_div_date", "")
                    rec.setdefault("purchase_price", None)
                    rec.setdefault("dividends_collected", 0.0)
                    rec.setdefault("summary", "")
                    if tkr not in portfolio_data["holdings"]:
                        portfolio_data["holdings"][tkr] = rec
                        added += 1
                    else:
                        if merge_mode.startswith("Overwrite"):
                            portfolio_data["holdings"][tkr] = rec
                            updated += 1
                portfolio_data["last_updated"] = datetime.now().isoformat(timespec="seconds")
                save_portfolio()
                st.success(f"Merged successfully into {st.session_state['selected_portfolio']}. Added: {added}, Updated: {updated}.")
                st.rerun()
            except Exception as e:
                st.error(f"Failed to merge: {e}")

    with tab_backup:
        st.subheader(f"Backup & Restore - {st.session_state['selected_portfolio']}", divider="gray")
        portfolio_data = st.session_state["DATA"]["portfolios"][st.session_state["selected_portfolio"]]
        new_cash_text = st.text_input("Cash Available", value=money_str(portfolio_data["cash_uninvested"]), key=f"backup_cash_text_{st.session_state['selected_portfolio']}", placeholder="$0.00")
        new_cash = money_to_float(new_cash_text)
        if new_cash != portfolio_data["cash_uninvested"]:
            portfolio_data["cash_uninvested"] = new_cash
            portfolio_data["last_updated"] = datetime.now().isoformat(timespec="seconds")
            save_portfolio()
            st.rerun()
        data_json = json.dumps(st.session_state["DATA"], indent=2)
        st.download_button("⬇️ Download backup (JSON)", data=data_json, file_name=f"portfolio_{st.session_state['user_id']}_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json", mime="application/json")
        st.download_button("⬇️ Download tracker_app.py", data=open(__file__, "r").read(), file_name="tracker_app.py", mime="text/python")
        upl = st.file_uploader("Restore from JSON backup", type=["json"], key=f"restore_uploader_{st.session_state['selected_portfolio']}")
        if upl is not None and st.button("Restore now"):
            try:
                incoming = json.load(upl)
                incoming.setdefault("portfolios", {
                    "IRA": {
                        "holdings": {},
                        "cash_uninvested": 0.0,
                        "settings": {"currency": "USD", "auto_price": True},
                        "last_prices": {},
                        "last_updated": None
                    },
                    "Roth": {
                        "holdings": {},
                        "cash_uninvested": 0.0,
                        "settings": {"currency": "USD", "auto_price": True},
                        "last_prices": {},
                        "last_updated": None
                    }
                })
                incoming["version"] = "1.9.5"
                for portfolio in incoming["portfolios"].values():
                    portfolio.setdefault("holdings", {})
                    portfolio.setdefault("cash_uninvested", 0.0)
                    portfolio.setdefault("settings", {"currency": "USD", "auto_price": True})
                    portfolio.setdefault("last_prices", {})
                    portfolio.setdefault("last_updated", None)
                    for rec in portfolio.get("holdings", {}).values():
                        rec.setdefault("purchase_price", None)
                        rec.setdefault("dividends_collected", 0.0)
                        rec.setdefault("last_div_amount", 0.0)
                        rec.setdefault("last_div_date", "")
                        rec.setdefault("summary", "")
                st.session_state["DATA"] = incoming
                st.session_state["DATA"]["last_updated"] = datetime.now().isoformat(timespec="seconds")
                save_portfolio()
                st.success(f"Backup restored for all portfolios.")
                st.rerun()
            except Exception as e:
                st.error(f"Failed to restore: {e}")