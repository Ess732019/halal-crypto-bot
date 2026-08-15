import ccxt
import requests
from datetime import datetime

TELEGRAM_TOKEN = "8446358268:AAHltvnojSB7LrDWkmPiTuluXLOxBDduP1o"
CHAT_ID = "7231266337"

halal_coins = ['BTC/USDT', 'ETH/USDT', 'SOL/USDT', 'XRP/USDT', 'ADA/USDT']
exchange = ccxt.binance()

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
    gains = []
    losses = []
    for i in range(1, len(closes)):
        diff = closes[i] - closes[i-1]
        if diff >= 0:
            gains.append(diff)
            losses.append(0)
        else:
            gains.append(0)
            losses.append(abs(diff))
    avg_gain = sum(gains[-period:]) / period
    avg_loss = sum(losses[-period:]) / period
    if avg_loss == 0:
        return 100
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))

def calculate_sma(closes, period):
    if len(closes) < period:
        return closes[-1]
    return sum(closes[-period:]) / period

print(f"⏰ فحص السوق: {datetime.now().strftime('%Y-%m-%d %H:%M')}")

for symbol in halal_coins:
    try:
        ticker = exchange.fetch_ticker(symbol)
        price = ticker['last']
        volume = ticker.get('quoteVolume', 0)
        
        ohlcv = exchange.fetch_ohlcv(symbol, timeframe='1h', limit=60)
        closes = [candle[4] for candle in ohlcv]
        
        rsi = calculate_rsi(closes)
        sma20 = calculate_sma(closes, 20)
        sma50 = calculate_sma(closes, 50)
        
        volume_strength = "عادي"
        if volume > 500_000_000:
            volume_strength = "قوي جداً"
        elif volume > 100_000_000:
            volume_strength = "قوي"
        
        trend = "صاعد" if sma20 > sma50 else "هابط"
        
        print(f"{symbol} | ${price:.4f} | RSI: {rsi:.1f} | Trend: {trend} | {volume_strength}")
        
        if rsi < 35 and volume_strength in ["قوي", "قوي جداً"] and sma20 > sma50:
            tp = price * (1 + TAKE_PROFIT)
            sl = price * (1 - STOP_LOSS)
            msg = f"""🟢 توصية شراء قوية

العملة: {symbol}
السعر: ${price:.4f}
RSI: {rsi:.1f}
الاتجاه: {trend}
الحجم: {volume_strength}

هدف الربح: ${tp:.4f}
وقف الخسارة: ${sl:.4f}"""
            send_telegram(msg)
            
        elif rsi < 32 and volume_strength in ["قوي", "قوي جداً"]:
            tp = price * (1 + TAKE_PROFIT)
            sl = price * (1 - STOP_LOSS)
            msg = f"""🟡 توصية شراء (بحذر)

العملة: {symbol}
السعر: ${price:.4f}
RSI: {rsi:.1f}
الحجم: {volume_strength}

هدف الربح: ${tp:.4f}
وقف الخسارة: ${sl:.4f}"""
            send_telegram(msg)
            
        elif rsi > 72:
            send_telegram(f"🔴 تحذير: {symbol} تشبع شرائي (RSI: {rsi:.1f})")
            
    except Exception as e:
        print(f"خطأ في {symbol}: {e}")

print("تم الفحص")
