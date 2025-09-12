# MKK Investment Tracker — v1.8.9
# - Portfolio: color-coded Overall Return $ & %, subtle row striping, right-aligned numbers
# - Top metrics: colored Overall Return "card" (green/red)
# - True ADA: color-coded Return vs True ADA %, striping
# - Keeps delete holding, dividend last amount/date, migration, backup
# - Updated to use session_state for data storage, with manual backup/restore for persistence
# - Fixed TypeError by adding placeholder parameter to money_input and shares_input
# - Fixed issue where new holdings don't appear in Portfolio tab by adding st.rerun()
# - Added automatic price fetching for total_invested when purchase_price is not provided and auto_price is enabled
# - Restored Portfolio banner with Total Invested Value, Current Value, Cash Available (with input), Total Value, Overall Return ($ and %)
# - Restored total_invested calculation as shares * purchase_price when purchase_price is provided
# - Restored cash_uninvested input in Backup tab
# - Updated Portfolio banner to color Overall Return label and $ amount green/red, with % below $ amount and also colored
# - Increased font size of Overall Return label, $, and % to match other metrics for uniform style
# - Added Refresh Prices button to Portfolio tab to address TSLA price fetch issues
# - Added dynamic Total Invested $ calculation in Add Holding tab based on Shares * Purchase Price
# - Added Total Value $ metric in True ADA tab after Dividends Collected
# - Removed Name column from True ADA tab table
# - Removed Name column from Portfolio tab table
# - Added Total Value $ column to Portfolio tab table after Dividends Collected
# - Added Firebase Realtime Database for cloud sync with User ID
# - Polished look

import json, os, re, shutil, sys
from datetime import datetime, date
from typing import Dict, Any
import streamlit as st, yfinance as yf, pandas as pd, numpy as np
import firebase_admin
from firebase_admin import credentials, db

# Firebase Initialization - Runs once
if not firebase_admin._apps:
    try:
        # Load your secret key
        with open('firebase_key.json', 'r') as f:
            cred = credentials.Certificate(json.load(f))
        # Initialize with your Database URL
        firebase_admin.initialize_app(cred, {
            'databaseURL': 'https://mkk-investment-tracker-default-rtdb.firebaseio.com/'
        })
        print("Firebase connected!")  # Debug - shows in terminal
    except Exception as e:
        st.error(f"Firebase connection failed: {e}. App will run locally.")
        print(f"Firebase error: {e}")  # Debug

# User ID for cloud sync (remembers for session)
if "user_id" not in st.session_state:
    st.session_state.user_id = st.text_input(
        "Enter a unique User ID (e.g., 'myportfolio' or your email) to sync across devices:",
        placeholder="Type here to start syncing"
    )
    if st.session_state.user_id.strip():
        st.info(f"Syncing as: {st.session_state.user_id}")
    else:
        st.stop()  # Wait for input

# Load portfolio from Firebase
def load_portfolio():
    if "DATA" not in st.session_state:
        try:
            ref = db.reference(f'portfolios/{st.session_state.user_id}')
            snapshot = ref.get()
            if snapshot:
                # Migrate old data if needed
                snapshot.setdefault("settings", {"currency": "USD", "auto_price": True})
                snapshot.setdefault("last_prices", {})
                snapshot.setdefault("last_updated", None)
                snapshot["version"] = "1.8.9"
                for rec in snapshot.get("holdings", {}).values():
                    rec.setdefault("purchase_price", None)
                    rec.setdefault("dividends_collected", 0.0)
                    rec.setdefault("last_div_amount", 0.0)
                    rec.setdefault("last_div_date", "")
                    rec.setdefault("summary", "")
                st.session_state["DATA"] = snapshot
                st.success("Portfolio loaded from cloud!")
            else:
                # New portfolio
                st.session_state["DATA"] = {
                    "holdings": {},
                    "cash_uninvested": 0.0,
                    "settings": {"currency": "USD", "auto_price": True},
                    "last_prices": {},
                    "last_updated": None,
                    "version": "1.8.9"
                }
                st.info("New portfolio created in cloud.")
        except Exception as e:
            st.error(f"Cloud load failed: {e}. Using local default.")
            # Fallback to local
            st.session_state["DATA"] = {
                "holdings": {},
                "cash_uninvested": 0.0,
                "settings": {"currency": "USD", "auto_price": True},
                "last_prices": {},
                "last_updated": None,
                "version": "1.8.9"
            }
load_portfolio()

# Save portfolio to Firebase
def save_portfolio():
    try:
        ref = db.reference(f'portfolios/{st.session_state.user_id}')
        ref.set(st.session_state["DATA"])
        st.session_state["DATA"]["last_updated"] = datetime.now().isoformat(timespec="seconds")
        # st.success("Saved to cloud!")  # Uncomment for feedback
    except Exception as e:
        st.error(f"Cloud save failed: {e}. Data saved locally.")

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
    </style>
""", unsafe_allow_html=True)

st.warning("Note: Your portfolio data is stored in the cloud with your User ID. Use the same ID to access it from any device. Manual backups are still available in the 'Backup' tab.", icon="ℹ️")

def money_to_float(text: str) -> float:
    if text is None: return 0.0
    s = str(text).strip().replace(',', '').replace('$', '')
    try: return float(s) if s else 0.0
    except: return 0.0

def money_str(x: float) -> str:
    if x is None or not np.isfinite(x): return ""
    return f"${x:,.2f}"

def money_input(label: str, key: str, value: float = 0.0, help: str = "", placeholder: str = "$0.00") -> float:
    st.write(label)
    default = money_str(value)
    txt = st.text_input(label="", value=default, key=key, help=help, label_visibility="collapsed", placeholder=placeholder)
    return money_to_float(txt)

def shares_to_float(text: str) -> float:
    if text is None: return 0.0
    s = str(text).strip().replace(',', ' ').replace('\u00a0', ' ').strip()
    s = re.sub(r'\s+', '', s)
    try: return float(s) if s else 0.0
    except: return 0.0

def shares_input(label: str, key: str, value: float = 0.0, help: str = "", placeholder: str = "0.000000") -> float:
    st.write(label)
    txt = st.text_input(label="", value=f"{value:.6f}" if value else "", key=key, help=help,
                        label_visibility="collapsed", placeholder=placeholder)
    return shares_to_float(txt)

@st.cache_data(show_spinner=False)
def fetch_price(ticker: str) -> float:
    try:
        t = yf.Ticker(ticker)
        hist = t.history(period="5d", interval="1d")
        if hist is None or hist.empty: return float("nan")
        return float(hist["Close"].dropna().iloc[-1])
    except Exception: return float("nan")

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

st.title("MKK Investment Tracker")
tab_port, tab_add, tab_edit, tab_div, tab_trueada, tab_migrate, tab_backup, tab_settings = st.tabs([
    "Portfolio", "Add Holding", "Edit Holdings", "Dividends", "True ADA", "Migration", "Backup", "Settings"
])

with tab_settings:
    st.subheader("Settings", divider="gray")
    st.session_state["DATA"]["settings"]["currency"] = st.selectbox(
        "Currency (display only)",
        ["USD", "EUR", "GBP", "JPY", "CAD"],
        index=["USD", "EUR", "GBP", "JPY", "CAD"].index(st.session_state["DATA"]["settings"].get("currency", "USD"))
    )
    st.session_state["DATA"]["settings"]["auto_price"] = st.checkbox(
        "Auto-update prices from the internet",
        value=st.session_state["DATA"]["settings"].get("auto_price", True)
    )
    if st.button("🔄 Update all prices now"):
        updated = 0
        for tkr, rec in st.session_state["DATA"]["holdings"].items():
            p = fetch_price(tkr)
            if np.isfinite(p):
                st.session_state["DATA"]["last_prices"][tkr] = p
                updated += 1
        st.session_state["DATA"]["last_updated"] = datetime.now().isoformat(timespec="seconds")
        st.success(f"Updated {updated} tickers.")
        save_portfolio()

# ---------------------- Portfolio ----------------------
with tab_port:
    if not st.session_state["DATA"]["holdings"]:
        st.info("No holdings yet. Add your first position in **Add Holding**.")
    else:
        if st.button("🔄 Refresh Prices"):
            updated = 0
            for tkr, rec in st.session_state["DATA"]["holdings"].items():
                p = fetch_price(tkr)
                if np.isfinite(p):
                    st.session_state["DATA"]["last_prices"][tkr] = p
                    updated += 1
            st.session_state["DATA"]["last_updated"] = datetime.now().isoformat(timespec="seconds")
            st.success(f"Refreshed {updated} tickers.")
            save_portfolio()
        
        rows = []
        total_invested = 0.0
        total_value = 0.0
        total_div = 0.0
        for tkr, rec in sorted(st.session_state["DATA"]["holdings"].items()):
            shares = float(rec.get("shares", 0))
            invested = float(rec.get("total_invested", 0))
            price = fetch_price(tkr) if st.session_state["DATA"]["settings"].get("auto_price", True) else float('nan')
            if np.isnan(price): price = float(st.session_state["DATA"]["last_prices"].get(tkr, np.nan))
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

        # Format + color + subtle striping
        money_cols = ["Purchase Price", "Total Invested", "Price Now", "Current Value", "Dividends Collected", "Total Value $", "True ADA", "Overall Return $"]
        pct_cols = ["Overall Return %"]

        def fmt_money(v): return "" if pd.isna(v) else f"${float(v):,.2f}"
        def fmt_pct(v): return "" if pd.isna(v) else f"{float(v):,.2f}%"
        def color_returns(v):
            try: x = float(v)
            except Exception: return ""
            if not np.isfinite(x): return ""
            if x > 0: return "color:#16a34a;"  # green-600
            if x < 0: return "color:#dc2626;"  # red-600
            return ""
        stripe_css = [{'selector': 'tbody tr:nth-child(odd)', 'props': 'background-color: rgba(0,0,0,0.03);'}]

        styler = (df.style
                  .format({**{c: fmt_money for c in money_cols}, **{c: fmt_pct for c in pct_cols}})
                  .map(color_returns, subset=["Overall Return $", "Overall Return %"])
                  .set_properties(subset=money_cols + pct_cols, **{"text-align": "right"})
                  .set_table_styles(stripe_css)
                  )

        # Show without index/number column
        try:
            st.dataframe(styler, use_container_width=True, height=620, hide_index=True)
        except TypeError:
            try:
                st.dataframe(styler.hide(axis="index"), use_container_width=True, height=620)
            except Exception:
                df_display = df.copy()
                st.dataframe(df_display, use_container_width=True, height=620)

        st.markdown("<div style='margin-top: 20px;'></div>", unsafe_allow_html=True)  # Spacing before banner
        # Portfolio banner with metrics
        overall_return = total_value + st.session_state["DATA"]["cash_uninvested"] + total_div - total_invested
        overall_return_pct = (overall_return / total_invested * 100.0) if total_invested > 0 else np.nan
        return_color = "#16a34a" if overall_return > 0 else "#dc2626" if overall_return < 0 else "inherit"
        cols = st.columns(5)
        cols[0].metric("Total Invested Value", money_str(total_invested))
        cols[1].metric("Current Value", money_str(total_value) if np.isfinite(total_value) else "—")
        with cols[2]:
            st.metric("Cash Available", money_str(st.session_state["DATA"]["cash_uninvested"]))
            new_cash = money_input("Update Cash Available", key="update_cash", value=st.session_state["DATA"]["cash_uninvested"])
            if new_cash != st.session_state["DATA"]["cash_uninvested"]:
                st.session_state["DATA"]["cash_uninvested"] = new_cash
                st.session_state["DATA"]["last_updated"] = datetime.now().isoformat(timespec="seconds")
                save_portfolio()
                st.rerun()
        cols[3].metric("Total Value", money_str(total_value + st.session_state["DATA"]["cash_uninvested"]) if np.isfinite(total_value) else "—")
        with cols[4]:
            st.markdown(
                f"<div style='color:{return_color}; font-size:18px;'>Overall Return</div>"
                f"<div style='color:{return_color}; font-size:32px;'>{money_str(overall_return) if np.isfinite(overall_return) else '—'}</div>"
                f"<div style='color:{return_color}; font-size:18px;'>{fmt_pct(overall_return_pct) if np.isfinite(overall_return_pct) else '—'}</div>",
                unsafe_allow_html=True
            )

# ---------------------- Add Holding ----------------------
with tab_add:
    st.subheader("Add New Holding", divider="gray")
    ticker = st.text_input("Ticker (e.g., AAPL)", key="add_ticker").strip().upper()
    if ticker:
        name, summary = fetch_name_and_summary(ticker)
        st.write(f"**{name}**")
        if summary: st.caption(summary)
    shares = shares_input("Shares", key="add_shares", placeholder="0.000000")
    purchase_price = money_input("Purchase Price per Share (optional)", key="add_purchase_price", placeholder="$0.00")
    
    # Dynamically calculate total_invested based on shares * purchase_price
    calc_invested = shares * purchase_price if shares > 0 and purchase_price > 0 else 0.0
    total_invested = money_input(
        "Total Invested $ (required if shares >0 and no purchase price)",
        key="add_total_invested",
        value=calc_invested,
        placeholder="$0.00"
    )
    dividends = money_input("Dividends Collected $ (optional)", key="add_dividends", placeholder="$0.00")
    
    if st.button("➕ Add Holding"):
        if not ticker:
            st.error("Enter a ticker.")
        elif ticker in st.session_state["DATA"]["holdings"]:
            st.error(f"{ticker} already exists. Edit it in Edit Holdings.")
        elif shares <= 0 and total_invested > 0:
            st.error("Cannot have invested without shares.")
        else:
            # Calculate total_invested for saving
            if purchase_price > 0:
                calc_invested = shares * purchase_price
            elif st.session_state["DATA"]["settings"].get("auto_price", True):
                purchase_price = fetch_price(ticker)
                calc_invested = shares * purchase_price if np.isfinite(purchase_price) and purchase_price > 0 else total_invested
            else:
                calc_invested = total_invested
            rec = {
                "name": name,
                "shares": float(shares),
                "purchase_price": float(purchase_price) if purchase_price > 0 else None,
                "total_invested": float(calc_invested),
                "dividends_collected": float(dividends),
                "summary": summary,
                "last_div_amount": 0.0,
                "last_div_date": ""
            }
            st.session_state["DATA"]["holdings"][ticker] = rec
            if np.isfinite(purchase_price) and purchase_price > 0:
                st.session_state["DATA"]["last_prices"][ticker] = purchase_price
            st.session_state["DATA"]["last_updated"] = datetime.now().isoformat(timespec="seconds")
            st.success(f"Added {ticker}")
            save_portfolio()
            st.rerun()

# ---------------------- Edit Holdings ----------------------
with tab_edit:
    st.subheader("Edit Holdings", divider="gray")
    if not st.session_state["DATA"]["holdings"]:
        st.info("Add a holding first.")
    else:
        sel = st.selectbox("Select holding to edit", options=sorted(st.session_state["DATA"]["holdings"].keys()))
        if sel:
            rec = st.session_state["DATA"]["holdings"][sel]
            name = rec.get("name", "")
            summary = rec.get("summary", "")
            st.write(f"**{name}**")
            if summary: st.caption(summary)

            shares_key = f"edit_shares_{sel}"
            shares = shares_input("Shares", key=shares_key, value=rec.get("shares", 0.0))

            purchase_price_key = f"edit_purchase_price_{sel}"
            purchase_price = money_input("Purchase Price per Share (optional)", key=purchase_price_key, value=rec.get("purchase_price", 0.0))

            inv_key = f"edit_total_invested_{sel}"
            calc_invested = shares * purchase_price if purchase_price > 0 else rec.get("total_invested", 0.0)
            total_invested = money_input("Total Invested $ (required if shares >0 and no purchase price)", key=inv_key, value=calc_invested)

            div_key = f"edit_dividends_{sel}"
            dividends = money_input("Dividends Collected $ (optional)", key=div_key, value=rec.get("dividends_collected", 0.0))

            if st.button(f"💾 Update {sel}"):
                if shares <= 0 and total_invested > 0:
                    st.error("Cannot have invested without shares.")
                else:
                    # Calculate total_invested
                    if purchase_price > 0:
                        calc_invested = shares * purchase_price
                    elif st.session_state["DATA"]["settings"].get("auto_price", True):
                        purchase_price = fetch_price(sel)
                        calc_invested = shares * purchase_price if np.isfinite(purchase_price) and purchase_price > 0 else total_invested
                    else:
                        calc_invested = total_invested
                    rec = {
                        "name": name,
                        "shares": float(shares),
                        "purchase_price": float(purchase_price) if purchase_price > 0 else None,
                        "total_invested": float(calc_invested),
                        "dividends_collected": float(dividends),
                        "summary": summary,
                    }
                    st.session_state["DATA"]["holdings"][sel] = rec
                    if np.isfinite(purchase_price) and purchase_price > 0:
                        st.session_state["DATA"]["last_prices"][sel] = purchase_price
                    st.session_state["DATA"]["last_updated"] = datetime.now().isoformat(timespec="seconds")
                    st.success(f"Updated {sel}")
                    save_portfolio()
                    st.rerun()

            st.markdown("---")
            st.subheader("Danger zone", divider="gray")
            st.warning(f"Delete **{sel}** permanently from your portfolio. This cannot be undone.", icon="⚠️")
            with st.form(key=f"delete_form_{sel}"):
                st.write("Type the ticker to confirm deletion:")
                confirm = st.text_input("", key=f"delete_confirm_{sel}", placeholder=sel)
                confirm_cb = st.checkbox("I understand this action is permanent.", key=f"delete_confirm_cb_{sel}")
                delete_submitted = st.form_submit_button(f"🗑️ Delete {sel}")
            if delete_submitted:
                if (confirm.strip().upper() == sel.strip().upper()) and confirm_cb:
                    if sel in st.session_state["DATA"]["holdings"]:
                        st.session_state["DATA"]["holdings"].pop(sel, None)
                        st.session_state["DATA"]["last_updated"] = datetime.now().isoformat(timespec="seconds")
                        st.success(f"Deleted {sel}.")
                        save_portfolio()
                        st.rerun()
                else:
                    st.error("Confirmation failed. Please type the ticker exactly and check the box.")

# ---------------------- Dividends ----------------------
with tab_div:
    st.subheader("Quick Dividend Entry (with last amount & date)", divider="gray")
    if not st.session_state["DATA"]["holdings"]:
        st.info("Add a holding first.")
    else:
        tickers = sorted(list(st.session_state["DATA"]["holdings"].keys()))
        col1, col2, col3, col4 = st.columns([1, 1, 1, 1])
        sel = col1.selectbox("Ticker", options=tickers)
        dflt_date = date.today()
        dt = col2.date_input("Dividend date", value=dflt_date, key=f"div_date_{sel}")
        amt = col3.text_input("Dividend amount to add", value="$0.00", key=f"div_amt_{sel}")
        def _money_to_float(s):
            s = str(s).strip().replace(',', '').replace('$', '')
            try: return float(s) if s else 0.0
            except: return 0.0
        if col4.button("Add dividend"):
            add_val = _money_to_float(amt)
            st.session_state["DATA"]["holdings"][sel]["dividends_collected"] = float(st.session_state["DATA"]["holdings"][sel].get("dividends_collected", 0.0)) + add_val
            st.session_state["DATA"]["holdings"][sel]["last_div_amount"] = add_val
            try:
                st.session_state["DATA"]["holdings"][sel]["last_div_date"] = dt.isoformat()
            except Exception:
                st.session_state["DATA"]["holdings"][sel]["last_div_date"] = str(dt)
            st.session_state["DATA"]["last_updated"] = datetime.now().isoformat(timespec="seconds")
            st.success(f"Added {money_str(add_val)} dividend to {sel} for {dt}.")
            save_portfolio()
            st.rerun()

        rows = []
        total = 0.0
        for tkr, rec in sorted(st.session_state["DATA"]["holdings"].items()):
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

# ---------------------- True ADA ----------------------
with tab_trueada:
    st.subheader("True Adjusted Dividend Average (True ADA)", divider="gray")
    if not st.session_state["DATA"]["holdings"]:
        st.info("Add a holding first to calculate True ADA.")
    else:
        rows = []
        sum_shares = 0.0
        sum_invested = 0.0
        sum_div = 0.0
        total_value = 0.0
        for tkr, rec in sorted(st.session_state["DATA"]["holdings"].items()):
            shares = float(rec.get("shares", 0.0))
            invested = float(rec.get("total_invested", 0.0))
            divs = float(rec.get("dividends_collected", 0.0))
            true_ada = (invested - divs) / shares if shares > 0 else np.nan
            price = fetch_price(tkr) if st.session_state["DATA"]["settings"].get("auto_price", True) else float('nan')
            if np.isnan(price): price = float(st.session_state["DATA"]["last_prices"].get(tkr, np.nan))
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
        c2.metric("Total Value", money_str(total_value + st.session_state["DATA"]["cash_uninvested"]) if np.isfinite(total_value) else "—")
        c3.metric("Unadjusted Avg Cost (Portfolio)", f"${avg_cost_portfolio:,.2f}" if np.isfinite(avg_cost_portfolio) else "—")
        c4.metric("True ADA (Portfolio)", f"${true_ada_portfolio:,.2f}" if np.isfinite(true_ada_portfolio) else "—")
        c5.metric("Adjusted Basis Improvement", f"{improvement_pct:.2f}%" if np.isfinite(improvement_pct) else "—")

# ---------------------- Migration ----------------------
with tab_migrate:
    st.subheader("Migrate from older version", divider="gray")
    st.caption("Import/merge a previous `portfolio_data.json` without losing your data.")
    upl = st.file_uploader("Choose previous JSON file", type=["json"])
    merge_mode = st.radio("Merge strategy", ["Add new tickers only", "Overwrite existing tickers with incoming data"])
    if upl is not None and st.button("Merge now"):
        try:
            incoming = json.load(upl)
            inc_holdings = incoming.get("holdings", {})
            added = 0
            updated = 0
            for tkr, rec in inc_holdings.items():
                rec.setdefault("last_div_amount", 0.0)
                rec.setdefault("last_div_date", "")
                rec.setdefault("purchase_price", None)
                rec.setdefault("dividends_collected", 0.0)
                rec.setdefault("summary", "")
                if tkr not in st.session_state["DATA"]["holdings"]:
                    st.session_state["DATA"]["holdings"][tkr] = rec
                    added += 1
                else:
                    if merge_mode.startswith("Overwrite"):
                        st.session_state["DATA"]["holdings"][tkr] = rec
                        updated += 1
            st.session_state["DATA"]["last_updated"] = datetime.now().isoformat(timespec="seconds")
            st.success(f"Merged successfully. Added: {added}, Updated: {updated}.")
            save_portfolio()
            st.rerun()
        except Exception as e:
            st.error(f"Failed to merge: {e}")

# ---------------------- Backup ----------------------
with tab_backup:
    st.subheader("Backup & Restore", divider="gray")
    new_cash = money_input("Cash Available", key="backup_cash", value=st.session_state["DATA"]["cash_uninvested"])
    if new_cash != st.session_state["DATA"]["cash_uninvested"]:
        st.session_state["DATA"]["cash_uninvested"] = new_cash
        st.session_state["DATA"]["last_updated"] = datetime.now().isoformat(timespec="seconds")
        save_portfolio()
        st.rerun()
    data_json = json.dumps(st.session_state["DATA"], indent=2)
    st.download_button("⬇️ Download backup (JSON)", data=data_json, file_name=f"portfolio_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json", mime="application/json")
    upl = st.file_uploader("Restore from JSON backup", type=["json"])
    if upl is not None and st.button("Restore now"):
        try:
            incoming = json.load(upl)
            incoming.setdefault("settings", {})
            incoming["settings"].setdefault("currency", "USD")
            incoming["settings"].setdefault("auto_price", True)
            incoming.setdefault("last_prices", {})
            incoming.setdefault("last_updated", None)
            incoming.setdefault("cash_uninvested", 0.0)
            incoming["version"] = "1.8.9"
            for rec in incoming.get("holdings", {}).values():
                rec.setdefault("purchase_price", None)
                rec.setdefault("dividends_collected", 0.0)
                rec.setdefault("last_div_amount", 0.0)
                rec.setdefault("last_div_date", "")
                rec.setdefault("summary", "")
            st.session_state["DATA"] = incoming
            st.session_state["DATA"]["last_updated"] = datetime.now().isoformat(timespec="seconds")
            st.success("Backup restored.")
            save_portfolio()
            st.rerun()
        except Exception as e:
            st.error(f"Failed to restore: {e}")