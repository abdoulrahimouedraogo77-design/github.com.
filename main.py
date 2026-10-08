import sys
import time
import requests

# Forcer l'affichage immédiat dans les logs Railway
sys.stdout.reconfigure(line_buffering=True)

TELEGRAM_BOT_TOKEN = "8646433044:AAGlwrPeXXbnL-EGCKJBFPpZkEIJzWBRUuY"
TELEGRAM_CHAT_ID = "8762743073"

MIN_MARKET_CAP = 15000
MIN_VOLUME_5M = 3000
MIN_AGE_SECONDS = 5 * 60
MAX_AGE_SECONDS = 12 * 3600

def send_telegram(text, reply_markup=None):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True
    }
    if reply_markup:
        payload["reply_markup"] = reply_markup
    try:
        r = requests.post(url, json=payload, timeout=10)
        print(f"[Telegram Send] Code {r.status_code}")
    except Exception as e:
        print(f"[Erreur Telegram] {e}")

def scanner_et_envoyer():
    print("[Action] Scan Solana en cours...")
    send_telegram("🔎 <b>Recherche de tokens Solana en cours...</b>")
    
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
                ca_token = pair.get("baseToken", {}).get("address", "")
                pair_addr = pair.get("pairAddress", "")
                url_dex = pair.get("url", f"https://dexscreener.com/solana/{ca_token}")
                age_min = age_sec / 60

                msg = (
                    f"🚨 <b>TOKEN DÉTECTÉ</b>\n\n"
                    f"🪙 <b>Nom :</b> {nom} (${sym})\n"
                    f"⏳ <b>Âge :</b> {age_min:.0f} min\n"
                    f"💰 <b>Market Cap :</b> ${mc:,.0f}\n"
                    f"📊 <b>Volume 5m :</b> ${vol_5m:,.0f}\n\n"
                    f"📋 <b>CA Token :</b>\n<code>{ca_token}</code>\n"
                    f"💧 <b>Pool Address :</b>\n<code>{pair_addr}</code>"
                )

                # Boutons interactifs sous le message
                keyboard = {
                    "inline_keyboard": [
                        [
                            {"text": "🟧 GMGN", "url": f"https://gmgn.ai/sol/token/{ca_token}"},
                            {"text": "🪐 Meteora", "url": f"https://app.meteora.ag/dlmm/{pair_addr}" if pair_addr else "https://app.meteora.ag"}
                        ],
                        [
                            {"text": "📋 Copier Token", "callback_data": f"copy_token:{ca_token[:30]}"},
                            {"text": "📋 Copier Pool", "callback_data": f"copy_pool:{pair_addr[:30]}"}
                        ],
                        [
                            {"text": "📊 DexScreener", "url": url_dex}
                        ]
                    ]
                }
                send_telegram(msg, reply_markup=keyboard)

        if trouves == 0:
            send_telegram("ℹ️ <b>Aucun token ne remplit les critères (MC > $15k, Vol5m > $3k) pour le moment.</b>")
        print(f"[Action] Scan terminé : {trouves} token(s) envoyés.")
    except Exception as e:
        print(f"[Erreur DexScreener] {e}")
        send_telegram(f"⚠️ Erreur lors du scan : {e}")

def main():
    print("=== Démarrage du scanner interactif ===")
    
    try:
        requests.get(f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/deleteWebhook?drop_pending_updates=true", timeout=10)
    except Exception as e:
        print(f"[Webhook Init Error] {e}")

    # Clavier persistant pour lancer le scan en 1 clic
    keyboard_reply = {
        "keyboard": [[{"text": "s"}]],
        "resize_keyboard": True,
        "is_persistent": True
    }
    send_telegram("🟢 <b>Scanner interactif opérationnel !</b>\nAppuyez sur <b>s</b> pour scanner.", reply_markup=keyboard_reply)

    offset = None
    while True:
        try:
            url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getUpdates"
            params = {"timeout": 15}
            if offset:
                params["offset"] = offset

            resp = requests.get(url, params=params, timeout=20)
            data = resp.json()

            for item in data.get("result", []):
                offset = item["update_id"] + 1
                
                # Gestion des commandes écrites
                msg = item.get("message", {})
                texte = msg.get("text", "").strip().lower()
                if texte in ["s", "scan", "/scan", "/start"]:
                    scanner_et_envoyer()

                # Gestion des clics sur les boutons Copier
                cb = item.get("callback_query", {})
                if cb:
                    cb_id = cb.get("id")
                    cb_data = cb.get("data", "")
                    alert_text = "Adresse copiée"
                    if cb_data.startswith("copy_"):
                        val = cb_data.split(":", 1)[-1]
                        alert_text = f"Adresse : {val}"
                    requests.post(
                        f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/answerCallbackQuery",
                        json={"callback_query_id": cb_id, "text": alert_text, "show_alert": False},
                        timeout=5
                    )

        except Exception as e:
            print(f"[Erreur boucle] {e}")
            time.sleep(2)

if __name__ == "__main__":
    main()
