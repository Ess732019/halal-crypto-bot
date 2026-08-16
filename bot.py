import ccxt
import requests
import os
from datetime import datetime

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
CHAT_ID = "7231266337"

halal_coins = ['BTC/USDT', 'ETH/USDT', 'SOL/USDT', 'XRP/USDT', 'ADA/USDT']
exchange = ccxt.kraken()

TAKE_PROFIT = 0.04
STOP_LOSS = 0.025


def send_telegram(message):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        data = {"chat_id": CHAT_ID, "text": message}
        requests.post(url, data=data, timeout=10)
    except:
        pass


def calculate_rsi(closes, period=14):
    if len(closes) < period + 1:
        return 50
    gains, losses = [], []
    for i in range(1, len(closes)):
        diff = closes[i] - closes[i - 1]
        gains.append(max(diff, 0))
        losses.append(abs(min(diff, 0)))
    avg_gain = sum(gains[-period:]) / period
    avg_loss = sum(losses[-period:]) / period
    if avg_loss == 0:
        return 100
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


def calculate_ema(closes, period):
    if len(closes) < period:
        return closes[-1]
    multiplier = 2 / (period + 1)
    ema = sum(closes[:period]) / period
    for price in closes[period:]:
        ema = (price - ema) * multiplier + ema
    return ema


def calculate_macd(closes):
    ema12 = calculate_ema(closes, 12)
    ema26 = calculate_ema(closes, 26)
    macd_line = ema12 - ema26
    # Simplified signal line using last 9 MACD-like estimate
    ema9_of_close = calculate_ema(closes[-9:], 9) if len(closes) >= 9 else macd_line
    return macd_line, macd_line - (ema9_of_close - calculate_ema(closes, 26))


def calculate_bollinger(closes, period=20, num_std=2):
    if len(closes) < period:
        period = len(closes)
    recent = closes[-period:]
    sma = sum(recent) / period
    variance = sum((p - sma) ** 2 for p in recent) / period
    std = variance ** 0.5
    upper = sma + (num_std * std)
    lower = sma - (num_std * std)
    return upper, sma, lower


def analyze_coin(symbol):
    ticker = exchange.fetch_ticker(symbol)
    price = ticker['last']
    volume = ticker.get('quoteVolume', 0)

    ohlcv = exchange.fetch_ohlcv(symbol, timeframe='1h', limit=100)
    closes = [c[4] for c in ohlcv]

    rsi = calculate_rsi(closes)
    ema20 = calculate_ema(closes, 20)
    ema50 = calculate_ema(closes, 50)
    macd_line, macd_signal = calculate_macd(closes)
    bb_upper, bb_mid, bb_lower = calculate_bollinger(closes)

    volume_strength = "عادي"
    if volume > 5_000_000:
        volume_strength = "قوي جداً"
    elif volume > 1_000_000:
        volume_strength = "قوي"

    trend = "صاعد" if ema20 > ema50 else "هابط"

    # ---- Scoring System (0 to 5) ----
    score = 0
    reasons = []

    if rsi < 40:
        score += 1
        reasons.append("RSI منخفض")
    if trend == "صاعد":
        score += 1
        reasons.append("اتجاه صاعد (EMA)")
    if macd_line > macd_signal:
        score += 1
        reasons.append("MACD إيجابي")
    if price <= bb_lower * 1.01:
        score += 1
        reasons.append("قرب الحد السفلي لبولينجر")
    if volume_strength in ["قوي", "قوي جداً"]:
        score += 1
        reasons.append("حجم تداول قوي")

    return {
        "symbol": symbol, "price": price, "rsi": rsi, "trend": trend,
        "macd_line": macd_line, "macd_signal": macd_signal,
        "volume_strength": volume_strength, "score": score, "reasons": reasons
    }


print(f"⏰ فحص السوق: {datetime.now().strftime('%Y-%m-%d %H:%M')}")

for symbol in halal_coins:
    try:
        r = analyze_coin(symbol)
        print(f"{r['symbol']} | ${r['price']:.4f} | RSI:{r['rsi']:.1f} | {r['trend']} | {r['volume_strength']} | نقاط: {r['score']}/5")

        if r["score"] >= 4:
            strength = "قوية جداً"
        elif r["score"] == 3:
            strength = "متوسطة"
        else:
            strength = None

        if strength:
            tp = r["price"] * (1 + TAKE_PROFIT)
            sl = r["price"] * (1 - STOP_LOSS)
            msg = f"""🟢 توصية شراء ({strength}) — {r['score']}/5

العملة: {r['symbol']}
السعر: ${r['price']:.4f}
RSI: {r['rsi']:.1f}
الاتجاه: {r['trend']}
الحجم: {r['volume_strength']}
أسباب الإشارة: {', '.join(r['reasons'])}

هدف الربح: ${tp:.4f}
وقف الخسارة: ${sl:.4f}

⚠️ توصية تحليلية آلية، مش نصيحة استثمارية. راجع قرارك دايمًا."""
            send_telegram(msg)

        elif r["rsi"] > 70:
            send_telegram(f"🔴 تحذير: {r['symbol']} تشبع شرائي (RSI: {r['rsi']:.1f})")

    except Exception as e:
        print(f"خطأ في {symbol}: {e}")

print("تم الفحص")
