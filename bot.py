import ccxt
import requests
import os
from datetime import datetime, timezone

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
GOOGLE_SCRIPT_URL = os.environ.get("GOOGLE_SCRIPT_URL")  # اختياري
CHAT_ID = "7231266337"

halal_coins = ['BTC/USDT', 'ETH/USDT', 'SOL/USDT', 'XRP/USDT', 'ADA/USDT']
exchange = ccxt.kraken()

COOLDOWN_HOURS = 6  # تحسين 16


# ---------------------------------------------------------
# Telegram
# ---------------------------------------------------------
def send_telegram(message):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        data = {"chat_id": CHAT_ID, "text": message}
        requests.post(url, data=data, timeout=10)
    except:
        pass


# ---------------------------------------------------------
# تحسين 9 و16: Google Sheet — تسجيل، متابعة، وفحص الـ Cooldown
# ---------------------------------------------------------
def sheet_log_recommendation(symbol, entry, tp, sl, score, trend, adx, fear_greed):
    if not GOOGLE_SCRIPT_URL:
        return
    try:
        requests.post(GOOGLE_SCRIPT_URL, json={
            "action": "log", "symbol": symbol, "entry": entry, "tp": tp,
            "sl": sl, "score": score, "trend": trend, "adx": adx,
            "fearGreed": fear_greed
        }, timeout=10)
    except:
        pass


def sheet_get_status():
    """بيرجع (open_trades, last_times) — last_times قاموس {symbol: تاريخ آخر توصية}"""
    if not GOOGLE_SCRIPT_URL:
        return [], {}
    try:
        resp = requests.get(GOOGLE_SCRIPT_URL, timeout=10)
        data = resp.json()
        return data.get("open", []), data.get("lastTimes", {})
    except:
        return [], {}


def is_in_cooldown(symbol, last_times):
    """تحسين 16: بيتأكد هل العملة بعتت توصية خلال آخر COOLDOWN_HOURS ساعة"""
    if symbol not in last_times or not last_times[symbol]:
        return False
    try:
        last_time = datetime.fromisoformat(str(last_times[symbol]).replace("Z", "+00:00"))
        now = datetime.now(timezone.utc)
        hours_passed = (now - last_time).total_seconds() / 3600
        return hours_passed < COOLDOWN_HOURS
    except:
        return False


def sheet_update_trade(trade_id, status, exit_price):
    if not GOOGLE_SCRIPT_URL:
        return
    try:
        requests.post(GOOGLE_SCRIPT_URL, json={
            "action": "update", "id": trade_id,
            "status": status, "exitPrice": exit_price
        }, timeout=10)
    except:
        pass


# ---------------------------------------------------------
# تحسين 6: Fear & Greed Index
# ---------------------------------------------------------
def get_fear_greed():
    try:
        r = requests.get("https://api.alternative.me/fng/?limit=1", timeout=10)
        data = r.json()["data"][0]
        return int(data["value"]), data["value_classification"]
    except:
        return 50, "غير متاح"


# ---------------------------------------------------------
# تحسين 18: هدوء وقت الأحداث الاقتصادية الكبيرة
# ---------------------------------------------------------
def is_near_major_economic_event():
    """بيرجع True لو فيه حدث اقتصادي عالي التأثير قريب (±1 ساعة)"""
    try:
        r = requests.get("https://nfs.faireconomy.media/ff_calendar_thisweek.json", timeout=10)
        events = r.json()
        now = datetime.now(timezone.utc)
        for ev in events:
            if ev.get("impact") != "High":
                continue
            ev_time = datetime.fromisoformat(ev["date"].replace("Z", "+00:00"))
            diff_hours = abs((ev_time - now).total_seconds()) / 3600
            if diff_hours <= 1:
                return True
        return False
    except:
        return False  # لو المصدر مش شغال، البوت يكمل عادي من غير توقف


# ---------------------------------------------------------
# تحسين 19: ساعات السيولة المنخفضة
# ---------------------------------------------------------
def is_low_liquidity_hour():
    hour = datetime.now(timezone.utc).hour
    return 21 <= hour or hour <= 1


# ---------------------------------------------------------
# المؤشرات الفنية (تحسين 1-5، 7، 8)
# ---------------------------------------------------------
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
    return 100 - (100 / (1 + avg_gain / avg_loss))


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
    return sma + num_std * std, sma, sma - num_std * std


def calculate_adx(highs, lows, closes, period=14):
    if len(closes) < period + 1:
        return 20
    tr_list, plus_dm, minus_dm = [], [], []
    for i in range(1, len(closes)):
        tr = max(highs[i] - lows[i], abs(highs[i] - closes[i - 1]), abs(lows[i] - closes[i - 1]))
        tr_list.append(tr)
        up = highs[i] - highs[i - 1]
        down = lows[i - 1] - lows[i]
        plus_dm.append(up if up > down and up > 0 else 0)
        minus_dm.append(down if down > up and down > 0 else 0)
    atr = sum(tr_list[-period:]) / period
    plus_di = 100 * (sum(plus_dm[-period:]) / period) / atr if atr else 0
    minus_di = 100 * (sum(minus_dm[-period:]) / period) / atr if atr else 0
    return 100 * abs(plus_di - minus_di) / (plus_di + minus_di) if (plus_di + minus_di) else 0


def calculate_atr(highs, lows, closes, period=14):
    if len(closes) < period + 1:
        return closes[-1] * 0.02
    tr_list = []
    for i in range(1, len(closes)):
        tr_list.append(max(highs[i] - lows[i], abs(highs[i] - closes[i - 1]), abs(lows[i] - closes[i - 1])))
    return sum(tr_list[-period:]) / period


def get_btc_trend():
    try:
        ohlcv = exchange.fetch_ohlcv('BTC/USDT', timeframe='1h', limit=100)
        closes = [c[4] for c in ohlcv]
        return "صاعد" if calculate_ema(closes, 20) > calculate_ema(closes, 50) else "هابط"
    except:
        return "غير محدد"


# ---------------------------------------------------------
# التحليل الكامل لكل عملة — تحسين 14: نظام نقاط موحّد
# ---------------------------------------------------------
def analyze_coin(symbol, btc_trend, fg_value, low_liquidity):
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
    atr = calculate_atr(highs, lows, closes)

    volume_strength = "عادي"
    if volume > 5_000_000:
        volume_strength = "قوي جداً"
    elif volume > 1_000_000:
        volume_strength = "قوي"

    trend = "صاعد" if ema20 > ema50 else "هابط"

    score = 0
    reasons = []
    rejections = []  # تحسين 17: تسجيل أسباب الرفض/الضعف

    if rsi < 40:
        score += 1
        reasons.append("RSI منخفض")
    else:
        rejections.append(f"RSI مش منخفض ({rsi:.1f})")

    if trend == "صاعد":
        score += 1
        reasons.append("اتجاه صاعد (EMA)")

    if macd_line > macd_signal:
        score += 1
        reasons.append("MACD إيجابي")
    else:
        rejections.append("MACD سلبي")

    if price <= bb_lower * 1.015:
        score += 1
        reasons.append("قرب الحد السفلي لبولينجر")
    else:
        rejections.append("بعيد عن بولينجر السفلي")

    if volume_strength in ["قوي", "قوي جداً"]:
        score += 1
        reasons.append("حجم تداول قوي")
    else:
        rejections.append("حجم عادي")

    if adx > 25:
        score += 1
        reasons.append(f"اتجاه قوي (ADX: {adx:.0f})")
    else:
        rejections.append(f"ADX ضعيف ({adx:.0f})")

    if fg_value <= 30:
        score += 1
        reasons.append("مشاعر السوق خائفة (فرصة)")
    elif fg_value >= 75:
        score -= 1
        rejections.append("مشاعر السوق طماعة (حذر)")

    if btc_trend == "صاعد":
        score += 1
        reasons.append("اتجاه البيتكوين العام صاعد")
    elif btc_trend == "هابط":
        score -= 1
        rejections.append("اتجاه البيتكوين العام هابط")

    if low_liquidity:
        score -= 1
        rejections.append("ساعة سيولة منخفضة")

    score = max(0, score)

    tp = price + (atr * 2.5)
    sl = price - (atr * 1.5)

    return {
        "symbol": symbol, "price": price, "rsi": rsi, "trend": trend,
        "adx": adx, "atr": atr, "ema20": ema20, "volume_strength": volume_strength,
        "score": score, "reasons": reasons, "rejections": rejections,
        "tp": tp, "sl": sl
    }


def check_open_trades():
    open_trades, _ = sheet_get_status()
    if not open_trades:
        return
    for trade in open_trades:
        try:
            ticker = exchange.fetch_ticker(trade["symbol"])
            price = ticker['last']
            if price >= float(trade["tp"]):
                sheet_update_trade(trade["id"], "WIN", price)
                send_telegram(f"✅ توصية {trade['symbol']} وصلت لهدف الربح! السعر: ${price:.4f}")
            elif price <= float(trade["sl"]):
                sheet_update_trade(trade["id"], "LOSS", price)
                send_telegram(f"❌ توصية {trade['symbol']} وصلت لوقف الخسارة. السعر: ${price:.4f}")
        except Exception as e:
            print(f"خطأ في متابعة {trade['symbol']}: {e}")


# ---------------------------------------------------------
# التشغيل الرئيسي
# ---------------------------------------------------------
print(f"⏰ فحص السوق: {datetime.now().strftime('%Y-%m-%d %H:%M')}")

check_open_trades()

fg_value, fg_class = get_fear_greed()
print(f"Fear & Greed: {fg_value} ({fg_class})")

btc_trend = get_btc_trend()
print(f"اتجاه البيتكوين العام: {btc_trend}")

low_liquidity = is_low_liquidity_hour()
if low_liquidity:
    print("⚠️ ساعة سيولة منخفضة — البوت أكثر تشددًا دلوقتي")

near_event = is_near_major_economic_event()
if near_event:
    print("⚠️ فيه حدث اقتصادي كبير قريب — البوت في وضع هدوء")

_, last_times = sheet_get_status()

for symbol in halal_coins:
    try:
        r = analyze_coin(symbol, btc_trend, fg_value, low_liquidity)
        print(f"{r['symbol']} | ${r['price']:.4f} | RSI:{r['rsi']:.1f} | {r['trend']} | ADX:{r['adx']:.1f} | نقاط: {r['score']}")
        if r["rejections"]:
            print(f"   أسباب الضعف: {', '.join(r['rejections'])}")

        # تحسين 16: Cooldown
        if is_in_cooldown(symbol, last_times):
            print(f"   ⏸️ متخطي {symbol} — توصية سابقة خلال آخر {COOLDOWN_HOURS} ساعات")
            continue

        # تحسين 18: هدوء وقت الأحداث الاقتصادية
        if near_event:
            print(f"   ⏸️ متخطي {symbol} — قريب من حدث اقتصادي كبير")
            continue

        # تحسين 10: فلتر اتجاه العملة (بنيوي، مش نقطة إضافية)
        if r["trend"] == "هابط":
            if r["score"] >= 3:
                watch_msg = f"""🟡 ترقب (مش توصية شراء) — {r['symbol']}

السعر الحالي: ${r['price']:.4f}
الاتجاه العام: هابط ⚠️
لكن فيه إشارات إيجابية: {', '.join(r['reasons'])}

راقب لو السعر قفل فوق: ${r['ema20']:.4f} (EMA20)
لو حصل كده، الاتجاه القصير بيتحسن وتقدر تفكر تدخل

⚠️ رسالة ترقب فقط، مش توصية تنفيذ."""
                send_telegram(watch_msg)
            continue

        # تحسين 14: عتبات نظام النقاط الموحّد
        if r["score"] >= 6:
            strength = "قوية جداً"
            decision = "📌 القرار: ينصح بالدخول بثقة عالية"
        elif r["score"] == 5:
            strength = "قوية"
            decision = "📌 القرار: ينصح بالدخول"
        elif r["score"] in [3, 4]:
            strength = "متوسطة"
            decision = "📌 القرار: ينصح بالدخول بحذر (حجم صفقة أصغر)"
        else:
            strength = None
            decision = "📌 القرار: لا ينصح بالدخول حاليًا"

        if strength:
            # تحسين 13: صيغة واضحة + تحسين 15: سطر القرار الصريح
            msg = f"""✅ اشتري عند: ${r['price']:.4f}
🎯 بيع (هدف ربح) عند: ${r['tp']:.4f}
🛑 وقف الخسارة عند: ${r['sl']:.4f}

التقييم: {strength} — {r['score']} نقاط
العملة: {r['symbol']}
RSI: {r['rsi']:.1f} | الاتجاه: {r['trend']} | ADX: {r['adx']:.1f}
الحجم: {r['volume_strength']} | مشاعر السوق: {fg_value} ({fg_class})
أسباب الإشارة: {', '.join(r['reasons'])}

{decision}

⚠️ توصية تحليلية آلية، مش نصيحة استثمارية. راجع قرارك دايمًا."""
            send_telegram(msg)
            sheet_log_recommendation(r['symbol'], r['price'], r['tp'], r['sl'], r['score'], r['trend'], r['adx'], fg_value)

        elif r["rsi"] > 70:
            send_telegram(f"🔴 تحذير: {r['symbol']} تشبع شرائي (RSI: {r['rsi']:.1f})")

    except Exception as e:
        print(f"خطأ في {symbol}: {e}")

print("تم الفحص")
