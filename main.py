import sys
import time
import requests

# Force l'affichage immédiat dans les logs Railway
sys.stdout.reconfigure(line_buffering=True)

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
        "parse_mode": "HTML",
        "disable_web_page_preview": True
    }
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
                ca = pair.get("baseToken", {}).get("address", "")
                age_min = age_sec / 60

                msg = (
                    f"🚨 <b>TOKEN DÉTECTÉ</b>\n\n"
                    f"🪙 <b>Nom :</b> {nom} ({sym})\n"
                    f"⏳ <b>Âge :</b> {age_min:.0f} min\n"
                    f"💰 <b>Market Cap :</b> ${mc:,.0f}\n"
                    f"📊 <b>Volume 5m :</b> ${vol_5m:,.0f}\n\n"
                    f"📋 <b>Contrat :</b>\n<code>{ca}</code>\n\n"
                    f"🔗 <a href='https://gmgn.ai/sol/token/{ca}'>Voir sur GMGN</a>"
                )
                send_telegram(msg)

        if trouves == 0:
            send_telegram("ℹ️ <b>Aucun token ne remplit les critères (MC > $15k, Vol5m > $3k).</b>")
        print(f"[Action] Scan terminé : {trouves} token(s) envoyés.")
    except Exception as e:
        print(f"[Erreur DexScreener] {e}")
        send_telegram(f"⚠️ Erreur lors du scan : {e}")

def main():
    print("=== Nettoyage et initialisation Telegram ===")
    
    # Étape 1 : Débloquer Telegram (supprime tout ancien webhook résiduel)
    try:
        del_url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/deleteWebhook?drop_pending_updates=true"
        requests.get(del_url, timeout=10)
        print("[Telegram] Webhook supprimé et file nettoyée avec succès.")
    except Exception as e:
        print(f"[Telegram Init Warning] {e}")

    # Étape 2 : Envoyer le message de confirmation
    send_telegram("🟢 <b>Scanner interactif opérationnel !</b>\nEnvoyez la lettre <b>s</b> pour scanner.")

    # Étape 3 : Écoute en continu
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
                msg = item.get("message", {})
                texte = msg.get("text", "").strip().lower()
                print(f"[Commande reçue] : {texte}")

                if texte in ["s", "scan", "/scan", "/start"]:
                    scanner_et_envoyer()

        except Exception as e:
            print(f"[Erreur boucle] {e}")
            time.sleep(2)

if __name__ == "__main__":
    main()
