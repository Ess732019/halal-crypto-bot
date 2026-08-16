import requests
from datetime import datetime
import os

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
CHAT_ID = "7231266337"

coins = {
    "bitcoin": "BTC",
    "ethereum": "ETH",
    "solana": "SOL",
    "ripple": "XRP",
    "cardano": "ADA"
}

TAKE_PROFIT = 0.04
STOP_LOSS = 0.025

def send_telegram(message):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        data = {"chat_id": CHAT_ID, "text": message}
        requests.post(url, data=data, timeout=10)
    except:
        pass

def get_market_data():
    ids = ",".join(coins.keys())
    url = f"https://api.coingecko.com/api/v3/coins/markets?vs_currency=usd&ids={ids}&order=market_cap_desc&sparkline=false&price_change_percentage=24h"
    response = requests.get(url, timeout=15)
    return response.json()

print(f"⏰ فحص السوق: {datetime.now().strftime('%Y-%m-%d %H:%M')}")

try:
    data = get_market_data()
    
    for coin in data:
        symbol = coins.get(coin["id"], coin["symbol"].upper())
        price = coin["current_price"]
        change_24h = coin.get("price_change_percentage_24h", 0)
        volume = coin.get("total_volume", 0)
        
        volume_strength = "عادي"
        if volume > 1_000_000_000:
            volume_strength = "قوي جداً"
        elif volume > 300_000_000:
            volume_strength = "قوي"
        
        print(f"{symbol} | ${price:.4f} | تغير 24س: {change_24h:.2f}% | {volume_strength}")
        
        if change_24h <= -2.5 and volume_strength in ["قوي", "قوي جداً"]:
            tp = price * (1 + TAKE_PROFIT)
            sl = price * (1 - STOP_LOSS)
            msg = f"""🟢 توصية شراء

العملة: {symbol}
السعر: ${price:.4f}
التغير 24 ساعة: {change_24h:.2f}%
الحجم: {volume_strength}

هدف الربح: ${tp:.4f}
وقف الخسارة: ${sl:.4f}"""
            send_telegram(msg)
            
        elif change_24h >= 4.5 and volume_strength in ["قوي", "قوي جداً"]:
            send_telegram(f"🔴 تحذير: {symbol} ارتفع بقوة ({change_24h:.2f}%) - راقب جني الأرباح")
            
except Exception as e:
    print(f"خطأ عام: {e}")

print("تم الفحص")
