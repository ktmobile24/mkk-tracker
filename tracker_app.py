
# MKK Investment Tracker — v1.8.8
# - Portfolio: color-coded Overall Return $ & %, subtle row striping, right-aligned numbers
# - Top metrics: colored Overall Return "card" (green/red)
# - True ADA: color-coded Return vs True ADA %, striping
# - Keeps delete holding, dividend last amount/date, migration, backup

import json, os, re, shutil, sys
from datetime import datetime, date
from typing import Dict, Any
import streamlit as st, yfinance as yf, pandas as pd, numpy as np

APP_NAME = "MKK Investment Tracker"
st.set_page_config(page_title=APP_NAME, page_icon="💠", layout="wide")

def _data_path()->str:
    if sys.platform == "darwin":
        base = os.path.expanduser("~/Library/Application Support/MKK Investment Tracker")
    else:
        base = os.path.join(os.path.expanduser("~"), ".mkk_investment_tracker")
    os.makedirs(base, exist_ok=True)
    newp = os.path.join(base, "portfolio_data.json")
    for candidate in ["portfolio_data.json", os.path.join(os.path.dirname(__file__), "portfolio_data.json")]:
        if not os.path.exists(newp) and os.path.exists(candidate):
            try: shutil.copy2(candidate, newp)
            except Exception: pass
    return newp

DATA_FILE = _data_path()

def load_data() -> Dict[str, Any]:
    if not os.path.exists(DATA_FILE):
        return {"holdings": {}, "cash_uninvested": 0.0,
                "settings": {"currency":"USD","auto_price": True},
                "last_prices": {}, "last_updated": None, "version":"1.8.8"}
    with open(DATA_FILE,"r",encoding="utf-8") as f:
        d = json.load(f)
    d.setdefault("settings", {})
    d["settings"].setdefault("currency","USD")
    d["settings"].setdefault("auto_price", True)
    d.setdefault("last_prices", {}); d.setdefault("last_updated", None)
    d.setdefault("cash_uninvested", 0.0); d["version"]="1.8.8"
    for rec in d.get("holdings", {}).values():
        rec.setdefault("purchase_price", None)
        rec.setdefault("dividends_collected", 0.0)
        rec.setdefault("last_div_amount", 0.0)
        rec.setdefault("last_div_date", "")
        rec.setdefault("summary","")
    return d

def save_data(data: Dict[str, Any]) -> None:
    with open(DATA_FILE,"w",encoding="utf-8") as f: json.dump(data,f,indent=2)

DATA = load_data()

def money_to_float(text:str)->float:
    if text is None: return 0.0
    s=str(text).strip().replace(',','').replace('$','')
    try: return float(s) if s else 0.0
    except: return 0.0

def money_str(x:float)->str:
    if x is None or not np.isfinite(x): return ""
    return f"${x:,.2f}"

def money_input(label:str,key:str,value:float=0.0,help:str="")->float:
    st.write(label)
    default = money_str(value)
    txt = st.text_input(label="", value=default, key=key, help=help, label_visibility="collapsed", placeholder="$0.00")
    return money_to_float(txt)

def shares_to_float(text: str) -> float:
    if text is None: return 0.0
    s = str(text).strip().replace(',', ' ').replace('\\u00a0',' ').strip()
    s = re.sub(r'\\s+', '', s)
    try: return float(s) if s else 0.0
    except: return 0.0

def shares_input(label: str, key: str, value: float = 0.0, help: str = "", placeholder: str = "0.000000") -> float:
    st.write(label)
    txt = st.text_input(label="", value=f"{value:.6f}" if value else "", key=key, help=help,
                        label_visibility="collapsed", placeholder=placeholder)
    return shares_to_float(txt)

@st.cache_data(show_spinner=False)
def fetch_price(ticker:str)->float:
    try:
        t=yf.Ticker(ticker); hist=t.history(period="5d", interval="1d")
        if hist is None or hist.empty: return float("nan")
        return float(hist["Close"].dropna().iloc[-1])
    except Exception: return float("nan")

@st.cache_data(show_spinner=False)
def fetch_name_and_summary(ticker:str):
    try:
        tk=yf.Ticker(ticker); info=tk.info or {}
        name=info.get("longName") or info.get("shortName") or info.get("symbol") or ticker
        summary=info.get("longBusinessSummary") or info.get("description") or ""
        if summary: summary=(summary[:500]+"…") if len(summary)>500 else summary
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

with st.sidebar:
    st.subheader("Settings")
    DATA["settings"]["currency"] = st.selectbox("Currency (display only)", ["USD","EUR","GBP","JPY","CAD"],
                                                index=["USD","EUR","GBP","JPY","CAD"].index(DATA["settings"].get("currency","USD")))
    DATA["settings"]["auto_price"] = st.checkbox("Auto-update prices from the internet",
                                                 value=DATA["settings"].get("auto_price", True))
    if st.button("🔄 Update all prices now"):
        updated = 0
        for tkr, rec in DATA["holdings"].items():
            p = fetch_price(tkr)
            if np.isfinite(p):
                DATA["last_prices"][tkr] = p; updated += 1
        DATA["last_updated"] = datetime.now().isoformat(timespec="seconds"); save_data(DATA)
        st.success(f"Updated {updated} tickers.")
    if st.button("💾 Save data"):
        save_data(DATA); st.success("Saved.")

st.title("MKK Investment Tracker")
tab_port, tab_add, tab_edit, tab_div, tab_trueada, tab_migrate, tab_backup = st.tabs(
    ["Portfolio","Add Holding","Edit Holdings","Dividends","True ADA","Migration","Backup"]
)

# ---------------------- Portfolio ----------------------
with tab_port:
    if not DATA["holdings"]:
        st.info("No holdings yet. Add your first position in **Add Holding**.")
    else:
        rows=[]; total_invested=0.0; total_value=0.0; total_div=0.0
        for tkr, rec in sorted(DATA["holdings"].items()):
            shares=float(rec.get("shares",0)); invested=float(rec.get("total_invested",0))
            price = fetch_price(tkr) if DATA["settings"].get("auto_price", True) else float('nan')
            if np.isnan(price): price=float(DATA["last_prices"].get(tkr,np.nan))
            market_value = shares*price if np.isfinite(price) else np.nan
            divs=float(rec.get("dividends_collected",0.0))
            overall_return = (market_value - invested if np.isfinite(market_value) else 0.0) + divs
            ret_pct = (overall_return / invested * 100.0) if invested>0 else np.nan
            payout = fetch_dividend_frequency(tkr)
            true_ada = ((invested - divs)/shares) if shares>0 else np.nan

            rows.append({
                "Ticker": tkr,
                "Name": rec.get("name",""),
                "Payout Freq": payout,
                "Shares": round(shares,6),
                "Purchase Price": rec.get("purchase_price", np.nan),
                "Total Invested": invested,
                "Price Now": price if np.isfinite(price) else np.nan,
                "Current Value": market_value if np.isfinite(market_value) else np.nan,
                "Dividends Collected": divs,
                "True ADA": true_ada,
                "Overall Return $": overall_return if np.isfinite(overall_return) else np.nan,
                "Overall Return %": ret_pct if np.isfinite(ret_pct) else np.nan
            })

            if np.isfinite(market_value): total_value += market_value
            total_invested += invested; total_div += divs

        order = ["Ticker","Name","Payout Freq","Shares","Purchase Price","Total Invested","Price Now","Current Value","Dividends Collected","True ADA","Overall Return $","Overall Return %"]
        df = (pd.DataFrame(rows))[order]

        # Format + color + subtle striping
        money_cols=["Purchase Price","Total Invested","Price Now","Current Value","Dividends Collected","True ADA","Overall Return $"]
        pct_cols=["Overall Return %"]

        def fmt_money(v): return "" if pd.isna(v) else f"${float(v):,.2f}"
        def fmt_pct(v): return "" if pd.isna(v) else f"{float(v):,.2f}%"
        def color_returns(v):
            try: x=float(v)
            except Exception: return ""
            if not np.isfinite(x): return ""
            if x > 0: return "color:#16a34a;"   # green-600
            if x < 0: return "color:#dc2626;"   # red-600
            return ""
        stripe_css = [{'selector':'tbody tr:nth-child(odd)','props':'background-color: rgba(0,0,0,0.03);'}]

        styler = (df.style
                    .format({**{c: fmt_money for c in money_cols}, **{c: fmt_pct for c in pct_cols}})
                    .applymap(color_returns, subset=["Overall Return $","Overall Return %"])
                    .set_properties(subset=money_cols+pct_cols, **{"text-align":"right"})
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
                for c in money_cols: df_display[c]=df_display[c].apply(fmt_money)
                for c in pct_cols: df_display[c]=df_display[c].apply(fmt_pct)
                st.dataframe(df_display, use_container_width=True, height=620)

        # Metrics (with colored Overall Return value)
        cash=float(DATA.get("cash_uninvested",0.0))
        overall=(total_value-total_invested)+total_div
        overall_pct=(overall/total_invested*100.0) if total_invested>0 else np.nan
        total_value_incl_cash=total_value+cash

        c1,c2,c3,c4,c5=st.columns(5)
        c1.metric("Total Invested", money_str(total_invested))
        c2.metric("Current Value (Holdings)", money_str(total_value))
        c3.metric("Cash Available", money_str(cash))
        c4.metric("Total Value (incl. Cash)", money_str(total_value_incl_cash))

        # Custom colored card for Overall Return value text
        color = "#16a34a" if (np.isfinite(overall) and overall>0) else ("#dc2626" if (np.isfinite(overall) and overall<0) else "#374151")
        pct_txt = (f"{overall_pct:.2f}%" if np.isfinite(overall_pct) else "—")
        c5.markdown(f"""
<div style="border:1px solid #e5e7eb;border-radius:10px;padding:10px 12px;">
  <div style="font-size:12px;color:#6b7280;">Overall Return</div>
  <div style="font-size:22px;font-weight:700;color:{color};">{money_str(overall)}</div>
  <div style="font-size:12px;color:#6b7280;">{pct_txt}</div>
</div>
""", unsafe_allow_html=True)

        st.markdown("---")
        st.subheader("Cash Available")
        new_cash = money_input("Cash Available", key="cash_available_main", value=float(DATA.get("cash_uninvested",0.0)),
                               help="This is included in Total Value (incl. Cash).")
        if st.button("Save Cash Available"):
            DATA["cash_uninvested"] = float(new_cash); save_data(DATA); st.success("Cash Available saved.")

        if DATA.get("last_updated"): st.caption(f"Last price update: {DATA['last_updated']}")

        st.markdown("---"); st.subheader("Ticker Summaries")
        for tkr, rec in sorted(DATA["holdings"].items()):
            with st.expander(f"{tkr} — {rec.get('name','')}"):
                summary=rec.get("summary","")
                if not summary:
                    nm, sm = fetch_name_and_summary(tkr)
                    if not rec.get("name"): rec["name"]=nm
                    rec["summary"]=sm; save_data(DATA); summary=sm
                if summary: st.write(summary)
                payout=fetch_dividend_frequency(tkr); st.markdown(f"- **Dividend Payout Frequency:** {payout}")

# ---------------------- Add Holding ----------------------
with tab_add:
    st.subheader("Add a Holding")
    with st.form("add_form", clear_on_submit=True):
        col1, col2 = st.columns(2)
        ticker = col1.text_input("Ticker", placeholder="AAPL").strip().upper()
        name = col2.text_input("Name (auto-fills if blank)", placeholder="Apple Inc.").strip()
        shares = shares_input("Shares purchased", key="add_shares", help="Supports up to 6 decimals (e.g., 100.391000).")
        purchase_price = money_input("Purchase price per share ($, optional)", key="add_purchase_price", value=0.0)
        total_invested = money_input("Total invested", key="add_total_invested", value=0.0, help="Include fees/commissions if applicable.")
        dividends = money_input("Dividends collected so far", key="add_dividends", value=0.0)
        submitted = st.form_submit_button("Add Holding")
    if submitted:
        if not ticker or shares <= 0 or total_invested <= 0:
            st.error("Please enter at least Ticker, Shares > 0, and Total invested > 0.")
        else:
            auto_name, auto_summary = fetch_name_and_summary(ticker) if not name else (name, "")
            if ticker in DATA["holdings"]: st.warning("Ticker already exists. Use Edit tab to modify existing holding.")
            else:
                DATA["holdings"][ticker]={
                    "name":auto_name, "shares":float(shares), "total_invested":float(total_invested),
                    "purchase_price": float(purchase_price) if purchase_price>0 else None,
                    "dividends_collected": float(dividends), "summary": auto_summary,
                    "last_div_amount": 0.0, "last_div_date": "",
                    "created": datetime.now().isoformat(timespec="seconds")
                }
                save_data(DATA); st.success(f"Added {ticker} — {auto_name}")

# ---------------------- Edit Holdings ----------------------
with tab_edit:
    st.subheader("Edit / Update Holdings")
    if not DATA["holdings"]:
        st.info("Nothing to edit yet.")
    else:
        all_tickers=sorted(list(DATA["holdings"].keys()))
        sel=st.selectbox("Select ticker", options=all_tickers)
        rec=DATA["holdings"][sel]
        with st.form("edit_form"):
            name=st.text_input("Name", value=rec.get("name",""))
            shares=shares_input("Shares", key=f"edit_shares_{sel}", value=float(rec.get("shares",0)), help="Supports up to 6 decimals.")
            total_invested=money_input("Total invested", key=f"edit_total_invested_{sel}", value=float(rec.get("total_invested",0)))
            purchase_price=money_input("Purchase price per share ($, optional)", key=f"edit_purchase_price_{sel}", value=float(rec.get("purchase_price") or 0.0))
            dividends=money_input("Dividends collected so far", key=f"edit_div_{sel}", value=float(rec.get("dividends_collected",0.0)))
            summary=st.text_area("Summary (auto-fetched; you can edit)", value=rec.get("summary",""), height=120)
            save_btn=st.form_submit_button("Save changes")
        if save_btn:
            DATA["holdings"][sel]={**rec,"name":name,"shares":float(shares),"total_invested":float(total_invested),
                                   "purchase_price": float(purchase_price) if purchase_price>0 else None,
                                   "dividends_collected": float(dividends),"summary":summary,
                                   "updated": datetime.now().isoformat(timespec="seconds")}
            save_data(DATA); st.success(f"Updated {sel}.")
        with st.expander("🗑️ Delete Holding"):
            st.caption("This permanently removes the selected holding from your portfolio data.")
            col_a, col_b = st.columns([1,1])
            confirm = col_a.checkbox(f"Yes, delete {sel}")
            if col_b.button("Delete Holding", disabled=not confirm, type="secondary"):
                try:
                    del DATA["holdings"][sel]
                    save_data(DATA)
                    st.success(f"Deleted {sel}. Refreshing…")
                    st.rerun()
                except KeyError:
                    st.error("Ticker not found.")

# ---------------------- Dividends ----------------------
with tab_div:
    st.subheader("Quick Dividend Entry (with last amount & date)")
    if not DATA["holdings"]:
        st.info("Add a holding first.")
    else:
        tickers=sorted(list(DATA["holdings"].keys()))
        col1,col2,col3,col4=st.columns([1,1,1,1])
        sel=col1.selectbox("Ticker", options=tickers)
        dflt_date = date.today()
        dt = col2.date_input("Dividend date", value=dflt_date, key=f"div_date_{sel}")
        amt = col3.text_input("Dividend amount to add", value="$0.00", key=f"div_amt_{sel}")
        def _money_to_float(s):
            s = str(s).strip().replace(',', '').replace('$','')
            try: return float(s) if s else 0.0
            except: return 0.0
        if col4.button("Add dividend"):
            add_val = _money_to_float(amt)
            DATA["holdings"][sel]["dividends_collected"] = float(DATA["holdings"][sel].get("dividends_collected",0.0)) + add_val
            DATA["holdings"][sel]["last_div_amount"] = add_val
            try:
                DATA["holdings"][sel]["last_div_date"] = dt.isoformat()
            except Exception:
                DATA["holdings"][sel]["last_div_date"] = str(dt)
            save_data(DATA); st.success(f"Added {money_str(add_val)} dividend to {sel} for {dt}.")

        rows=[]; total=0.0
        for tkr, rec in sorted(DATA["holdings"].items()):
            d=float(rec.get("dividends_collected",0.0))
            last_amt=float(rec.get("last_div_amount",0.0))
            last_dt=rec.get("last_div_date","")
            rows.append({"Ticker":tkr,
                         "Dividends Collected": d,
                         "Last Dividend $": last_amt,
                         "Last Dividend Date": last_dt})
            total+=d
        df_div=pd.DataFrame(rows).reset_index(drop=True)
        df_div["Dividends Collected"]=df_div["Dividends Collected"].apply(lambda v: f"${float(v):,.2f}")
        df_div["Last Dividend $"]=df_div["Last Dividend $"].apply(lambda v: f"${float(v):,.2f}" if v else "")
        try:
            st.dataframe(df_div.style.set_table_styles([{'selector':'tbody tr:nth-child(odd)','props':'background-color: rgba(0,0,0,0.03);'}]), use_container_width=True, height=360, hide_index=True)
        except TypeError:
            try:
                st.dataframe(df_div.style.hide(axis="index").set_table_styles([{'selector':'tbody tr:nth-child(odd)','props':'background-color: rgba(0,0,0,0.03);'}]), use_container_width=True, height=360)
            except Exception:
                st.dataframe(df_div, use_container_width=True, height=360)
        st.metric("Total Dividends Collected", money_str(total))

# ---------------------- True ADA ----------------------
with tab_trueada:
    st.subheader("True Adjusted Dividend Average (True ADA)")
    if not DATA["holdings"]:
        st.info("Add a holding first to calculate True ADA.")
    else:
        rows=[]; sum_shares=0.0; sum_invested=0.0; sum_div=0.0
        for tkr, rec in sorted(DATA["holdings"].items()):
            shares=float(rec.get("shares",0.0))
            invested=float(rec.get("total_invested",0.0))
            divs=float(rec.get("dividends_collected",0.0))
            true_ada = (invested - divs)/shares if shares>0 else np.nan
            price = fetch_price(tkr) if DATA["settings"].get("auto_price", True) else float('nan')
            if np.isnan(price): price=float(DATA["last_prices"].get(tkr, np.nan))
            vs_true_pct = ((price - true_ada)/true_ada*100.0) if (shares>0 and np.isfinite(price) and np.isfinite(true_ada) and true_ada!=0) else np.nan
            rows.append({
                "Ticker": tkr,
                "Shares": round(shares,6),
                "Total Invested": invested,
                "Dividends Collected": divs,
                "True ADA": true_ada,
                "Current Price": price if np.isfinite(price) else np.nan,
                "Return vs True ADA %": vs_true_pct
            })
            sum_shares += shares; sum_invested += invested; sum_div += divs

        df = pd.DataFrame(rows)
        df_display = df.copy()
        for c in ["Total Invested","Dividends Collected","True ADA","Current Price"]:
            df_display[c]=df_display[c].apply(lambda v: "" if pd.isna(v) else f"${float(v):,.2f}")
        def fmt_pct(v): return "" if pd.isna(v) else f"{float(v):,.2f}%"
        df_display["Return vs True ADA %"]=df_display["Return vs True ADA %"].apply(fmt_pct)

        def color_pct(v):
            try: x=float(str(v).replace('%',''))
            except: return ""
            if not np.isfinite(x): return ""
            if x > 0: return "color:#16a34a;"
            if x < 0: return "color:#dc2626;"
            return ""

        try:
            sty = (df_display.style
                    .applymap(color_pct, subset=["Return vs True ADA %"])
                    .set_properties(subset=["Total Invested","Dividends Collected","True ADA","Current Price","Return vs True ADA %"], **{"text-align":"right"})
                    .set_table_styles([{'selector':'tbody tr:nth-child(odd)','props':'background-color: rgba(0,0,0,0.03);'}])
                 )
            st.dataframe(sty, use_container_width=True, height=520, hide_index=True)
        except TypeError:
            try:
                st.dataframe(sty.hide(axis="index"), use_container_width=True, height=520)
            except Exception:
                st.dataframe(df_display, use_container_width=True, height=520)

        if sum_shares > 0:
            avg_cost_portfolio = (sum_invested / sum_shares)
            true_ada_portfolio = ((sum_invested - sum_div) / sum_shares)
            improvement_pct = ((avg_cost_portfolio - true_ada_portfolio) / avg_cost_portfolio * 100.0) if avg_cost_portfolio>0 else np.nan
        else:
            avg_cost_portfolio = np.nan
            true_ada_portfolio = np.nan
            improvement_pct = np.nan

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Total Dividends Collected", f"${sum_div:,.2f}")
        c2.metric("Unadjusted Avg Cost (Portfolio)", f"${avg_cost_portfolio:,.2f}" if np.isfinite(avg_cost_portfolio) else "—")
        c3.metric("True ADA (Portfolio)", f"${true_ada_portfolio:,.2f}" if np.isfinite(true_ada_portfolio) else "—")
        c4.metric("Adjusted Basis Improvement", f"{improvement_pct:.2f}%" if np.isfinite(improvement_pct) else "—")

# ---------------------- Migration ----------------------
with tab_migrate:
    st.subheader("Migrate from older version")
    st.caption("Import/merge a previous `portfolio_data.json` without losing your data.")
    upl=st.file_uploader("Choose previous JSON file", type=["json"])
    merge_mode=st.radio("Merge strategy", ["Add new tickers only","Overwrite existing tickers with incoming data"])
    if upl is not None and st.button("Merge now"):
        try:
            incoming=json.load(upl); inc_holdings=incoming.get("holdings",{}); added=0; updated=0
            for tkr, rec in inc_holdings.items():
                rec.setdefault("last_div_amount", 0.0)
                rec.setdefault("last_div_date", "")
                if tkr not in DATA["holdings"]: DATA["holdings"][tkr]=rec; added+=1
                else:
                    if merge_mode.startswith("Overwrite"): DATA["holdings"][tkr]=rec; updated+=1
            save_data(DATA); st.success(f"Merged successfully. Added: {added}, Updated: {updated}.")
        except Exception as e: st.error(f"Failed to merge: {e}")

# ---------------------- Backup ----------------------
with tab_backup:
    st.subheader("Backup & Restore")
    with open(DATA_FILE,"rb") as f:
        st.download_button("⬇️ Download backup (JSON)", data=f, file_name=f"portfolio_backup_%s.json" % datetime.now().strftime('%Y%m%d_%H%M%S'), mime="application/json")
    upl=st.file_uploader("Restore from JSON backup", type=["json"])
    if upl is not None and st.button("Restore now"):
        try:
            DATA=json.load(upl)
            for rec in DATA.get("holdings", {}).values():
                rec.setdefault("last_div_amount", 0.0)
                rec.setdefault("last_div_date", "")
            save_data(DATA); st.success("Backup restored."); st.rerun()
        except Exception as e: st.error(f"Failed to restore: {e}")
