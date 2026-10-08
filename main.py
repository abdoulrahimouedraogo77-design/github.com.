import sys
import time
import requests

sys.stdout.reconfigure(line_buffering=True)

TELEGRAM_BOT_TOKEN = "8646433044:AAGlwrPeXXbnL-EGCKJBFPpZkEIJzWBRUuY"
TELEGRAM_CHAT_ID = "8762743073"

# --- FILTRES EQUILIBRÉS ---
MIN_MARKET_CAP = 15000       # MC min : $15k
MIN_VOLUME_5M = 1500         # Volume 5m min : $1.5k
MIN_LIQUIDITY_USD = 5000     # Liquidité min : $5k
MIN_AGE_SECONDS = 3 * 60     # Âge min : 3 min
MAX_AGE_SECONDS = 24 * 3600  # Âge max : 24 heures

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

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

def get_security_details(mint_address):
    """Vérifie la sécurité sans bloquer le script en cas d'erreur API"""
    url = f"https://api.rugcheck.xyz/v1/tokens/{mint_address}/report/summary"
    try:
        r = requests.get(url, headers=HEADERS, timeout=4)
        if r.status_code == 200:
            data = r.json()
            score = data.get("score", "N/A")
            token_meta = data.get("token", {})
            mint_auth = "✅ Révoqué" if token_meta.get("mintAuthority") is None else "⚠️ Actif"
            freeze_auth = "✅ Révoqué" if token_meta.get("freezeAuthority") is None else "⚠️ Actif"
            
            top10_share = 0
            for h in (data.get("topHolders") or [])[:10]:
                top10_share += float(h.get("pct", 0))
            
            return {
                "ok": True,
                "score": score,
                "mint": mint_auth,
                "freeze": freeze_auth,
                "top10": f"{top10_share:.1f}%" if top10_share > 0 else "N/A"
            }
    except Exception:
        pass
    return {"ok": False}

def scanner_et_envoyer():
    print("[Action] Scan Solana Elite en cours...")
    send_telegram("🔎 <b>Scan Solana en cours...</b> Recherche des paires actives...")
    
    url = "https://api.dexscreener.com/latest/dex/search?q=solana"
    try:
        resp = requests.get(url, headers=HEADERS, timeout=10)
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
            liq_usd = pair.get("liquidity", {}).get("usd", 0)

            # Filtres DexScreener
            if not (mc >= MIN_MARKET_CAP and vol_5m >= MIN_VOLUME_5M and liq_usd >= MIN_LIQUIDITY_USD):
                continue

            ca_token = pair.get("baseToken", {}).get("address", "")
            nom = pair.get("baseToken", {}).get("name", "Inconnu")
            sym = pair.get("baseToken", {}).get("symbol", "")
            pair_addr = pair.get("pairAddress", "")
            url_dex = pair.get("url", f"https://dexscreener.com/solana/{ca_token}")
            age_min = age_sec / 60

            # Récupération infos sécurité
            sec = get_security_details(ca_token)
            if sec.get("ok"):
                sec_text = (
                    f"🛡️ <b>SÉCURITÉ AUDIT :</b>\n"
                    f"• Mint : {sec['mint']}\n"
                    f"• Freeze : {sec['freeze']}\n"
                    f"• Top 10 Holders : <b>{sec['top10']}</b>\n"
                    f"• Risque RugCheck : <b>{sec['score']}</b>\n\n"
                )
            else:
                sec_text = "🛡️ <i>Audit complet disponible sur GMGN</i>\n\n"

            trouves += 1
            msg = (
                f"💎 <b>TOKEN DÉTECTÉ</b>\n\n"
                f"🪙 <b>Nom :</b> {nom} (${sym})\n"
                f"⏳ <b>Âge :</b> {age_min:.0f} min\n"
                f"💰 <b>Market Cap :</b> ${mc:,.0f}\n"
                f"📊 <b>Volume 5m :</b> ${vol_5m:,.0f}\n"
                f"💧 <b>Liquidité :</b> ${liq_usd:,.0f}\n\n"
                f"{sec_text}"
                f"📋 <b>CA Token :</b>\n<code>{ca_token}</code>\n"
                f"🏊 <b>Pool :</b>\n<code>{pair_addr}</code>"
            )

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

            if trouves >= 5:  # Limite à 5 tokens par scan pour ne pas spammer
                break

        if trouves == 0:
            send_telegram(f"ℹ️ Aucun token ne correspond exactement aux filtres en ce moment (MC > ${MIN_MARKET_CAP:,}, Liq > ${MIN_LIQUIDITY_USD:,}). Réessayez dans quelques instants !")
        print(f"[Action] Scan terminé : {trouves} token(s) envoyés.")
    except Exception as e:
        print(f"[Erreur Scan] {e}")
        send_telegram(f"⚠️ Erreur lors du scan : {e}")

def main():
    print("=== Démarrage du scanner interactif ===")
    try:
        requests.get(f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/deleteWebhook?drop_pending_updates=true", timeout=10)
    except Exception as e:
        print(f"[Webhook Error] {e}")

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
                msg = item.get("message", {})
                texte = msg.get("text", "").strip().lower()
                if texte in ["s", "scan", "/scan", "/start"]:
                    scanner_et_envoyer()

                cb = item.get("callback_query", {})
                if cb:
                    cb_id = cb.get("id")
                    cb_data = cb.get("data", "")
                    alert_text = "Adresse sélectionnée"
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
            
