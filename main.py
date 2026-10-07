import time
import requests

TELEGRAM_BOT_TOKEN = "8646433044:AAHVmXRdyIZ5UGeNkwvJPMWG42Vh0Gz1Uxo"
TELEGRAM_CHAT_ID = "8762743073"

MIN_MARKET_CAP = 15000
MIN_VOLUME_5M = 3000
MIN_AGE_SECONDS = 5 * 60
MAX_AGE_SECONDS = 12 * 3600

def send_telegram(text):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text,
        "parse_mode": "Markdown",
        "disable_web_page_preview": True
    }
    try:
        requests.post(url, json=payload, timeout=10)
    except Exception as e:
        print(f"[Erreur Envoi] : {e}")

def scanner_et_envoyer():
    send_telegram("🔎 *Recherche de tokens Solana en cours...*")
    url = "https://api.dexscreener.com/latest/dex/search?q=solana"
    try:
        resp = requests.get(url, timeout=10)
        data = resp.json()
        pairs = data.get("pairs") or []
        now_ms = time.time() * 1000
        trouves = 0

        for pair in pairs:
            if pair.get("chainId") != "solana":
                continue

            created_at = pair.get("pairCreatedAt", 0)
            if not created_at:
                continue

            age_sec = (now_ms - created_at) / 1000
            if not (MIN_AGE_SECONDS <= age_sec <= MAX_AGE_SECONDS):
                continue

            mc = pair.get("marketCap") or pair.get("fdv", 0)
            vol_5m = pair.get("volume", {}).get("m5", 0)

            if mc >= MIN_MARKET_CAP and vol_5m >= MIN_VOLUME_5M:
                trouves += 1
                nom = pair.get("baseToken", {}).get("name", "Inconnu")
                sym = pair.get("baseToken", {}).get("symbol", "")
                ca = pair.get("baseToken", {}).get("address", "")
                age_min = age_sec / 60

                msg = (
                    f"🚨 *TOKEN DÉTECTÉ*\n\n"
                    f"🪙 *Nom :* {nom} ({sym})\n"
                    f"⏳ *Âge :* {age_min:.0f} min\n"
                    f"💰 *Market Cap :* ${mc:,.0f}\n"
                    f"📊 *Volume 5m :* ${vol_5m:,.0f}\n\n"
                    f"📋 *Contrat :*\n`{ca}`\n\n"
                    f"🔗 [Voir sur GMGN](https://gmgn.ai/sol/token/{ca})"
                )
                send_telegram(msg)

        if trouves == 0:
            send_telegram("ℹ️ *Aucun token ne remplit les critères (MC > $15k, Vol5m > $3k) pour le moment.*")
    except Exception as e:
        send_telegram(f"⚠️ Erreur lors du scan : {e}")

def main():
    print("=== Démarrage du scanner interactif ===")
    send_telegram("🚀 *Scanner prêt !* Envoyez *s* pour lancer un scan.")

    offset = None
    while True:
        try:
            url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getUpdates"
            params = {"timeout": 20}
            if offset:
                params["offset"] = offset

            resp = requests.get(url, params=params, timeout=25)
            data = resp.json()

            for item in data.get("result", []):
                offset = item["update_id"] + 1
                msg = item.get("message", {})
                texte = msg.get("text", "").strip().lower()

                if texte in ["s", "scan", "/scan", "/start"]:
                    scanner_et_envoyer()

        except Exception as e:
            time.sleep(2)

if __name__ == "__main__":
    main()
