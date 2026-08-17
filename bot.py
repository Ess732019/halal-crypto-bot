import ccxt
import requests
import os
from datetime import datetime

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
CHAT_ID = "7231266337"

halal_coins = ['BTC/USDT', 'ETH/USDT', 'SOL/USDT', 'XRP/USDT', 'ADA/USDT']
exchange = ccxt.kraken()

TAKE_PROFIT = 0.025   # 2.5%
STOP_LOSS = 0.015     # 1.5%


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
    signal = calculate_ema(closes[-9:], 9) if len(closes) >= 9 else macd_line
    return macd_line, signal


def calculate_bollinger(closes, period=20, num_std=2):
    if len(closes) < period:
        period = len(closes)
    recent = closes[-period:]
    sma = sum(recent) / period
    variance = sum((p - sma) ** 2 for p in recent) / period
    std = variance ** 0.5
    return sma + (num_std * std), sma, sma - (num_std * std)


def calculate_adx(highs, lows, closes, period=14):
    if len(closes) < period + 1:
        return 20
    tr_list, plus_dm, minus_dm = [], [], []
    for i in range(1, len(closes)):
        tr = max(highs[i] - lows[i], abs(highs[i] - closes[i-1]), abs(lows[i] - closes[i-1]))
        tr_list.append(tr)
        up = highs[i] - highs[i-1]
        down = lows[i-1] - lows[i]
        plus_dm.append(up if up > down and up > 0 else 0)
        minus_dm.append(down if down > up and down > 0 else 0)

    atr = sum(tr_list[-period:]) / period
    plus_di = 100 * (sum(plus_dm[-period:]) / period) / atr if atr != 0 else 0
    minus_di = 100 * (sum(minus_dm[-period:]) / period) / atr if atr != 0 else 0
    dx = 100 * abs(plus_di - minus_di) / (plus_di + minus_di) if (plus_di + minus_di) != 0 else 0
    return dx


def get_btc_trend():
    try:
        ohlcv = exchange.fetch_ohlcv('BTC/USDT', timeframe='1h', limit=50)
        closes = [c[4] for c in ohlcv]
        ema20 = calculate_ema(closes, 20)
        ema50 = calculate_ema(closes, 50)
        return "صاعد" if ema20 > ema50 else "هابط"
    except:
        return "غير محدد"


def analyze_coin(symbol, btc_trend):
    ticker = exchange.fetch_ticker(symbol)
    price = ticker['last']
    volume = ticker.get('quoteVolume', 0)

    ohlcv = exchange.fetch_ohlcv(symbol, timeframe='1h', limit=100)
    closes = [c[4] for c in ohlcv]
    highs = [c[2] for c in ohlcv]
    lows = [c[3] for c in ohlcv]

    rsi = calculate_rsi(closes)
    ema20 = calculate_ema(closes, 20)
    ema50 = calculate_ema(closes, 50)
    macd_line, macd_signal = calculate_macd(closes)
    bb_upper, bb_mid, bb_lower = calculate_bollinger(closes)
    adx = calculate_adx(highs, lows, closes)

    volume_strength = "عادي"
    if volume > 5_000_000:
        volume_strength = "قوي جداً"
    elif volume > 1_000_000:
        volume_strength = "قوي"

    trend = "صاعد" if ema20 > ema50 else "هابط"

    # ---- Scoring (0 to 5) ----
    score = 0
    reasons = []

    if rsi < 40:
        score += 1
        reasons.append("RSI منخفض")
    if trend == "صاعد":
        score += 1
        reasons.append("اتجاه صاعد")
    if macd_line > macd_signal:
        score += 1
        reasons.append("MACD إيجابي")
    if price <= bb_lower * 1.015:
        score += 1
        reasons.append("قرب بولينجر السفلي")
    if volume_strength in ["قوي", "قوي جداً"]:
        score += 1
        reasons.append("حجم قوي")

    return {
        "symbol": symbol, "price": price, "rsi": rsi, "trend": trend,
        "adx": adx, "volume_strength": volume_strength,
        "score": score, "reasons": reasons, "btc_trend": btc_trend
    }


print(f"⏰ فحص السوق: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
btc_trend = get_btc_trend()
print(f"اتجاه البيتكوين العام: {btc_trend}")

for symbol in halal_coins:
    try:
        r = analyze_coin(symbol, btc_trend)
        print(f"{r['symbol']} | ${r['price']:.4f} | RSI:{r['rsi']:.1f} | ADX:{r['adx']:.1f} | {r['trend']} | نقاط:{r['score']}/5")

        # فلتر 1: منع الشراء في ترند هابط
        if r["trend"] == "هابط":
            if r["score"] >= 3:
                send_telegram(f"⏳ ترقب: {r['symbol']} فيه إشارات لكن الاتجاه هابط حالياً. ننتظر تحول صاعد.")
            continue

        # فلتر 2: اتجاه البيتكوين
        if btc_trend == "هابط" and r["symbol"] != "BTC/USDT":
            if r["score"] >= 4:
                send_telegram(f"⏳ ترقب: {r['symbol']} إشاراته جيدة لكن البيتكوين في اتجاه هابط.")
            continue

        # فلتر 3: ADX ضعيف (اتجاه ضعيف)
        if r["adx"] < 18 and r["score"] >= 3:
            send_telegram(f"⏳ ترقب: {r['symbol']} الاتجاه ضعيف (ADX منخفض).")
            continue

        if r["score"] >= 4:
            strength = "قوية جداً"
        elif r["score"] == 3:
            strength = "متوسطة"
        else:
            strength = None

        if strength:
            buy_price = r["price"]
            tp = buy_price * (1 + TAKE_PROFIT)
            sl = buy_price * (1 - STOP_LOSS)

            msg = f"""🟢 توصية شراء ({strength}) — {r['score']}/5

العملة: {r['symbol']}
RSI: {r['rsi']:.1f} | ADX: {r['adx']:.1f}
الاتجاه: {r['trend']}
الحجم: {r['volume_strength']}
أسباب الإشارة: {', '.join(r['reasons'])}

📥 اشتري عند: ${buy_price:.4f}
🎯 بيع عند: ${tp:.4f}
🛑 وقف خسارة عند: ${sl:.4f}

⚠️ توصية تحليلية آلية، مش نصيحة استثمارية."""
            send_telegram(msg)

        elif r["rsi"] > 70:
            send_telegram(f"🔴 تحذير: {r['symbol']} تشبع شرائي (RSI: {r['rsi']:.1f})")

    except Exception as e:
        print(f"خطأ في {symbol}: {e}")

print("تم الفحص")
