import os
import time
import requests

TELEGRAM_BOT_TOKEN = "8646433044:AAHVmXRdyIZ5UGcNkwvIPMWG42VhOGz1Uxo"
TELEGRAM_CHAT_ID = "8762743073"

MIN_AGE_SECONDS = 5 * 60
MAX_AGE_SECONDS = 12 * 3600
MIN_MARKET_CAP = 15000
MIN_VOLUME_5M = 3000

seen_tokens = set()

def send_alert(name, symbol, ca, mc, vol, age_min):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    message = (
        f"🚨 *NOUVEAU TOKEN VALIDÉ* 🚨\n\n"
        f"🪙 *Nom:* {name} (${symbol})\n"
        f"⏱️ *Âge:* {age_min:.0f} minutes\n"
        f"💰 *Market Cap:* ${mc:,.0f}\n"
        f"📊 *Volume 5m:* ${vol:,.0f}\n\n"
        f"📋 *Contrat (Clique pour copier) :*\n`{ca}`\n\n"
        f"🔗 [Ouvrir sur GMGN](https://gmgn.ai/sol/token/{ca})"
    )
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "Markdown",
        "disable_web_page_preview": True
    }
    try:
        requests.post(url, json=payload, timeout=10)
    except Exception as e:
        print(f"Erreur d'envoi: {e}")

def run_scanner():
    url = "https://api.dexscreener.com/latest/dex/search?q=solana"
    try:
        resp = requests.get(url, timeout=10)
        data = resp.json()
        pairs = data.get("pairs", [])
        now_ms = time.time() * 1000

        for pair in pairs:
            if pair.get("chainId") != "solana":
                continue

            ca = pair.get("baseToken", {}).get("address")
            if not ca or ca in seen_tokens:
                continue

            created_at = pair.get("pairCreatedAt", 0)
            if not created_at:
                continue

            age_seconds = (now_ms - created_at) / 1000

            if MIN_AGE_SECONDS <= age_seconds <= MAX_AGE_SECONDS:
                mc = pair.get("marketCap", 0) or pair.get("fdv", 0)
                vol_5m = pair.get("volume", {}).get("m5", 0)

                if mc >= MIN_MARKET_CAP and vol_5m >= MIN_VOLUME_5M:
                    seen_tokens.add(ca)
                    name = pair.get("baseToken", {}).get("name", "Unknown")
                    symbol = pair.get("baseToken", {}).get("symbol", "TOKEN")
                    
                    send_alert(name, symbol, ca, mc, vol_5m, age_seconds / 60)
                    print(f"Contrat envoyé: {symbol} ({ca})")
    except Exception as e:
        print(f"Erreur scan: {e}")

if __name__ == "__main__":
    print("Démarrage du scanner cloud...")
    while True:
        run_scanner()
        time.sleep(20)
