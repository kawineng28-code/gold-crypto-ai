import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import requests
import json
import os
import time
from datetime import datetime

# ---------- ตั้งค่าหน้า ----------
st.set_page_config(page_title="Gold & Crypto AI Trade Analyzer", page_icon="📈", layout="wide")
st.markdown("""
<style>
.stTabs [data-baseweb="tab-list"] { overflow-x: auto; flex-wrap: nowrap; scrollbar-width: thin; }
.stTabs [data-baseweb="tab"] { white-space: nowrap; }
div[data-testid="stMetric"] { background: #f8f9fa; padding: 10px; border-radius: 10px; }
</style>
""", unsafe_allow_html=True)

SETTINGS_FILE = "settings.json"
DEFAULT_COINS = ["BTC-USD", "ETH-USD", "SOL-USD", "BNB-USD", "XRP-USD", "DOGE-USD"]

DEFAULT_SETTINGS = {
    "asset_type": "ทองคำ (Gold)",
    "gold_ticker": "GC=F",
    "crypto_ticker": "BTC-USD",
    "custom_coins": [],
    "timeframe": "15m",
    "mode": "Day Trade",
    "capital": 100000,
    "tp_mult": 2.40,
    "sl_mult": 1.20,
    "chart_type": "Candlestick",
    "show_sma": True,
    "show_boll": False,
    "show_sr": True,
    "panels": ["RSI", "MACD"],
    "show_thb": True,
    "alert_enabled": True,
    "alert_tolerance": 0.5,
    "alert_cooldown": 15,
    "arr_manual": 0,
    "entry_input": 0.0,
    "tp_input": 0.0,
    "sl_input": 0.0,
    "last_ai_key": "",
}

def load_settings():
    data = {}
    try:
        if os.path.exists(SETTINGS_FILE):
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
    except Exception:
        data = {}
    merged = DEFAULT_SETTINGS.copy()
    merged.update(data)
    for k, v in merged.items():
        if k not in st.session_state:
            st.session_state[k] = v
    if "custom_coins" not in st.session_state:
        st.session_state["custom_coins"] = []
    if "last_alert_time" not in st.session_state:
        st.session_state["last_alert_time"] = 0

def save_settings():
    try:
        data = {}
        for k in DEFAULT_SETTINGS.keys():
            if k in st.session_state:
                v = st.session_state[k]
                if isinstance(v, (str, int, float, bool, list)):
                    data[k] = v
        if "custom_coins" in st.session_state:
            data["custom_coins"] = st.session_state["custom_coins"]
        with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception:
        pass

load_settings()

# ---------- ฟังก์ชันช่วย ----------
@st.cache_data(ttl=60)
def get_usd_thb():
    try:
        df = yf.download("USDTHB=X", period="1d", interval="1m", progress=False)
        if len(df) > 0:
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)
            return float(df["Close"].iloc[-1])
    except Exception:
        pass
    try:
        df = yf.download("THB=X", period="1d", interval="1m", progress=False)
        if len(df) > 0:
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)
            return float(df["Close"].iloc[-1])
    except Exception:
        pass
    return 35.5

@st.cache_data(ttl=120)
def get_arr_price():
    return None

@st.cache_data(ttl=60)
def fetch_data(ticker, interval):
    # ดึงยาวสุดที่ 【entity-Yahoo¦canonical_name=Yahoo】 อนุญาตในแต่ละ Timeframe เพื่อให้ข้อมูลเยอะเท่าเดิม
    period_map = {"1m": "7d", "5m": "60d", "15m": "60d", "1h": "730d", "4h": "730d", "1d": "5y"}
    period = period_map.get(interval, "60d")
    try:
        df = yf.download(ticker, period=period, interval=interval, progress=False, auto_adjust=False)
        if df is None or len(df) == 0:
            return pd.DataFrame()
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        df = df.dropna(subset=["Close"])
        df.columns = [c.capitalize() if isinstance(c, str) else c for c in df.columns]
        return df
    except Exception:
        return pd.DataFrame()

def compute_indicators(df):
    df = df.copy()
    df["SMA20"] = df["Close"].rolling(20).mean()
    df["SMA50"] = df["Close"].rolling(50).mean()
    df["SMA200"] = df["Close"].rolling(200).mean()
    delta = df["Close"].diff()
    gain = delta.where(delta > 0, 0).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
    rs = gain / (loss + 1e-9)
    df["RSI"] = 100 - (100 / (1 + rs))
    ema12 = df["Close"].ewm(span=12, adjust=False).mean()
    ema26 = df["Close"].ewm(span=26, adjust=False).mean()
    df["MACD"] = ema12 - ema26
    df["Signal"] = df["MACD"].ewm(span=9, adjust=False).mean()
    df["Hist"] = df["MACD"] - df["Signal"]
    tr1 = df["High"] - df["Low"]
    tr2 = (df["High"] - df["Close"].shift(1)).abs()
    tr3 = (df["Low"] - df["Close"].shift(1)).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    df["ATR"] = tr.rolling(14).mean()
    std20 = df["Close"].rolling(20).std()
    df["BB_Upper"] = df["SMA20"] + 2 * std20
    df["BB_Lower"] = df["SMA20"] - 2 * std20
    return df

def find_sr(df, price):
    levels = []
    try:
        window = 10
        highs = []
        lows = []
        for i in range(window, len(df) - window):
            h = df["High"].iloc[i]
            if h == df["High"].iloc[i-window:i+window+1].max():
                highs.append(float(h))
            l = df["Low"].iloc[i]
            if l == df["Low"].iloc[i-window:i+window+1].min():
                lows.append(float(l))
        def group_and_count(vals):
            vals = sorted(vals)
            grouped = []
            for v in vals:
                found = False
                for g in grouped:
                    if abs(v - g["price"]) / (g["price"] + 1e-9) < 0.005:
                        g["count"] += 1
                        found = True
                        break
                if not found:
                    grouped.append({"price": v, "count": 1})
            return sorted(grouped, key=lambda x: x["count"], reverse=True)
        res = [g for g in group_and_count(highs) if g["price"] > price][:3]
        sup = [g for g in group_and_count(lows) if g["price"] < price][:3]
        res = sorted(res, key=lambda x: x["price"])
        sup = sorted(sup, key=lambda x: x["price"], reverse=True)
        for g in res:
            levels.append({"type": "Res", "price": g["price"], "count": g["count"]})
        for g in sup:
            levels.append({"type": "Sup", "price": g["price"], "count": g["count"]})
    except Exception:
        pass
    return levels

# ---------- Sidebar ตั้งค่า ----------
st.sidebar.title("⚙️ ตั้งค่า")
asset_type = st.sidebar.selectbox("สินทรัพย์", ["ทองคำ (Gold)", "คริปโต (Crypto)"], key="asset_type")
if asset_type == "ทองคำ (Gold)":
    gold_ticker = st.sidebar.selectbox("สัญลักษณ์ทอง", ["GC=F", "GLD", "IAU", "GOLD"], key="gold_ticker")
    active_ticker = gold_ticker
else:
    all_coins = []
    for c in DEFAULT_COINS + list(st.session_state.get("custom_coins", [])):
        if c not in all_coins:
            all_coins.append(c)
    if st.session_state.get("crypto_ticker") not in all_coins:
        all_coins.append(st.session_state.get("crypto_ticker"))
    crypto_ticker = st.sidebar.selectbox("เหรียญ", all_coins, key="crypto_ticker")
    active_ticker = crypto_ticker
    new_coin = st.sidebar.text_input("เพิ่มเหรียญใหม่ เช่น DOGE หรือ PEPE", key="new_coin_input")
    if st.sidebar.button("➕ เพิ่มเหรียญ", key="add_coin_btn"):
        if new_coin.strip() != "":
            nc = new_coin.strip().upper()
            if "-" not in nc:
                nc = nc + "-USD"
            if nc not in st.session_state["custom_coins"] and nc not in DEFAULT_COINS:
                st.session_state["custom_coins"].append(nc)
            st.session_state["crypto_ticker"] = nc
            st.session_state["pending_coin"] = nc
            save_settings()
            st.rerun()

interval = st.sidebar.selectbox("Timeframe", ["1m", "5m", "15m", "1h", "4h", "1d"], key="timeframe")
mode = st.sidebar.selectbox("โหมด", ["Scalping", "Day Trade", "Swing"], key="mode")
capital = st.sidebar.number_input("ทุน (THB)", min_value=1000, step=1000, key="capital")
tp_mult = st.sidebar.number_input("TP x ATR", step=0.1, key="tp_mult")
sl_mult = st.sidebar.number_input("SL x ATR", step=0.1, key="sl_mult")
chart_type = st.sidebar.selectbox("ชนิดกราฟ", ["Candlestick", "Line", "OHLC"], key="chart_type")
show_sma = st.sidebar.checkbox("แสดง SMA 20 / 50 / 200", key="show_sma")
show_boll = st.sidebar.checkbox("แสดง Bollinger", key="show_boll")
show_sr = st.sidebar.checkbox("แสดง แนวรับ-แนวต้าน", key="show_sr")
panels = st.sidebar.multiselect("แผงล่าง", ["RSI", "MACD"], key="panels")
show_thb = st.sidebar.checkbox("แสดงราคา THB", key="show_thb")
st.sidebar.markdown("---")
st.sidebar.markdown("🔔 แจ้งเตือนแนวรับ-แนวต้าน")
alert_enabled = st.sidebar.checkbox("เปิดแจ้งเตือน", key="alert_enabled")
alert_tolerance = st.sidebar.slider("ความใกล้เส้น (%)", 0.1, 2.0, step=0.1, key="alert_tolerance")
alert_cooldown = st.sidebar.number_input("พักแจ้งเตือน (นาที)", min_value=1, step=1, key="alert_cooldown")
st.sidebar.markdown("---")
st.sidebar.markdown("🇹🇭 ทองไทย 96.5%")
arr_manual = st.sidebar.number_input("ราคาทอง ARR ต่อบาท ใส่เอง ถ้าดึงอัตโนมัติไม่ได้ (0 = อัตโนมัติ)", min_value=0, step=100, key="arr_manual")
if st.sidebar.button("🔄 รีเฟรชข้อมูล", key="refresh_btn"):
    st.cache_data.clear()
    st.rerun()

# ---------- ดึงข้อมูล ----------
usd_thb = get_usd_thb()
arr_auto = get_arr_price()
df_raw = fetch_data(active_ticker, interval)

st.title("📈 Gold & Crypto AI Trade Analyzer")
if df_raw.empty:
    st.error("ดึงข้อมูลไม่ได้ ลองเปลี่ยน Timeframe หรือเช็คอินเทอร์เน็ต แล้วกดรีเฟรช")
    st.stop()

df = compute_indicators(df_raw)
last = df.iloc[-1]
price = float(last["Close"])
atr = float(last["ATR"]) if not pd.isna(last["ATR"]) else 0.0
rsi_val = float(last["RSI"]) if not pd.isna(last["RSI"]) else 50.0
macd_val = float(last["MACD"]) if not pd.isna(last["MACD"]) else 0.0
sig_val = float(last["Signal"]) if not pd.isna(last["Signal"]) else 0.0

thai_gold_per_baht = 0.0
if asset_type == "ทองคำ (Gold)":
    thai_gold_per_baht = (price * usd_thb / 31.1035) * 15.244 * 0.965
    if arr_manual and arr_manual > 0:
        thai_gold_per_baht = float(arr_manual)
    elif arr_auto:
        thai_gold_per_baht = float(arr_auto)

sr_levels = find_sr(df, price)

score = 0
if price > last["SMA20"]:
    score += 1
else:
    score -= 1
if not pd.isna(last["SMA50"]):
    if price > last["SMA50"]:
        score += 1
    else:
        score -= 1
if rsi_val > 50:
    score += 1
else:
    score -= 1
if macd_val > sig_val:
    score += 1
else:
    score -= 1

if score >= 2:
    ai_side = "BUY"
    ai_entry = price
    ai_tp = price + tp_mult * atr
    ai_sl = price - sl_mult * atr
elif score <= -2:
    ai_side = "SELL"
    ai_entry = price
    ai_tp = price - tp_mult * atr
    ai_sl = price + sl_mult * atr
else:
    ai_side = "WAIT"
    ai_entry = price
    ai_tp = price + tp_mult * atr
    ai_sl = price - sl_mult * atr

ai_key = f"{active_ticker}_{interval}"
if st.session_state.get("last_ai_key") != ai_key or st.session_state.get("entry_input", 0) == 0:
    st.session_state["entry_input"] = float(ai_entry)
    st.session_state["tp_input"] = float(ai_tp)
    st.session_state["sl_input"] = float(ai_sl)
    st.session_state["last_ai_key"] = ai_key

c1, c2, c3, c4 = st.columns(4)
with c1:
    st.metric(f"{active_ticker} | {interval}", f"{price:,.2f} USD")
with c2:
    if show_thb:
        st.metric("ราคา THB", f"{price * usd_thb:,.2f} ฿")
    else:
        st.metric("USD/THB", f"{usd_thb:,.2f}")
with c3:
    if asset_type == "ทองคำ (Gold)":
        st.metric("ทองไทย 96.5% / บาท", f"{thai_gold_per_baht:,.2f} ฿")
    else:
        st.metric("RSI (14)", f"{rsi_val:.1f}")
with c4:
    st.metric("ATR", f"{atr:.2f}")
    st.caption(f"ข้อมูลทั้งหมด {len(df)} แท่ง | อัปเดต {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

alert_msgs = []
if alert_enabled and sr_levels:
    now_ts = time.time()
    cooldown_sec = int(alert_cooldown) * 60
    for lv in sr_levels:
        diff_pct = abs(price - lv["price"]) / (lv["price"] + 1e-9) * 100
        if diff_pct <= float(alert_tolerance):
            msg = f"ราคา {price:,.2f} ใกล้ {lv['type']} {lv['price']:,.2f} ({lv['count']}x) ห่าง {diff_pct:.2f}%"
            alert_msgs.append(msg)
            if now_ts - st.session_state.get("last_alert_time", 0) > cooldown_sec:
                st.toast(f"🔔 {msg}")
                st.session_state["last_alert_time"] = now_ts
    if alert_msgs:
        for m in alert_msgs:
            st.warning(f"🔔 {m}")

col_ai, col_chart = st.columns([1, 2.1])

with col_ai:
    st.markdown("### 🤖 AI แผนเทรด")
    color = "green" if ai_side == "BUY" else "red" if ai_side == "SELL" else "gray"
    st.markdown(f"**สัญญาณ:** :{color}[{ai_side}]  | คะแนน {score} / 4 | โหมด {mode}")
    st.markdown(f"RSI {rsi_val:.1f} | MACD {macd_val:.2f} | Signal {sig_val:.2f}")
    entry_val = st.number_input("Entry (แก้ไขได้)", key="entry_input", format="%.2f")
    tp_val = st.number_input("TP (แก้ไขได้)", key="tp_input", format="%.2f")
    sl_val = st.number_input("SL (แก้ไขได้)", key="sl_input", format="%.2f")
    if ai_side == "BUY":
        if not (sl_val < entry_val < tp_val):
            st.warning("สำหรับ BUY ต้องเป็น SL < Entry < TP")
    elif ai_side == "SELL":
        if not (tp_val < entry_val < sl_val):
            st.warning("สำหรับ SELL ต้องเป็น TP < Entry < SL")
    risk_per_unit = abs(entry_val - sl_val) if entry_val != 0 else 0
    reward_per_unit = abs(tp_val - entry_val) if entry_val != 0 else 0
    rr = (reward_per_unit / risk_per_unit) if risk_per_unit > 0 else 0
    risk_amount = capital * 0.02
    qty = (risk_amount / (risk_per_unit * usd_thb)) if risk_per_unit > 0 and usd_thb > 0 else 0
    st.markdown(f"**R:R = 1 : {rr:.2f}** | เสี่ยง 2% = {risk_amount:,.0f} ฿")
    st.markdown(f"**ขนาดที่แนะนำ:** {qty:.4f} หน่วย")
    st.markdown(f"กำไรถ้าถึง TP: {reward_per_unit * qty * usd_thb:,.0f} ฿ | ขาดทุนถ้าโดน SL: -{risk_amount:,.0f} ฿")
    if asset_type == "ทองคำ (Gold)":
        st.markdown(f"ทองไทย 96.5% : {thai_gold_per_baht:,.2f} ฿ / บาท")
        st.caption("ราคาทองไทยคำนวณจาก GC=F x USDTHB ถ้าใส่ ARR เองจะใช้ราคาที่ใส่")
    st.markdown("---")
    st.markdown("**แนวรับ-แนวต้านล่าสุด**")
    for lv in sr_levels:
        st.write(f"{lv['type']} {lv['price']:,.2f} ({lv['count']}x)")

with col_chart:
    z1, z2 = st.columns([1, 2])
    with z1:
        zoom_choice = st.selectbox("🔍 ซูมดูกราฟ", ["ดูทั้งหมด", "200 แท่งล่าสุด", "100 แท่งล่าสุด", "50 แท่งล่าสุด"], key="zoom_window_select")
    zoom_map = {"ดูทั้งหมด": len(df), "200 แท่งล่าสุด": 200, "100 แท่งล่าสุด": 100, "50 แท่งล่าสุด": 50}
    zoom_n = min(zoom_map[zoom_choice], len(df))
    scroll_pos = len(df) - zoom_n
    if zoom_n < len(df):
        if "chart_scroll" in st.session_state and st.session_state["chart_scroll"] > len(df) - zoom_n:
            st.session_state["chart_scroll"] = len(df) - zoom_n
        with z2:
            scroll_pos = st.slider("⬅️ เลื่อนซ้าย-ขวา ➡️", 0, len(df) - zoom_n, len(df) - zoom_n, key="chart_scroll")
    x_start = df.index[scroll_pos]
    x_end = df.index[min(scroll_pos + zoom_n - 1, len(df) - 1)]

    with st.container(border=True):
        st.markdown(f"### กราฟ {active_ticker} • {interval} • {len(df)} แท่ง")
        active_panels = [p for p in panels if p in ["RSI", "MACD"]]
        n_rows = 1 + len(active_panels)
        row_heights = [0.6] + [0.2] * len(active_panels)
        titles = [f"{active_ticker} | {interval}"]
        if "RSI" in active_panels:
            titles.append("RSI (14)")
        if "MACD" in active_panels:
            titles.append("MACD (12, 26, 9)")
        fig = make_subplots(rows=n_rows, cols=1, shared_xaxes=True, vertical_spacing=0.05, row_heights=row_heights, subplot_titles=titles)
        if chart_type == "Candlestick":
            fig.add_trace(go.Candlestick(x=df.index, open=df["Open"], high=df["High"], low=df["Low"], close=df["Close"], name="Candlestick"), row=1, col=1)
        elif chart_type == "OHLC":
            fig.add_trace(go.Ohlc(x=df.index, open=df["Open"], high=df["High"], low=df["Low"], close=df["Close"], name="OHLC"), row=1, col=1)
        else:
            fig.add_trace(go.Scatter(x=df.index, y=df["Close"], mode="lines", name="Line", line=dict(color="#2563eb", width=2)), row=1, col=1)
        if show_sma:
            fig.add_trace(go.Scatter(x=df.index, y=df["SMA20"], mode="lines", name="SMA 20", line=dict(color="orange", width=1)), row=1, col=1)
            fig.add_trace(go.Scatter(x=df.index, y=df["SMA50"], mode="lines", name="SMA 50", line=dict(color="purple", width=1)), row=1, col=1)
            fig.add_trace(go.Scatter(x=df.index, y=df["SMA200"], mode="lines", name="SMA 200", line=dict(color="blue", width=1)), row=1, col=1)
        if show_boll:
            fig.add_trace(go.Scatter(x=df.index, y=df["BB_Upper"], mode="lines", name="BB Upper", line=dict(color="gray", dash="dot")), row=1, col=1)
            fig.add_trace(go.Scatter(x=df.index, y=df["BB_Lower"], mode="lines", name="BB Lower", line=dict(color="gray", dash="dot")), row=1, col=1)
        fig.add_hline(y=float(entry_val), line_dash="solid", line_color="black", annotation_text=f"Entry {entry_val:,.2f}", row=1, col=1)
        fig.add_hline(y=float(tp_val), line_dash="dash", line_color="green", annotation_text=f"TP {tp_val:,.2f}", row=1, col=1)
        fig.add_hline(y=float(sl_val), line_dash="dash", line_color="red", annotation_text=f"SL {sl_val:,.2f}", row=1, col=1)
        if show_sr:
            for lv in sr_levels:
                col = "red" if lv["type"] == "Res" else "green"
                dash = "dash" if lv["type"] == "Res" else "dot"
                fig.add_hline(y=lv["price"], line_dash=dash, line_color=col, annotation_text=f"{lv['type']} {lv['price']:,.2f} ({lv['count']}x)", row=1, col=1)
        r = 2
        if "RSI" in active_panels:
            fig.add_trace(go.Scatter(x=df.index, y=df["RSI"], mode="lines", name="RSI", line=dict(color="orange")), row=r, col=1)
            fig.add_hline(y=70, line_dash="dash", line_color="red", row=r, col=1)
            fig.add_hline(y=30, line_dash="dash", line_color="green", row=r, col=1)
            r += 1
        if "MACD" in active_panels:
            fig.add_trace(go.Scatter(x=df.index, y=df["MACD"], mode="lines", name="MACD", line=dict(color="blue")), row=r, col=1)
            fig.add_trace(go.Scatter(x=df.index, y=df["Signal"], mode="lines", name="Signal", line=dict(color="red", dash="dash")), row=r, col=1)
            fig.add_trace(go.Bar(x=df.index, y=df["Hist"], name="Hist", marker_color="green"), row=r, col=1)
            r += 1
        fig.update_layout(height=520 + (len(active_panels) * 130), hovermode="x unified", dragmode="zoom", legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
        fig.update_xaxes(
            range=[x_start, x_end],
            rangeslider=dict(visible=True, thickness=0.08),
            rangeselector=dict(
                buttons=[
                    dict(count=1, label="1D", step="day", stepmode="backward"),
                    dict(count=5, label="5D", step="day", stepmode="backward"),
                    dict(count=1, label="1M", step="month", stepmode="backward"),
                    dict(step="all", label="ทั้งหมด"),
                ]
            ),
            type="date",
        )
        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": True, "scrollZoom": True, "displaylogo": False, "modeBarButtonsToRemove": ["lasso2d", "select2d"]})
        st.caption("วิธีใช้: ลากแถบบาร์ด้านล่างเพื่อเลื่อนซ้าย-ขวา / หมุนล้อเมาส์บนกราฟเพื่อซูม / ลากคลุมกราฟเพื่อซูม / ดับเบิ้ลคลิกที่กราฟเพื่อรีเซ็ตซูม")

tab1, tab2, tab3, tab4 = st.tabs(["📊 สรุป AI", "🎯 แนวรับ-แนวต้าน", "🔔 แจ้งเตือน", "⚙️ ตั้งค่าที่บันทึกไว้"])
with tab1:
    st.markdown(f"**สัญญาณ {ai_side}** | Entry {entry_val:,.2f} | TP {tp_val:,.2f} | SL {sl_val:,.2f} | R:R 1:{rr:.2f}")
    st.markdown(f"เหตุผล: ราคา {'อยู่เหนือ' if price > last['SMA20'] else 'อยู่ต่ำกว่า'} SMA20, RSI {rsi_val:.1f}, MACD {'เหนือ' if macd_val > sig_val else 'ต่ำกว่า'} Signal, ATR {atr:.2f}")
    st.dataframe(df.tail(100)[["Close", "SMA20", "SMA50", "RSI", "MACD", "Signal", "ATR"]].sort_index(ascending=False), use_container_width=True)
with tab2:
    if sr_levels:
        sr_df = pd.DataFrame(sr_levels)
        sr_df["ห่างจากราคาปัจจุบัน (%)"] = (price - sr_df["price"]).abs() / sr_df["price"] * 100
        st.dataframe(sr_df, use_container_width=True)
    else:
        st.info("ยังหาแนวรับแนวต้านไม่เจอ รอข้อมูลเพิ่ม")
with tab3:
    if alert_msgs:
        for m in alert_msgs:
            st.warning(m)
    else:
        st.success("ตอนนี้ราคาไม่ใกล้แนวรับแนวต้านตามค่าที่ตั้งไว้")
    st.markdown(f"ตั้งค่า: เปิดแจ้งเตือน = {alert_enabled} | ความใกล้ = {alert_tolerance}% | พัก = {alert_cooldown} นาที")
with tab4:
    st.markdown("ค่าที่จะถูกจำไว้ทุกครั้งที่เปิดแอปใหม่")
    st.json({"asset": asset_type, "ticker": active_ticker, "timeframe": interval, "mode": mode, "capital": capital, "tp_mult": tp_mult, "sl_mult": sl_mult, "chart_type": chart_type, "panels": panels, "custom_coins": st.session_state.get("custom_coins", [])})

save_settings()
st.caption("Gold & Crypto AI Trade Analyzer - ข้อมูลจาก 【entity-Yahoo Finance¦canonical_name=Yahoo】, ราคาทองไทยอ้างอิง ARR / คำนวณจาก GC=F x USDTHB - ไม่ใช่คำแนะนำการลงทุน")
