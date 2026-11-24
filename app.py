"""
=============================================================================
🤖 AMD + FVG TELEGRAM AUTO-SCANNER BOT (RENDER CLOUD 24/7 EDITION)
Author: Pheara (for MOROKOT)
=============================================================================
"""

import os
import time
import json
import threading
import urllib.request
import urllib.parse
from http.server import HTTPServer, BaseHTTPRequestHandler
from datetime import datetime

# ────────────────── ⚙️ TELEGRAM CONFIG ──────────────────
TELEGRAM_BOT_TOKEN = "8777933137:AAEZH-DwTGCueANp7FMgxXeo7JOEaJ2SlZE"
TELEGRAM_CHAT_ID   = "385316411"

# គូដែលត្រូវស្កេន
SYMBOLS = ["BTC_USDT", "ETH_USDT", "SOL_USDT"]
TIMEFRAME = "5m"

# Strategy Parameters
ACC_LEN = 12
RANGE_MULT = 3.0
MAX_SWEEP_ATR = 1.5
DISP_MULT = 0.5

# ────────────────── 📲 TELEGRAM SENDER ──────────────────
def send_telegram(text):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text,
        "parse_mode": "HTML"
    }
    data = json.dumps(payload).encode('utf-8')
    req = urllib.request.Request(url, data=data, headers={'Content-Type': 'application/json'})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status == 200
    except Exception as e:
        print(f"❌ Telegram Error: {e}")
        return False

# ────────────────── 📊 DATA FETCHER (GATE.IO) ──────────────────
def fetch_candles(symbol, interval=TIMEFRAME, limit=100):
    url = f"https://api.gateio.ws/api/v4/spot/candlesticks?currency_pair={symbol}&interval={interval}&limit={limit}"
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    try:
        with urllib.request.urlopen(req, timeout=8) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            candles = []
            for d in data:
                candles.append({
                    "time": int(d[0]),
                    "open": float(d[5]),
                    "high": float(d[3]),
                    "low": float(d[4]),
                    "close": float(d[2]),
                })
            return candles
    except Exception as e:
        print(f"❌ Fetch Error ({symbol}): {e}")
    return None

def calc_atr(candles, period=14):
    if len(candles) < period + 1:
        return 0.0
    trs = []
    for i in range(1, len(candles)):
        h = candles[i]["high"]
        l = candles[i]["low"]
        prev_c = candles[i - 1]["close"]
        trs.append(max(h - l, abs(h - prev_c), abs(l - prev_c)))
    return sum(trs[-period:]) / period

# ────────────────── 🧠 AMD + FVG SCANNER ──────────────────
last_alerted_candle = {}

def scan_symbol(symbol):
    candles = fetch_candles(symbol, TIMEFRAME)
    if not candles or len(candles) < ACC_LEN + 15:
        return

    cur = candles[-1]
    prev1 = candles[-2]
    prev2 = candles[-3]
    atr = calc_atr(candles, 14)
    if atr == 0:
        return

    recent_highs = [c["high"] for c in candles[-ACC_LEN:]]
    recent_lows  = [c["low"]  for c in candles[-ACC_LEN:]]
    rng_hi = max(recent_highs)
    rng_lo = min(recent_lows)
    h = rng_hi - rng_lo

    # 1. Accumulation Check
    if h > (atr * RANGE_MULT):
        return

    # 2. Manipulation Sweep Check
    lookback = candles[-10:]
    max_h = max([c["high"] for c in lookback])
    min_l = min([c["low"] for c in lookback])

    bear_sweep = max_h > rng_hi and (max_h - rng_hi) <= (atr * MAX_SWEEP_ATR)
    bull_sweep = min_l < rng_lo and (rng_lo - min_l) <= (atr * MAX_SWEEP_ATR)

    # 3. FVG Displacement Check
    bear_fvg = (cur["high"] < prev2["low"]) and (prev1["close"] < prev1["open"])
    bull_fvg = (cur["low"] > prev2["high"]) and (prev1["close"] > prev1["open"])
    body_ok  = abs(prev1["close"] - prev1["open"]) >= (atr * DISP_MULT)

    sig_side = None
    sl = None
    target = None

    if bear_sweep and bear_fvg and body_ok and (cur["close"] < rng_hi):
        sig_side = "SELL"
        sl = max_h
        target = rng_lo - (h * 1.5)
    elif bull_sweep and bull_fvg and body_ok and (cur["close"] > rng_lo):
        sig_side = "BUY"
        sl = min_l
        target = rng_hi + (h * 1.5)

    if sig_side:
        if last_alerted_candle.get(symbol) == cur["time"]:
            return

        last_alerted_candle[symbol] = cur["time"]

        risk = abs(cur["close"] - sl)
        reward = abs(target - cur["close"])
        rr = round(reward / risk, 2) if risk > 0 else 2.0

        icon = "🔴 SELL" if sig_side == "SELL" else "🟢 BUY"
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        sym_clean = symbol.replace("_", "/")

        msg = (
            f"🎯 <b>AMD + FVG LIVE SIGNAL ALERT!</b> 🎯\n\n"
            f"📊 <b>Pair:</b> <code>{sym_clean}</code> ({TIMEFRAME})\n"
            f"⚡ <b>Signal:</b> <b>{icon}</b>\n"
            f"💵 <b>Entry:</b> <code>${cur['close']}</code>\n"
            f"🛑 <b>Stop Loss:</b> <code>${round(sl, 2)}</code>\n"
            f"🎯 <b>Target (TP):</b> <code>${round(target, 2)}</code>\n"
            f"⚖️ <b>Risk:Reward:</b> <code>1:{rr}</code>\n"
            f"⏰ <b>Time:</b> {now_str}\n\n"
            f"☁️ <i>Running 24/7 on Cloud (Render) - by Pheara</i>"
        )
        print(f"\n[🚀 SIGNAL FOUND] {sym_clean} {sig_side} @ ${cur['close']} (RR: 1:{rr})")
        send_telegram(msg)

def scanner_loop():
    print(f"🚀 Scanner Thread Started! Monitoring: {', '.join(SYMBOLS)}")
    while True:
        try:
            for s in SYMBOLS:
                scan_symbol(s)
            time.sleep(15)
        except Exception as e:
            print(f"Scanner Loop Error: {e}")
            time.sleep(15)

# ────────────────── 🌐 HTTP DUMMY SERVER FOR RENDER ──────────────────
# Render requires a web port open on Free Tier to keep the service healthy
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.end_headers()
        html = (
            "<html><body style='font-family:sans-serif; background:#131722; color:#fff; text-align:center; padding-top:50px;'>"
            "<h2>🤖 Morokot AMD + FVG Bot is Active 24/7!</h2>"
            "<p style='color:#00e676;'>Cloud Service Status: HEALTHY & ONLINE</p>"
            "</body></html>"
        )
        self.wfile.write(html.encode('utf-8'))

    def log_message(self, format, *args):
        pass

def run_web_server():
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(("0.0.0.0", port), HealthCheckHandler)
    print(f"🌐 Web Server listening on port {port} (Render Health Check OK)")
    server.serve_forever()

if __name__ == '__main__':
    print("=" * 60)
    print("🤖 STARTING MOROKOT TELEGRAM BOT (RENDER CLOUD)")
    print("=" * 60)

    # 1. Start market scanner in background thread
    t = threading.Thread(target=scanner_loop, daemon=True)
    t.start()

    # 2. Send startup notification to MOROKOT Telegram
    send_telegram("☁️ <b>Bot ត្រូវបានដាក់ឱ្យដំណើរការលើ Cloud ២៤/៧ រួចរាល់ហើយ!</b>\n\nឥឡូវនេះ ទោះបីជាបងបិទកុំព្យូទ័រក៏ដោយ ក៏ Bot នៅតែបន្តស្កេនទីផ្សារ និងផ្ញើ Signal មកទូរស័ព្ទដៃរបស់បងជានិច្ច។")

    # 3. Run Web Server on main thread (satisfies Render)
    run_web_server()
