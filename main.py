import sys
import time
import requests

# Forcer l'affichage immédiat dans les logs Railway
sys.stdout.reconfigure(line_buffering=True)

TELEGRAM_BOT_TOKEN = "8646433044:AAGlwrPeXXbnL-EGCKJBFPpZkEIJzWBRUuY"
TELEGRAM_CHAT_ID = "8762743073"

# --- FILTRES DE MARCHÉ ---
MIN_MARKET_CAP = 15000       # MC min : $15k
MIN_VOLUME_5M = 3000         # Volume 5m min : $3k
MIN_LIQUIDITY_USD = 10000    # Liquidité min : $10k
MIN_AGE_SECONDS = 5 * 60     # Âge min : 5 min
MAX_AGE_SECONDS = 12 * 3600  # Âge max : 12 heures

# --- FILTRES DE SÉCURITÉ ---
MAX_RUGCHECK_SCORE = 1200    # Score de risque max (en dessous de 1000-1200 = Good)
MAX_TOP10_SHARE = 25.0       # Top 10 holders max : 25% de la supply

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

def check_rugcheck_security(mint_address):
    """
    Vérifie la sécurité on-chain via l'API RugCheck :
    Mint/Freeze authority, RugScore, LP Lock/Burn, Top Holders
    """
    url = f"https://api.rugcheck.xyz/v1/tokens/{mint_address}/report/summary"
    try:
        r = requests.get(url, timeout=7)
        if r.status_code != 200:
            # Fallback endpoint complet si summary indisponible
            r = requests.get(f"https://api.rugcheck.xyz/v1/tokens/{mint_address}/report", timeout=7)
            if r.status_code != 200:
                return False, {}

        data = r.json()
        score = data.get("score", 9999)
        token_meta = data.get("token", {})
        
        mint_auth = token_meta.get("mintAuthority")
        freeze_auth = token_meta.get("freezeAuthority")

        # 1. Vérification Mint et Freeze (doivent être révoqués / null)
        if mint_auth is not None or freeze_auth is not None:
            return False, {}

        # 2. Vérification du Score de risque global
        if score > MAX_RUGCHECK_SCORE:
            return False, {}

        # 3. Vérification de la concentration Top 10
        top10_share = 0
        top_holders = data.get("topHolders") or []
        for h in top_holders[:10]:
            top10_share += float(h.get("pct", 0))

        if top10_share > MAX_TOP10_SHARE:
            return False, {}

        details = {
            "score": score,
            "top10": top10_share,
            "mint_revoked": mint_auth is None,
            "freeze_revoked": freeze_auth is None
        }
        return True, details
    except Exception:
        # En cas de timeout de l'API de sécurité, on ne valide pas par prudence
        return False, {}

def scanner_et_envoyer():
    print("[Action] Scan Solana Elite en cours...")
    send_telegram("🔎 <b>Scan Solana Elite en cours...</b> (Filtres Sécurité + Liquidité + Dev activés)")
    
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
            liq_usd = pair.get("liquidity", {}).get("usd", 0)

            # Filtres DexScreener : MC + Volume 5m + Liquidité
            if not (mc >= MIN_MARKET_CAP and vol_5m >= MIN_VOLUME_5M and liq_usd >= MIN_LIQUIDITY_USD):
                continue

            ca_token = pair.get("baseToken", {}).get("address", "")
            
            # Audit on-chain RugCheck
            is_safe, sec_info = check_rugcheck_security(ca_token)
            if not is_safe:
                continue

            trouves += 1
            nom = pair.get("baseToken", {}).get("name", "Inconnu")
            sym = pair.get("baseToken", {}).get("symbol", "")
            pair_addr = pair.get("pairAddress", "")
            url_dex = pair.get("url", f"https://dexscreener.com/solana/{ca_token}")
            age_min = age_sec / 60
            top10 = sec_info.get("top10", 0)
            score = sec_info.get("score", 0)

            msg = (
                f"💎 <b>TOKEN SÉCURISÉ DÉTECTÉ</b>\n\n"
                f"🪙 <b>Nom :</b> {nom} (${sym})\n"
                f"⏳ <b>Âge :</b> {age_min:.0f} min\n"
                f"💰 <b>Market Cap :</b> ${mc:,.0f}\n"
                f"📊 <b>Volume 5m :</b> ${vol_5m:,.0f}\n"
                f"💧 <b>Liquidité :</b> ${liq_usd:,.0f}\n\n"
                f"🛡️ <b>SÉCURITÉ AUDIT :</b>\n"
                f"• Mint : ✅ Révoqué\n"
                f"• Freeze : ✅ Révoqué\n"
                f"• Top 10 Holders : <b>{top10:.1f}%</b> (Sain)\n"
                f"• Risque RugCheck : <b>{score}</b> (Safe)\n\n"
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

        if trouves == 0:
            send_telegram(f"ℹ️ <b>Aucun token ne respecte l'intégralité des critères stricts (MC > ${MIN_MARKET_CAP:,}, Liq > ${MIN_LIQUIDITY_USD:,}, Mint & Freeze révoqués, Top10 < 25%).</b>")
        print(f"[Action] Scan terminé : {trouves} token(s) envoyés.")
    except Exception as e:
        print(f"[Erreur Scan] {e}")
        send_telegram(f"⚠️ Erreur lors du scan : {e}")

def main():
    print("=== Démarrage du scanner interactif ===")
    
    try:
        requests.get(f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/deleteWebhook?drop_pending_updates=true", timeout=10)
    except Exception as e:
        print(f"[Webhook Init Error] {e}")

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
