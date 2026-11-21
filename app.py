import time
import json
import os
import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st
import streamlit.components.v1 as components
import yfinance as yf
from datetime import datetime

TROY_OZ_TO_GRAM = 31.1035
THAI_BAHT_GOLD_GRAM = 15.244
PURITY_965 = 0.965
ALERT_FILE = "alerts.json"
WATCH_FILE = "watchlist.json"

GOLD_PRESETS = {
    "GC=F": "GC=F - Gold Futures",
    "GLD": "GLD - SPDR Gold Shares",
    "IAU": "IAU - iShares Gold Trust",
    "GOLD": "GOLD - Barrick Mining",
}
DEFAULT_CRYPTO_COINS = ["BTC-USD", "ETH-USD", "SOL-USD", "BNB-USD", "XRP-USD"]
OVERLAY_OPTIONS = ["SMA 20", "SMA 50", "SMA 200", "EMA 20", "EMA 50", "Bollinger Bands", "VWAP", "Parabolic SAR", "Pivot Points", "Auto Support/Resistance"]
PANEL_OPTIONS = ["RSI (14)", "MACD (12, 26, 9)", "Stochastic (%K, %D)", "ATR (14)", "ADX (14)", "OBV", "Volume"]

st.set_page_config(page_title="Gold & Crypto AI", page_icon="🥇", layout="wide")
st.markdown("""
<style>
.stApp { background-color: #F6F7F9; }
.block-container { padding-top: 1.2rem; padding-bottom: 1rem; max-width: 1280px; }
div[data-testid="stMetric"] { background: #FFFFFF; border-radius: 14px; padding: 12px 14px; border: 1px solid #EDEFF3; }
div[data-testid="stExpander"] { background: #FFFFFF; border-radius: 12px; border: 1px solid #EDEFF3; }
</style>
""", unsafe_allow_html=True)

if "custom_coins" not in st.session_state:
    st.session_state.custom_coins = []
if "selected_coin" not in st.session_state:
    st.session_state.selected_coin = "BTC-USD"
if "ai_ticker" not in st.session_state:
    st.session_state.ai_ticker = None
if "last_alert_times" not in st.session_state:
    st.session_state.last_alert_times = {}

def normalize_crypto_symbol(raw: str) -> str:
    sym = raw.strip().upper()
    if not sym:
        return ""
    if "-" not in sym and not sym.endswith("=X") and not sym.endswith("=F"):
        sym = f"{sym}-USD"
    return sym

def calc_thai_gold_965_per_baht(spot_usd_per_oz: float, usd_thb: float) -> float:
    return (spot_usd_per_oz / TROY_OZ_TO_GRAM) * PURITY_965 * THAI_BAHT_GOLD_GRAM * usd_thb

def to_thb_value(usd_price: float, usd_thb: float, is_gold_spot: bool) -> float:
    if is_gold_spot:
        return calc_thai_gold_965_per_baht(usd_price, usd_thb)
    return usd_price * usd_thb

def compute_parabolic_sar(high: pd.Series, low: pd.Series, af_start=0.02, af_step=0.02, af_max=0.2) -> pd.Series:
    h = high.to_numpy(dtype=float)
    l = low.to_numpy(dtype=float)
    n = len(h)
    if n < 2:
        return pd.Series([np.nan] * n, index=high.index)
    sar = np.zeros(n, dtype=float)
    is_uptrend = h[1] >= h[0]
    af = af_start
    ep = h[1] if is_uptrend else l[1]
    sar[0] = l[0] if is_uptrend else h[0]
    sar[1] = l[0] if is_uptrend else h[0]
    for i in range(2, n):
        prev_sar = sar[i - 1]
        if is_uptrend:
            curr_sar = prev_sar + af * (ep - prev_sar)
            curr_sar = min(curr_sar, l[i - 1], l[i - 2])
            if l[i] < curr_sar:
                is_uptrend = False
                curr_sar = ep
                ep = l[i]
                af = af_start
            else:
                if h[i] > ep:
                    ep = h[i]
                    af = min(af + af_step, af_max)
        else:
            curr_sar = prev_sar + af * (ep - prev_sar)
            curr_sar = max(curr_sar, h[i - 1], h[i - 2])
            if h[i] > curr_sar:
                is_uptrend = True
                curr_sar = ep
                ep = h[i]
                af = af_start
            else:
                if l[i] < ep:
                    ep = l[i]
                    af = min(af + af_step, af_max)
        sar[i] = curr_sar
    return pd.Series(sar, index=high.index)

def compute_ai_signal_score(row: pd.Series):
    score = 0.0
    reasons = []
    rsi = row.get("RSI")
    if pd.notna(rsi):
        if rsi < 30:
            score += 22.0
            reasons.append(f"RSI {rsi:.1f} Oversold ลุ้นเด้ง (+22)")
        elif rsi < 40:
            score += 10.0
            reasons.append(f"RSI {rsi:.1f} ฟื้นจากโซนล่าง (+10)")
        elif rsi > 70:
            score -= 22.0
            reasons.append(f"RSI {rsi:.1f} Overbought ระวังย่อ (-22)")
        elif rsi > 60:
            score -= 8.0
            reasons.append(f"RSI {rsi:.1f} เริ่มตึง (-8)")
    macd = row.get("MACD")
    sig = row.get("MACD_SIGNAL")
    if pd.notna(macd) and pd.notna(sig):
        if macd > sig:
            score += 18.0
            reasons.append("MACD เหนือ Signal โมเมนตัมบวก (+18)")
        else:
            score -= 18.0
            reasons.append("MACD ต่ำกว่า Signal โมเมนตัมลบ (-18)")
    close_p = row.get("Close")
    sma20 = row.get("SMA_20")
    sma50 = row.get("SMA_50")
    if pd.notna(close_p) and pd.notna(sma20) and pd.notna(sma50):
        if close_p > sma20 > sma50:
            score += 25.0
            reasons.append("ราคาเหนือ SMA 20 > SMA 50 ขาขึ้น (+25)")
        elif close_p < sma20 < sma50:
            score -= 25.0
            reasons.append("ราคาต่ำกว่า SMA 20 < SMA 50 ขาลง (-25)")
    sk = row.get("STOCH_K")
    sd = row.get("STOCH_D")
    if pd.notna(sk) and pd.notna(sd):
        if sk < 20 and sk > sd:
            score += 15.0
            reasons.append("Stochastic ตัดขึ้นจากโซนขายมาก (+15)")
        elif sk > 80 and sk < sd:
            score -= 15.0
            reasons.append("Stochastic ตัดลงจากโซนซื้อมาก (-15)")
    adx = row.get("ADX")
    pdi = row.get("PLUS_DI")
    mdi = row.get("MINUS_DI")
    if pd.notna(adx) and pd.notna(pdi) and pd.notna(mdi) and adx >= 25:
        if pdi > mdi:
            score += 20.0
            reasons.append(f"ADX {adx:.1f} ฝั่ง +DI นำ (+20)")
        else:
            score -= 20.0
            reasons.append(f"ADX {adx:.1f} ฝั่ง -DI นำ (-20)")
    return float(np.clip(score, -100.0, 100.0)), reasons

def estimate_historical_win_rate(df: pd.DataFrame, horizon_bars: int = 12):
    if len(df) < horizon_bars + 25:
        return 0, None, None
    scores = df.apply(lambda r: compute_ai_signal_score(r)[0], axis=1)
    closes = df["Close"].to_numpy(dtype=float)
    wins = 0
    total = 0
    returns_pct = []
    for i in range(20, len(df) - horizon_bars):
        s = float(scores.iloc[i])
        entry = closes[i]
        exit_p = closes[i + horizon_bars]
        if entry <= 0:
            continue
        if s >= 35.0:
            ret = ((exit_p - entry) / entry) * 100.0
            total += 1
            returns_pct.append(ret)
            if ret > 0:
                wins += 1
        elif s <= -35.0:
            ret = ((entry - exit_p) / entry) * 100.0
            total += 1
            returns_pct.append(ret)
            if ret > 0:
                wins += 1
    if total == 0:
        return 0, None, None
    return total, (wins / total) * 100.0, float(np.mean(returns_pct))

def compute_ai_levels(summary: dict, tp_mult: float, sl_mult: float) -> dict:
    score = summary["ai_score"]
    latest_p = summary["latest_close"]
    atr_p = summary["atr"] or max(latest_p * 0.008, 1.0)
    support = summary["support"]
    resistance = summary["resistance"]
    if score >= 25.0:
        side = "LONG"
        title = "🟢 เข้าซื้อ / รอย่อซื้อ"
        entry = latest_p
        tp = min(latest_p + (atr_p * tp_mult), resistance) if resistance > latest_p else latest_p + (atr_p * tp_mult)
        if tp <= entry:
            tp = latest_p + (atr_p * tp_mult)
        sl = max(latest_p - (atr_p * sl_mult), support) if support < latest_p else latest_p - (atr_p * sl_mult)
        if sl >= entry:
            sl = latest_p - (atr_p * sl_mult)
    elif score <= -25.0:
        side = "SHORT"
        title = "🔴 ขาย / รอดีดขาย"
        entry = latest_p
        tp = max(latest_p - (atr_p * tp_mult), support) if support < latest_p else latest_p - (atr_p * tp_mult)
        if tp >= entry:
            tp = latest_p - (atr_p * tp_mult)
        sl = min(latest_p + (atr_p * sl_mult), resistance) if resistance > latest_p else latest_p + (atr_p * sl_mult)
        if sl <= entry:
            sl = latest_p + (atr_p * sl_mult)
    else:
        side = "LONG"
        title = "🟡 รอสัญญาณ / เล่นในกรอบ"
        entry = latest_p
        tp = latest_p + (atr_p * tp_mult)
        sl = latest_p - (atr_p * sl_mult)
    return {"side": side, "title": title, "entry": entry, "tp": tp, "sl": sl, "score": score}

# ---------- แนวรับแนวต้าน + แจ้งเตือน ----------
def compute_sr_levels(df: pd.DataFrame, window: int = 60):
    price = float(df["Close"].iloc[-1])
    recent = df.tail(min(window, len(df)))
    prev_bar = df.iloc[-2] if len(df) >= 2 else df.iloc[-1]
    ph = float(prev_bar["High"])
    pl = float(prev_bar["Low"])
    pc = float(prev_bar["Close"])
    pp = (ph + pl + pc) / 3.0
    r1 = 2 * pp - pl
    s1 = 2 * pp - ph
    r2 = pp + (ph - pl)
    s2 = pp - (ph - pl)
    candidates = [
        {"level": float(recent["Low"].min()), "source": "Low รอบล่าสุด"},
        {"level": float(recent["High"].max()), "source": "High รอบล่าสุด"},
        {"level": s1, "source": "Pivot S1"},
        {"level": r1, "source": "Pivot R1"},
        {"level": s2, "source": "Pivot S2"},
        {"level": r2, "source": "Pivot R2"},
        {"level": pp, "source": "Pivot PP"},
    ]
    for step in [100, 50, 10]:
        if price < 100:
            step = 1
        nearest = round(price / step) * step
        for d in [-step, 0, step]:
            lvl = float(nearest + d)
            if lvl > 0:
                candidates.append({"level": lvl, "source": f"เลขกลม {step}"})
    levels = []
    tail = df.tail(200)
    for cand in candidates:
        lvl = cand["level"]
        if any(abs(lvl - x["level"]) / price * 100 < 0.3 for x in levels):
            continue
        touches = 0
        for _, row in tail.iterrows():
            if abs(float(row["Low"]) - lvl) / lvl * 100 < 0.5 or abs(float(row["High"]) - lvl) / lvl * 100 < 0.5:
                touches += 1
        dist_pct = (price - lvl) / price * 100
        typ = "support" if lvl < price else "resistance" if lvl > price else "pivot"
        strength = "แข็ง" if touches >= 5 else "กลาง" if touches >= 3 else "อ่อน"
        levels.append({"level": lvl, "type": typ, "source": cand["source"], "touches": touches, "dist_pct": dist_pct, "strength": strength})
    supports = sorted([x for x in levels if x["level"] < price], key=lambda x: -x["level"])[:4]
    resistances = sorted([x for x in levels if x["level"] > price], key=lambda x: x["level"])[:4]
    return supports, resistances, levels

def check_sr_alerts(price: float, supports, resistances, summary: dict, tolerance_pct: float):
    alerts = []
    for sup in supports:
        dist = abs(price - sup["level"]) / price * 100
        if dist <= tolerance_pct:
            alerts.append({"kind": "near_support", "level": sup["level"], "dist_pct": dist, "msg": f"ราคาใกล้แนวรับ {sup['level']:,.2f} ห่าง {dist:.2f}% | {sup['source']} ชน {sup['touches']} ครั้ง ({sup['strength']})"})
    for res in resistances:
        dist = abs(price - res["level"]) / price * 100
        if dist <= tolerance_pct:
            alerts.append({"kind": "near_resistance", "level": res["level"], "dist_pct": dist, "msg": f"ราคาใกล้แนวต้าน {res['level']:,.2f} ห่าง {dist:.2f}% | {res['source']} ชน {res['touches']} ครั้ง ({res['strength']})"})
    if price > summary["resistance"]:
        alerts.append({"kind": "break_resistance", "level": summary["resistance"], "dist_pct": 0.0, "msg": f"ทะลุแนวต้านแล้ว {price:,.2f} > {summary['resistance']:,.2f} ลุ้นไปต่อ"})
    if price < summary["support"]:
        alerts.append({"kind": "break_support", "level": summary["support"], "dist_pct": 0.0, "msg": f"หลุดแนวรับแล้ว {price:,.2f} < {summary['support']:,.2f} ระวังลงต่อ"})
    return alerts

def load_alert_history():
    try:
        with open(ALERT_FILE, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []

def save_alert_to_file(alert: dict):
    hist = load_alert_history()
    hist.insert(0, alert)
    hist = hist[:100]
    try:
        with open(ALERT_FILE, "w", encoding="utf-8") as f:
            json.dump(hist, f, ensure_ascii=False, indent=2)
    except Exception:
        pass
    return hist

def save_watch_config(tickers, tolerance, cooldown_min):
    try:
        with open(WATCH_FILE, "w", encoding="utf-8") as f:
            json.dump({"tickers": tickers, "tolerance": tolerance, "cooldown_min": cooldown_min, "updated": datetime.now().isoformat()}, f, ensure_ascii=False, indent=2)
    except Exception:
        pass

def send_desktop_notify(title: str, message: str):
    try:
        from plyer import notification
        notification.notify(title=title, message=message, app_name="Gold Crypto AI", timeout=10)
        return True
    except Exception:
        return False

def trigger_browser_alert(title: str, message: str):
    try:
        safe_title = title.replace("`", "").replace('"', "")
        safe_msg = message.replace("`", "").replace('"', "")
        components.html(f"""
        <script>
        if (window.Notification && Notification.permission !== 'granted') {{ Notification.requestPermission(); }}
        else if (window.Notification) {{ new Notification("{safe_title}", {{body: "{safe_msg}"}}); }}
        try {{
          var ctx = new (window.AudioContext || window.webkitAudioContext)();
          var o = ctx.createOscillator(); o.connect(ctx.destination); o.frequency.value = 880; o.start();
          setTimeout(function(){{ o.stop(); }}, 500);
        }} catch(e) {{}}
        </script>
        """, height=0)
    except Exception:
        pass

@st.cache_data(ttl=20, show_spinner=False)
def fetch_and_analyze(sym: str, hist_period: str, bar_interval: str, window_size: int):
    df = yf.download(sym, period=hist_period, interval=bar_interval, progress=False)
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    df = df.dropna(subset=["Open", "High", "Low", "Close"]).copy()
    if df.empty or len(df) < 15:
        return None, None
    if getattr(df.index, "tz", None) is None:
        df.index = df.index.tz_localize("UTC").tz_convert("Asia/Bangkok")
    else:
        df.index = df.index.tz_convert("Asia/Bangkok")
    df["SMA_20"] = df["Close"].rolling(window=min(20, max(2, len(df) // 2))).mean()
    df["SMA_50"] = df["Close"].rolling(window=min(50, max(3, len(df) - 1))).mean()
    df["SMA_200"] = df["Close"].rolling(window=min(200, max(5, len(df) - 1))).mean()
    df["EMA_20"] = df["Close"].ewm(span=min(20, max(2, len(df) // 2)), adjust=False).mean()
    df["EMA_50"] = df["Close"].ewm(span=min(50, max(3, len(df) - 1)), adjust=False).mean()
    bb_win = min(20, max(2, len(df) // 2))
    bb_mid = df["Close"].rolling(window=bb_win).mean()
    bb_std = df["Close"].rolling(window=bb_win).std()
    df["BB_UPPER"] = bb_mid + (2 * bb_std)
    df["BB_LOWER"] = bb_mid - (2 * bb_std)
    has_vol_data = ("Volume" in df.columns) and (df["Volume"].fillna(0).sum() > 0)
    if has_vol_data:
        vol = df["Volume"].fillna(0.0)
        typical_price = (df["High"] + df["Low"] + df["Close"]) / 3.0
        cum_vol = vol.cumsum().replace(0, np.nan)
        df["VWAP"] = ((typical_price * vol).cumsum()) / cum_vol
        price_diff = df["Close"].diff().fillna(0.0)
        direction = np.where(price_diff > 0, 1.0, np.where(price_diff < 0, -1.0, 0.0))
        df["OBV"] = (direction * vol.to_numpy(dtype=float)).cumsum()
    else:
        df["VWAP"] = np.nan
        df["OBV"] = np.nan
    df["PSAR"] = compute_parabolic_sar(df["High"], df["Low"])
    rsi_win = min(14, max(2, len(df) - 1))
    delta = df["Close"].diff()
    gain = delta.where(delta > 0, 0.0).rolling(window=rsi_win).mean()
    loss = (-delta.where(delta < 0, 0.0)).rolling(window=rsi_win).mean()
    rs = gain / loss.replace(0, pd.NA)
    df["RSI"] = 100 - (100 / (1 + rs))
    ema_fast = df["Close"].ewm(span=12, adjust=False).mean()
    ema_slow = df["Close"].ewm(span=26, adjust=False).mean()
    df["MACD"] = ema_fast - ema_slow
    df["MACD_SIGNAL"] = df["MACD"].ewm(span=9, adjust=False).mean()
    df["MACD_HIST"] = df["MACD"] - df["MACD_SIGNAL"]
    stoch_win = min(14, max(2, len(df) - 1))
    low_min = df["Low"].rolling(window=stoch_win).min()
    high_max = df["High"].rolling(window=stoch_win).max()
    denom = (high_max - low_min).replace(0, np.nan)
    df["STOCH_K"] = ((df["Close"] - low_min) / denom) * 100.0
    df["STOCH_D"] = df["STOCH_K"].rolling(window=3).mean()
    atr_win = min(14, max(2, len(df) - 1))
    prev_close = df["Close"].shift(1)
    tr = pd.concat([df["High"] - df["Low"], (df["High"] - prev_close).abs(), (df["Low"] - prev_close).abs()], axis=1).max(axis=1)
    df["ATR"] = tr.rolling(window=atr_win).mean()
    up_move = df["High"].diff()
    down_move = -df["Low"].diff()
    plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0.0)
    minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0.0)
    atr_smooth = tr.rolling(window=atr_win).mean().replace(0, np.nan)
    plus_di = 100.0 * (pd.Series(plus_dm, index=df.index).rolling(window=atr_win).mean() / atr_smooth)
    minus_di = 100.0 * (pd.Series(minus_dm, index=df.index).rolling(window=atr_win).mean() / atr_smooth)
    dx = ((plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan)) * 100.0
    df["PLUS_DI"] = plus_di
    df["MINUS_DI"] = minus_di
    df["ADX"] = dx.rolling(window=atr_win).mean()
    recent_win = df.tail(min(window_size, len(df)))
    support = float(recent_win["Low"].min())
    resistance = float(recent_win["High"].max())
    prev_bar = df.iloc[-2] if len(df) >= 2 else df.iloc[-1]
    p_high = float(prev_bar["High"])
    p_low = float(prev_bar["Low"])
    p_close = float(prev_bar["Close"])
    pp = (p_high + p_low + p_close) / 3.0
    pivots = {"PP": pp, "R1": (2.0 * pp) - p_low, "S1": (2.0 * pp) - p_high, "R2": pp + (p_high - p_low), "S2": pp - (p_high - p_low)}
    latest = df.iloc[-1]
    prev = df.iloc[-2] if len(df) >= 2 else latest
    latest_close = float(latest["Close"])
    prev_close_val = float(prev["Close"])
    change = latest_close - prev_close_val
    pct_change = (change / prev_close_val) * 100 if prev_close_val else 0.0
    daily_df = df["Close"].resample("1D").last().dropna()
    if len(daily_df) >= 2:
        today_usd = float(daily_df.iloc[-1])
        prev_day_usd = float(daily_df.iloc[-2])
    else:
        today_usd = latest_close
        prev_day_usd = float(df["Open"].iloc[-1])
    today_diff_usd = today_usd - prev_day_usd
    today_diff_pct = (today_diff_usd / prev_day_usd) * 100 if prev_day_usd else 0.0
    ai_score, ai_reasons = compute_ai_signal_score(latest)
    bt_count, bt_win_rate, bt_avg_ret = estimate_historical_win_rate(df, horizon_bars=12)
    summary = {
        "latest_close": latest_close, "change": change, "pct_change": pct_change,
        "today_usd": today_usd, "prev_day_usd": prev_day_usd, "today_diff_usd": today_diff_usd, "today_diff_pct": today_diff_pct,
        "support": support, "resistance": resistance, "pivots": pivots, "has_vol_data": has_vol_data,
        "rsi": float(latest["RSI"]) if pd.notna(latest["RSI"]) else None,
        "macd": float(latest["MACD"]) if pd.notna(latest["MACD"]) else None,
        "macd_signal": float(latest["MACD_SIGNAL"]) if pd.notna(latest["MACD_SIGNAL"]) else None,
        "stoch_k": float(latest["STOCH_K"]) if pd.notna(latest["STOCH_K"]) else None,
        "stoch_d": float(latest["STOCH_D"]) if pd.notna(latest["STOCH_D"]) else None,
        "atr": float(latest["ATR"]) if pd.notna(latest["ATR"]) else max(latest_close * 0.008, 1.0),
        "adx": float(latest["ADX"]) if pd.notna(latest["ADX"]) else None,
        "sma_20": float(latest["SMA_20"]) if pd.notna(latest["SMA_20"]) else None,
        "sma_50": float(latest["SMA_50"]) if pd.notna(latest["SMA_50"]) else None,
        "sma_200": float(latest["SMA_200"]) if pd.notna(latest["SMA_200"]) else None,
        "sma200_actual_bars": len(df) >= 200, "ai_score": ai_score, "ai_reasons": ai_reasons,
        "bt_count": bt_count, "bt_win_rate": bt_win_rate, "bt_avg_ret": bt_avg_ret,
        "last_bar_time": df.index[-1].strftime("%Y-%m-%d %H:%M:%S"), "fetched_at": time.strftime("%H:%M:%S"),
    }
    return df, summary

@st.cache_data(ttl=20, show_spinner=False)
def get_usd_thb():
    for iv in ("5m", "1d"):
        fx = yf.download("USDTHB=X", period="5d", interval=iv, progress=False)
        if isinstance(fx.columns, pd.MultiIndex):
            fx.columns = fx.columns.get_level_values(0)
        if not fx.empty and not fx["Close"].dropna().empty:
            return float(fx["Close"].dropna().iloc[-1])
    return None

@st.cache_data(ttl=20, show_spinner=False)
def fetch_pair_series(sym: str, hist_period: str, bar_interval: str):
    pair_df = yf.download(sym, period=hist_period, interval=bar_interval, progress=False)
    if isinstance(pair_df.columns, pd.MultiIndex):
        pair_df.columns = pair_df.columns.get_level_values(0)
    pair_df = pair_df.dropna(subset=["Close"]).copy()
    if pair_df.empty:
        return None
    if getattr(pair_df.index, "tz", None) is None:
        pair_df.index = pair_df.index.tz_localize("UTC").tz_convert("Asia/Bangkok")
    else:
        pair_df.index = pair_df.index.tz_convert("Asia/Bangkok")
    return pair_df

ai_left_placeholder = st.sidebar.empty()

def render_ai_left_panel(summary: dict, levels: dict, fx_rate, is_gold_spot: bool, ai_entry_val: float, ai_tp_val: float, ai_sl_val: float, sr_alerts):
    with ai_left_placeholder.container():
        with st.container(border=True):
            st.markdown("### 🤖 AI แนวโน้ม")
            st.caption(f"Live • {summary['last_bar_time']}")
            score = levels["score"]
            st.metric("AI Score", f"{score:+.1f} / 100")
            st.progress(float(np.clip((score + 100) / 200, 0.0, 1.0)))
            if score >= 25:
                st.success(levels["title"])
            elif score <= -25:
                st.error(levels["title"])
            else:
                st.warning(levels["title"])
            close_val = summary["latest_close"]
            sma20 = summary["sma_20"]
            sma50 = summary["sma_50"]
            if sma20 is not None and sma50 is not None:
                if close_val > sma20 > sma50:
                    st.markdown("**แนวโน้ม:** 📈 ขาขึ้น")
                elif close_val < sma20 < sma50:
                    st.markdown("**แนวโน้ม:** 📉 ขาลง")
                else:
                    st.markdown("**แนวโน้ม:** ➡ ไซด์เวย์")
            c1, c2 = st.columns(2)
            c1.metric("Entry", f"{ai_entry_val:,.2f}")
            c2.metric("TP", f"{ai_tp_val:,.2f}")
            c3, c4 = st.columns(2)
            c3.metric("SL", f"{ai_sl_val:,.2f}")
            risk = abs(ai_entry_val - ai_sl_val)
            reward = abs(ai_tp_val - ai_entry_val)
            rr = (reward / risk) if risk > 0 else 0.0
            c4.metric("R:R", f"1 : {rr:.2f}")
            if fx_rate:
                tp_thb = to_thb_value(ai_tp_val, fx_rate, is_gold_spot)
                st.caption(f"TP ~{tp_thb:,.0f} บาท")
            if sr_alerts:
                st.warning("🔔 " + sr_alerts[0]["msg"])
            with st.expander("เหตุผล AI"):
                for r in summary["ai_reasons"]:
                    st.write(f"• {r}")

h1, h2 = st.columns([3, 1])
with h1:
    st.title("🥇 Gold & Crypto AI")
    st.caption("ดูแนวโน้ม เข้าซื้อขาย ด้วย AI ง่ายๆ ในหน้าเดียว")
with h2:
    st.markdown("<div style='text-align:right; padding-top:18px;'><span style='background:#DCFCE7; color:#166534; padding:6px 12px; border-radius:999px; font-size:13px;'>● LIVE</span></div>", unsafe_allow_html=True)

with st.sidebar:
    st.markdown("### สินทรัพย์")
    asset_category = st.radio("ประเภท", options=["gold", "crypto"], format_func=lambda x: "🥇 ทองคำ" if x == "gold" else "🪙 คริปโต", index=0, horizontal=True)
    if asset_category == "gold":
        gold_keys = list(GOLD_PRESETS.keys()) + ["กำหนดเอง..."]
        preset_ticker = st.selectbox("เลือกทองคำ", options=gold_keys, format_func=lambda x: GOLD_PRESETS.get(x, "พิมพ์เอง..."), key="gold_preset")
        if preset_ticker == "กำหนดเอง...":
            custom_gold = st.text_input("Ticker", value="GC=F", key="custom_gold_input").strip().upper()
            ticker = custom_gold if custom_gold else "GC=F"
        else:
            ticker = preset_ticker
    else:
        available_coins = list(dict.fromkeys(DEFAULT_CRYPTO_COINS + st.session_state.custom_coins))
        if st.session_state.selected_coin not in available_coins:
            st.session_state.selected_coin = available_coins[0]
        ticker = st.selectbox("เลือกเหรียญ", options=available_coins, index=available_coins.index(st.session_state.selected_coin), key="selected_coin")
        with st.expander("➕ เพิ่มเหรียญ"):
            new_coin_input = st.text_input("ชื่อเหรียญ เช่น DOGE", value="", key="new_coin_input")
            if st.button("เพิ่ม", use_container_width=True):
                norm_coin = normalize_crypto_symbol(new_coin_input)
                if norm_coin:
                    if norm_coin not in DEFAULT_CRYPTO_COINS and norm_coin not in st.session_state.custom_coins:
                        st.session_state.custom_coins.append(norm_coin)
                    st.session_state["pending_coin"] = norm_coin
                    st.success(f"เพิ่ม {norm_coin} แล้ว")
                    st.rerun()
        with st.expander("🗑 ลบเหรียญ"):
            if st.session_state.custom_coins:
                coin_to_del = st.selectbox("เลือกเหรียญที่จะลบ", options=st.session_state.custom_coins, key="coin_to_del")
                if st.button("ลบ", use_container_width=True):
                    st.session_state.custom_coins.remove(coin_to_del)
                    if st.session_state.selected_coin == coin_to_del:
                        st.session_state["pending_coin"] = "BTC-USD"
                    st.rerun()
    st.markdown("### ช่วงเวลา")
    mode = st.radio("โหมด", options=["realtime", "daily"], format_func=lambda x: "⚡ เรียลไทม์" if x == "realtime" else "📅 รายวัน", index=0, horizontal=True)
    if mode == "realtime":
        interval = st.selectbox("แท่งราคา", options=["1m", "5m", "15m", "1h"], index=1)
        period = st.selectbox("ย้อนหลัง", options=["1d", "5d", "1mo"], index=1)
        auto_refresh = st.checkbox("รีเฟรชอัตโนมัติ", value=True)
        refresh_sec = st.slider("รีเฟรชทุก (วินาที)", min_value=15, max_value=300, value=60, step=15)
        lookback_window = st.slider("หาแนวรับต้าน (แท่ง)", min_value=20, max_value=200, value=60, step=10)
    else:
        interval = "1d"
        period = st.selectbox("ย้อนหลัง", options=["3mo", "6mo", "1y", "2y", "5y"], index=2)
        auto_refresh = False
        refresh_sec = 300
        lookback_window = 30

    with st.expander("🔔 แจ้งเตือนแนวรับต้าน", expanded=True):
        enable_alerts = st.checkbox("เปิดแจ้งเตือน", value=True)
        alert_tolerance = st.slider("แจ้งเมื่อห่างแนว ( % )", min_value=0.1, max_value=2.0, value=0.5, step=0.1)
        alert_cooldown = st.slider("พักแจ้งซ้ำ (นาที)", min_value=1, max_value=60, value=15, step=1)
        enable_desktop = st.checkbox("แจ้งเตือนเดสท็อป (ตอนเปิดแอพ)", value=True)
        enable_sound = st.checkbox("เสียงเตือนในหน้าเว็บ", value=True)
        if st.button("🔔 ทดสอบแจ้งเตือน", use_container_width=True):
            send_desktop_notify("ทดสอบ Gold Crypto AI", "แจ้งเตือนทำงานแล้ว ถ้าเห็นข้อความนี้คือพร้อมใช้")
            if enable_sound:
                trigger_browser_alert("ทดสอบแจ้งเตือน", "เสียงและแจ้งเตือนทำงานแล้ว")
            st.success("ส่งทดสอบแล้ว ดูที่มุมขวาล่างของ Windows")

    with st.expander("🤖 ตั้งค่า AI และกำไร"):
        enable_ai_plan = st.checkbox("เปิด AI แผนเทรด", value=True)
        capital_thb = st.number_input("เงินทุน (บาท)", min_value=1000.0, value=100000.0, step=5000.0)
        tp_atr_mult = st.slider("TP x ATR", min_value=1.0, max_value=5.0, value=2.4, step=0.2)
        sl_atr_mult = st.slider("SL x ATR", min_value=0.5, max_value=3.0, value=1.2, step=0.1)
        show_ai_lines_on_chart = st.checkbox("แสดงเส้น Entry / TP / SL", value=True)
    with st.expander("📈 ตั้งค่ากราฟ"):
        chart_type = st.radio("รูปแบบ", options=["line", "candlestick", "bar"], format_func=lambda x: "เส้น" if x == "line" else "แท่งเทียน" if x == "candlestick" else "แท่ง OHLC", index=0, horizontal=True)
        selected_overlays = st.multiselect("เส้นบนกราฟ", options=OVERLAY_OPTIONS, default=["SMA 20", "SMA 50", "SMA 200", "Auto Support/Resistance"])
        selected_panels = st.multiselect("แผงล่าง", options=PANEL_OPTIONS, default=["RSI (14)", "MACD (12, 26, 9)"])
    with st.expander("🎯 ระดับราคาเอง"):
        use_custom_levels = st.checkbox("กำหนดแนวรับต้านเอง", value=False)
        custom_res = st.number_input("แนวต้าน (USD)", min_value=0.0, value=3700.0, step=10.0) if use_custom_levels else None
        custom_sup = st.number_input("แนวรับ (USD)", min_value=0.0, value=3514.0, step=10.0) if use_custom_levels else None
    show_thb = st.checkbox("แสดงเป็นเงินบาท", value=True)
    show_gold_btc_compare = st.checkbox("เปรียบเทียบทอง vs BTC", value=True)
    run_btn = st.button("🔄 ดึงข้อมูลใหม่", type="primary", use_container_width=True)

def build_ai_trade_plan(summary: dict, fx_rate, is_gold_spot: bool, levels: dict):
    score = summary["ai_score"]
    side = levels["side"]
    st.markdown("#### แผนเทรด AI")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Score", f"{score:+.1f}")
    c2.metric("Entry", f"{levels['entry']:,.2f}")
    c3.metric("TP", f"{levels['tp']:,.2f}")
    c4.metric("SL", f"{levels['sl']:,.2f}")
    st.info(levels["title"])
    p1, p2, p3 = st.columns(3)
    entry_input = p1.number_input("Entry (USD)", min_value=0.01, value=float(st.session_state.get("ai_entry", levels["entry"])), step=1.0, key="ai_entry")
    tp_input = p2.number_input("TP (USD)", min_value=0.01, value=float(st.session_state.get("ai_tp", levels["tp"])), step=1.0, key="ai_tp")
    sl_input = p3.number_input("SL (USD)", min_value=0.01, value=float(st.session_state.get("ai_sl", levels["sl"])), step=1.0, key="ai_sl")
    if side == "LONG":
        profit_pct = ((tp_input - entry_input) / entry_input) * 100.0 if entry_input else 0.0
        loss_pct = ((sl_input - entry_input) / entry_input) * 100.0 if entry_input else 0.0
    else:
        profit_pct = ((entry_input - tp_input) / entry_input) * 100.0 if entry_input else 0.0
        loss_pct = ((entry_input - sl_input) / entry_input) * 100.0 if entry_input else 0.0
    est_profit_thb = capital_thb * (profit_pct / 100.0)
    est_loss_thb = capital_thb * (loss_pct / 100.0)
    risk_dist = abs(entry_input - sl_input)
    reward_dist = abs(tp_input - entry_input)
    rr_ratio = (reward_dist / risk_dist) if risk_dist > 0 else 0.0
    k1, k2, k3 = st.columns(3)
    k1.metric("กำไรถ้าถึง TP", f"{est_profit_thb:+,.0f} บาท", delta=f"{profit_pct:+.2f}%")
    k2.metric("ขาดทุนถ้าหลุด SL", f"{est_loss_thb:+,.0f} บาท", delta=f"{loss_pct:+.2f}%")
    k3.metric("R:R", f"1 : {rr_ratio:.2f}")
    if fx_rate:
        st.caption(f"TP เทียบเท่า ~{to_thb_value(tp_input, fx_rate, is_gold_spot):,.0f} บาท")
    with st.expander("เหตุผล AI"):
        for r in summary["ai_reasons"]:
            st.write(f"• {r}")
    return entry_input, tp_input, sl_input

def render_gold_vs_btc_section(fx_rate):
    gold_df = fetch_pair_series("GC=F", period, interval)
    btc_df = fetch_pair_series("BTC-USD", period, interval)
    if gold_df is None or btc_df is None or gold_df.empty or btc_df.empty:
        st.warning("ดึงข้อมูลเปรียบเทียบไม่ได้")
        return
    gold_now = float(gold_df["Close"].iloc[-1])
    btc_now = float(btc_df["Close"].iloc[-1])
    g_daily = gold_df["Close"].resample("1D").last().dropna()
    g_today = float(g_daily.iloc[-1]) if len(g_daily) >= 1 else gold_now
    g_prev = float(g_daily.iloc[-2]) if len(g_daily) >= 2 else float(gold_df["Open"].iloc[-1])
    g_diff_pct = ((g_today - g_prev) / g_prev) * 100 if g_prev else 0.0
    b_daily = btc_df["Close"].resample("1D").last().dropna()
    b_today = float(b_daily.iloc[-1]) if len(b_daily) >= 1 else btc_now
    b_prev = float(b_daily.iloc[-2]) if len(b_daily) >= 2 else float(btc_df["Open"].iloc[-1])
    b_diff_pct = ((b_today - b_prev) / b_prev) * 100 if b_prev else 0.0
    rate_val = fx_rate if fx_rate else get_usd_thb()
    spread_pct = b_diff_pct - g_diff_pct
    c1, c2, c3 = st.columns(3)
    if rate_val:
        c1.metric("ทอง 96.5%", f"~{calc_thai_gold_965_per_baht(gold_now, rate_val):,.0f} บาท", delta=f"{g_diff_pct:+.2f}%")
        c2.metric("BTC", f"~{btc_now * rate_val:,.0f} บาท", delta=f"{b_diff_pct:+.2f}%")
    else:
        c1.metric("ทอง", f"{gold_now:,.2f} USD", delta=f"{g_diff_pct:+.2f}%")
        c2.metric("BTC", f"{btc_now:,.2f} USD", delta=f"{b_diff_pct:+.2f}%")
    c3.metric("ส่วนต่าง BTC - Gold", f"{spread_pct:+.2f}%", delta="BTC แรงกว่า" if spread_pct >= 0 else "ทองแกร่งกว่า")
    aligned = pd.DataFrame({"Gold": gold_df["Close"], "BTC": btc_df["Close"]}).dropna()
    if not aligned.empty:
        gold_base = float(aligned["Gold"].iloc[0])
        btc_base = float(aligned["BTC"].iloc[0])
        aligned["Gold_Pct"] = ((aligned["Gold"] - gold_base) / gold_base) * 100.0
        aligned["BTC_Pct"] = ((aligned["BTC"] - btc_base) / btc_base) * 100.0
        aligned["Spread_Pct"] = aligned["BTC_Pct"] - aligned["Gold_Pct"]
        fig2 = go.Figure()
        fig2.add_trace(go.Scatter(x=aligned.index, y=aligned["Gold_Pct"], name="Gold %", line=dict(color="#EAB308", width=2.2)))
        fig2.add_trace(go.Scatter(x=aligned.index, y=aligned["BTC_Pct"], name="BTC %", line=dict(color="#3B82F6", width=2.2)))
        fig2.add_trace(go.Scatter(x=aligned.index, y=aligned["Spread_Pct"], name="Spread", line=dict(color="#10B981", width=1.6, dash="dot")))
        fig2.add_hline(y=0, line_dash="dash", line_color="#94A3B8", opacity=0.6)
        fig2.update_layout(height=360, hovermode="x unified", legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
        st.plotly_chart(fig2, use_container_width=True)

def render_watchlist():
    if asset_category != "crypto" or not st.session_state.custom_coins:
        return
    st.markdown("##### เหรียญที่เพิ่มเอง")
    cols = st.columns(len(st.session_state.custom_coins))
    for col, coin in zip(cols, list(st.session_state.custom_coins)):
        w_df = fetch_pair_series(coin, period, interval)
        with col:
            with st.container(border=True):
                if w_df is not None and not w_df.empty:
                    w_now = float(w_df["Close"].iloc[-1])
                    w_prev = float(w_df["Close"].iloc[-2]) if len(w_df) >= 2 else w_now
                    w_pct = ((w_now - w_prev) / w_prev * 100) if w_prev else 0
                    st.metric(coin, f"{w_now:,.4f}" if w_now < 10 else f"{w_now:,.2f}", delta=f"{w_pct:+.2f}%")
                    if coin != ticker:
                        if st.button("ดูกราฟ", key=f"view_{coin}", use_container_width=True):
                            st.session_state.selected_coin = coin
                            st.rerun()
                    else:
                        st.caption("กำลังดูอยู่")

def render_sr_panel(supports, resistances, price):
    with st.container(border=True):
        st.markdown("### 🧱 แนวรับ แนวต้าน")
        sc1, sc2 = st.columns(2)
        with sc1:
            st.markdown("**🔴 แนวต้าน (ข้างบน)**")
            if resistances:
                for r in resistances:
                    st.write(f"{r['level']:,.2f} • ห่าง {abs(r['dist_pct']):.2f}% • {r['source']} • ชน {r['touches']} ครั้ง • {r['strength']}")
            else:
                st.caption("ไม่มีแนวต้านใกล้ๆ")
        with sc2:
            st.markdown("**🟢 แนวรับ (ข้างล่าง)**")
            if supports:
                for s in supports:
                    st.write(f"{s['level']:,.2f} • ห่าง {abs(s['dist_pct']):.2f}% • {s['source']} • ชน {s['touches']} ครั้ง • {s['strength']}")
            else:
                st.caption("ไม่มีแนวรับใกล้ๆ")
        st.caption(f"ราคาปัจจุบัน {price:,.2f} • ถ้าราคาเข้าใกล้แนวภายใน {alert_tolerance}% จะแจ้งเตือนทันที")

def render_dashboard():
    active_ticker = ticker
    if asset_category == "crypto":
        active_ticker = st.session_state.get("selected_coin", ticker)
    df, summary = fetch_and_analyze(active_ticker, period, interval, lookback_window)
    if df is None or summary is None:
        st.error("ไม่พบข้อมูล ลองเปลี่ยน Ticker หรือช่วงเวลาดูครับ")
        return
    rate = get_usd_thb() if (show_thb or show_gold_btc_compare or enable_ai_plan) else None
    is_gold_spot = asset_category == "gold" and active_ticker in ("GC=F", "XAUUSD=X")
    thb_now = to_thb_value(summary["latest_close"], rate, is_gold_spot) if (show_thb and rate) else None
    levels = compute_ai_levels(summary, tp_atr_mult, sl_atr_mult)
    need_reset = (st.session_state.get("ai_ticker") != active_ticker or st.session_state.get("ai_tp_mult") != tp_atr_mult or st.session_state.get("ai_sl_mult") != sl_atr_mult)
    if need_reset:
        st.session_state["ai_entry"] = float(round(levels["entry"], 2))
        st.session_state["ai_tp"] = float(round(levels["tp"], 2))
        st.session_state["ai_sl"] = float(round(levels["sl"], 2))
        st.session_state["ai_ticker"] = active_ticker
        st.session_state["ai_tp_mult"] = tp_atr_mult
        st.session_state["ai_sl_mult"] = sl_atr_mult
    ai_entry_val = float(st.session_state.get("ai_entry", levels["entry"]))
    ai_tp_val = float(st.session_state.get("ai_tp", levels["tp"]))
    ai_sl_val = float(st.session_state.get("ai_sl", levels["sl"]))

    supports, resistances, _ = compute_sr_levels(df, window=lookback_window)
    sr_alerts = []
    if enable_alerts:
        sr_alerts = check_sr_alerts(summary["latest_close"], supports, resistances, summary, alert_tolerance)
        watch_tickers = list(dict.fromkeys([active_ticker, "GC=F", "BTC-USD", "ETH-USD"] + st.session_state.custom_coins))
        save_watch_config(watch_tickers, alert_tolerance, alert_cooldown)
        for al in sr_alerts:
            key = f"{active_ticker}_{al['kind']}_{al['level']:.2f}"
            last = st.session_state.last_alert_times.get(key, 0)
            if time.time() - last > alert_cooldown * 60:
                st.session_state.last_alert_times[key] = time.time()
                save_alert_to_file({"time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "ticker": active_ticker, "kind": al["kind"], "level": al["level"], "price": summary["latest_close"], "msg": al["msg"]})
                if enable_desktop:
                    send_desktop_notify(f"{active_ticker} แจ้งเตือนแนวรับต้าน", al["msg"])
                if enable_sound:
                    trigger_browser_alert(f"{active_ticker} แนวรับต้าน", al["msg"])
                st.toast(f"🔔 {al['msg']}", icon="🔔")

    render_ai_left_panel(summary, levels, rate, is_gold_spot, ai_entry_val, ai_tp_val, ai_sl_val, sr_alerts)

    if sr_alerts:
        for al in sr_alerts:
            if "break" in al["kind"]:
                st.error(f"🚨 {al['msg']}")
            else:
                st.warning(f"🔔 {al['msg']}")

    k1, k2, k3, k4 = st.columns(4)
    with k1:
        st.metric(f"{active_ticker}", f"{summary['latest_close']:,.2f} USD", delta=f"{summary['change']:+.2f} ({summary['pct_change']:+.2f}%)")
    with k2:
        st.metric("แนวต้าน", f"{summary['resistance']:,.2f}")
    with k3:
        st.metric("แนวรับ", f"{summary['support']:,.2f}")
    with k4:
        st.metric("RSI (14)", f"{summary['rsi']:.1f}" if summary["rsi"] is not None else "N/A")
    if show_thb and rate and thb_now is not None:
        st.caption(f"USD/THB {rate:.2f} • วันนี้ {summary['today_diff_pct']:+.2f}% • มูลค่าล่าสุด ~{thb_now:,.0f} บาท")

    render_sr_panel(supports, resistances, summary["latest_close"])
    render_watchlist()

    with st.container(border=True):
        st.markdown(f"### กราฟ {active_ticker} • {interval}")
        active_panels = [p for p in selected_panels if not (p in ("VWAP", "OBV", "Volume") and not summary["has_vol_data"])]
        rows_count = 1 + len(active_panels)
        if rows_count == 1:
            row_heights = [1.0]
        else:
            sub_h = min(0.18, 0.48 / len(active_panels))
            row_heights = [1.0 - (sub_h * len(active_panels))] + [sub_h] * len(active_panels)
        fig = make_subplots(rows=rows_count, cols=1, shared_xaxes=True, vertical_spacing=0.04, row_heights=row_heights, subplot_titles=(f"{active_ticker} | {interval}", *active_panels))
        if chart_type == "candlestick":
            fig.add_trace(go.Candlestick(x=df.index, open=df["Open"], high=df["High"], low=df["Low"], close=df["Close"], name="Candlestick", increasing_line_color="#16A34A", decreasing_line_color="#DC2626"), row=1, col=1)
        elif chart_type == "bar":
            fig.add_trace(go.Ohlc(x=df.index, open=df["Open"], high=df["High"], low=df["Low"], close=df["Close"], name="OHLC Bar", increasing_line_color="#16A34A", decreasing_line_color="#DC2626"), row=1, col=1)
        else:
            fig.add_trace(go.Scatter(x=df.index, y=df["Close"], name="Close", line=dict(color="#EAB308", width=2.2)), row=1, col=1)
        overlay_styles = {"SMA 20": ("SMA_20", dict(color="#2563EB", width=1.5, dash="dash")), "SMA 50": ("SMA_50", dict(color="#DC2626", width=1.5, dash="dash")), "SMA 200": ("SMA_200", dict(color="#7C3AED", width=2.0)), "EMA 20": ("EMA_20", dict(color="#06B6D4", width=1.5)), "EMA 50": ("EMA_50", dict(color="#EC4899", width=1.5, dash="dot"))}
        for name, (col_name, line_cfg) in overlay_styles.items():
            if name in selected_overlays and col_name in df.columns:
                fig.add_trace(go.Scatter(x=df.index, y=df[col_name], name=name, line=line_cfg), row=1, col=1)
        if "VWAP" in selected_overlays and summary["has_vol_data"]:
            fig.add_trace(go.Scatter(x=df.index, y=df["VWAP"], name="VWAP", line=dict(color="#F59E0B", width=1.8, dash="longdash")), row=1, col=1)
        if "Bollinger Bands" in selected_overlays:
            fig.add_trace(go.Scatter(x=df.index, y=df["BB_UPPER"], name="BB Upper", line=dict(color="#94A3B8", width=1, dash="dot")), row=1, col=1)
            fig.add_trace(go.Scatter(x=df.index, y=df["BB_LOWER"], name="BB Lower", line=dict(color="#94A3B8", width=1, dash="dot"), fill="tonexty", fillcolor="rgba(148, 163, 184, 0.12)"), row=1, col=1)
        if "Parabolic SAR" in selected_overlays:
            fig.add_trace(go.Scatter(x=df.index, y=df["PSAR"], name="SAR", mode="markers", marker=dict(size=4, color="#14B8A6")), row=1, col=1)
        if "Pivot Points" in selected_overlays:
            for p_label, p_val in summary["pivots"].items():
                fig.add_hline(y=p_val, line_dash="dashdot", line_width=1, opacity=0.65, annotation_text=f"{p_label}: {p_val:,.2f}", row=1, col=1)
        if "Auto Support/Resistance" in selected_overlays:
            fig.add_hline(y=summary["resistance"], line_dash="dot", line_color="#16A34A", annotation_text=f"Res: {summary['resistance']:,.2f}", row=1, col=1)
            fig.add_hline(y=summary["support"], line_dash="dot", line_color="#9333EA", annotation_text=f"Sup: {summary['support']:,.2f}", row=1, col=1)
        for s in supports:
            fig.add_hline(y=s["level"], line_dash="dot", line_color="#16A34A", opacity=0.55, annotation_text=f"Sup {s['level']:,.0f} ({s['touches']}x)", row=1, col=1)
        for r in resistances:
            fig.add_hline(y=r["level"], line_dash="dot", line_color="#DC2626", opacity=0.55, annotation_text=f"Res {r['level']:,.0f} ({r['touches']}x)", row=1, col=1)
        if use_custom_levels:
            if custom_res and custom_res > 0:
                fig.add_hline(y=custom_res, line_dash="dash", line_color="#059669", annotation_text=f"Res: {custom_res:,.2f}", row=1, col=1)
            if custom_sup and custom_sup > 0:
                fig.add_hline(y=custom_sup, line_dash="dash", line_color="#E11D48", annotation_text=f"Sup: {custom_sup:,.2f}", row=1, col=1)
        if enable_ai_plan and show_ai_lines_on_chart:
            fig.add_hline(y=ai_entry_val, line_dash="solid", line_width=1.4, line_color="#2563EB", annotation_text=f"Entry: {ai_entry_val:,.2f}", row=1, col=1)
            fig.add_hline(y=ai_tp_val, line_dash="dash", line_width=1.4, line_color="#16A34A", annotation_text=f"TP: {ai_tp_val:,.2f}", row=1, col=1)
            fig.add_hline(y=ai_sl_val, line_dash="dash", line_width=1.4, line_color="#DC2626", annotation_text=f"SL: {ai_sl_val:,.2f}", row=1, col=1)
        fig.update_yaxes(title_text="Price (USD)", row=1, col=1)
            # --- Panels ด้านล่างกราฟหลัก ---
    for idx, panel_name in enumerate(active_panels, start=2):
        if panel_name == "RSI (14)":
            fig.add_trace(go.Scatter(x=df.index, y=df["RSI"], name="RSI", line=dict(color="#2563EB", width=1.8)), row=idx, col=1)
            fig.add_hline(y=70, line_dash="dash", line_color="#DC2626", opacity=0.6, row=idx, col=1)
            fig.add_hline(y=30, line_dash="dash", line_color="#16A34A", opacity=0.6, row=idx, col=1)
            fig.update_yaxes(title_text="RSI", range=[0, 100], row=idx, col=1)
        elif panel_name == "Stoch (14,3,3)":
            fig.add_trace(go.Scatter(x=df.index, y=df["STOCH_K"], name="%K", line=dict(color="#2563EB", width=1.6)), row=idx, col=1)
            fig.add_trace(go.Scatter(x=df.index, y=df["STOCH_D"], name="%D", line=dict(color="#DC2626", width=1.6)), row=idx, col=1)
            fig.add_hline(y=80, line_dash="dash", line_color="#DC2626", opacity=0.5, row=idx, col=1)
            fig.add_hline(y=20, line_dash="dash", line_color="#16A34A", opacity=0.5, row=idx, col=1)
            fig.update_yaxes(title_text="Stoch", range=[0, 100], row=idx, col=1)
        elif panel_name == "ATR (14)":
            fig.add_trace(go.Scatter(x=df.index, y=df["ATR"], name="ATR", line=dict(color="#8B5CF6", width=1.8)), row=idx, col=1)
            fig.update_yaxes(title_text="ATR", row=idx, col=1)
        elif panel_name == "ADX (14)":
            fig.add_trace(go.Scatter(x=df.index, y=df["ADX"], name="ADX", line=dict(color="#111827", width=2.0)), row=idx, col=1)
            fig.add_trace(go.Scatter(x=df.index, y=df["PLUS_DI"], name="+DI", line=dict(color="#16A34A", width=1.3, dash="dot")), row=idx, col=1)
            fig.add_trace(go.Scatter(x=df.index, y=df["MINUS_DI"], name="-DI", line=dict(color="#DC2626", width=1.3, dash="dot")), row=idx, col=1)
            fig.add_hline(y=25, line_dash="dash", line_color="#6B7280", opacity=0.6, row=idx, col=1)
            fig.update_yaxes(title_text="ADX", range=[0, 100], row=idx, col=1)
        elif panel_name == "OBV":
            fig.add_trace(go.Scatter(x=df.index, y=df["OBV"], name="OBV", line=dict(color="#0D9488", width=1.8)), row=idx, col=1)
            fig.update_yaxes(title_text="OBV", row=idx, col=1)
        elif panel_name == "Volume":
            fig.add_trace(go.Bar(x=df.index, y=df["Volume"], name="Volume", marker_color="#64748B", opacity=0.6), row=idx, col=1)
            fig.update_yaxes(title_text="Vol", row=idx, col=1)

    fig.update_layout(height=520 + (len(active_panels) * 130), hovermode="x unified", xaxis_rangeslider_visible=False, legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
    st.plotly_chart(fig, use_container_width=True)
    st.caption(f"แท่งล่าสุด {summary['last_bar_time']} • อัปเดต {summary['fetched_at']} • ATR ±{summary['atr']:.2f}")

    tab1, tab2, tab3, tab4 = st.tabs(["🤖 AI แผนเทรด", "⚖ ทอง vs BTC", "🔔 ประวัติแจ้งเตือน", "📊 ข้อมูล"])
    with tab1:
        if enable_ai_plan:
            build_ai_trade_plan(summary, rate, is_gold_spot, levels)
        else:
            st.caption("เปิด AI แผนเทรดในฝั่งซ้าย")
    with tab2:
        if show_gold_btc_compare:
            render_gold_vs_btc_section(rate)
    with tab3:
        hist = load_alert_history()
        if hist:
            st.dataframe(pd.DataFrame(hist), use_container_width=True)
            if st.button("ล้างประวัติแจ้งเตือน"):
                try:
                    os.remove(ALERT_FILE)
                except Exception:
                    pass
                st.rerun()
        else:
            st.caption("ยังไม่มีแจ้งเตือน ระบบจะแจ้งเมื่อราคาเข้าใกล้แนวหรือทะลุแนว")
            st.caption("ถ้าอยากได้แจ้งเตือนตอนปิดโปรแกรม ให้รันไฟล์ alert_watcher.py ค้างไว้")
    with tab4:
        daily_ohlc = df.resample("1D").agg({"Open": "first", "High": "max", "Low": "min", "Close": "last"}).dropna(subset=["Close"])
        daily_ohlc["Diff_USD"] = daily_ohlc["Close"].diff()
        daily_ohlc["Diff_Pct"] = daily_ohlc["Close"].pct_change() * 100.0
        fx_ref = rate if rate else get_usd_thb()
        if fx_ref:
            daily_ohlc["Close_THB"] = daily_ohlc["Close"].apply(lambda x: to_thb_value(float(x), fx_ref, is_gold_spot))
            daily_ohlc["Diff_THB"] = daily_ohlc["Close_THB"].diff()
        show_daily = daily_ohlc.tail(10).sort_index(ascending=False).copy()
        show_daily.index = show_daily.index.strftime("%Y-%m-%d")
        fmt_dict = {"Open": "{:,.2f}", "High": "{:,.2f}", "Low": "{:,.2f}", "Close": "{:,.2f}", "Diff_USD": "{:+,.2f}", "Diff_Pct": "{:+.2f}%"}
        if "Close_THB" in show_daily.columns:
            fmt_dict["Close_THB"] = "{:,.0f}"
            fmt_dict["Diff_THB"] = "{:+,.0f}"
        st.dataframe(show_daily.style.format(fmt_dict), use_container_width=True)

if not ticker:
    st.warning("กรุณากรอก Ticker ก่อนครับ")
    st.stop()
if run_btn:
    fetch_and_analyze.clear()
    get_usd_thb.clear()
    fetch_pair_series.clear()
    st.rerun()
if mode == "realtime" and auto_refresh:
    @st.fragment(run_every=refresh_sec)
    def live_fragment():
        render_dashboard()
    live_fragment()
else:
    render_dashboard()
