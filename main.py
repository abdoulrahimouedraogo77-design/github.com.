import sys
import time
import requests

# Forcer l'affichage dans les logs Railway
sys.stdout.reconfigure(line_buffering=True)

TELEGRAM_BOT_TOKEN = "8646433044:AAGlwrPeXXbnL-EGCKJBFPpZkEIJzWBRUuY"
TELEGRAM_CHAT_ID = "8762743073"

# --- FILTRES TRADING MEMECOINS ---
MIN_MC = 10000            # MC min : $10k (évite les tokens morts)
MAX_MC = 500000           # MC max : $500k (garde le potentiel de multiplicateur x2, x5, x10)
MIN_LIQUIDITY = 4000      # Liquidité min dans la pool : $4k
MIN_VOLUME_5M = 1500      # Volume récent 5m : min $1 500 (activité acheteuse)
MIN_AGE_MIN = 3           # Âge min : 3 minutes (évite le premier bloc de snipers bots)
MAX_AGE_HOURS = 8         # Âge max : 8 heures (focus memecoins frais)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko)"
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

def scanner_memecoins():
    print("[Action] Scan Memecoins Solana en cours...")
    send_telegram("🚀 <b>Scan Memecoins Solana...</b> Détection des opportunités en cours...")

    # Récupération des profils et tokens les plus récents et actifs sur Solana
    endpoints = [
        "https://api.dexscreener.com/token-profiles/latest/v1",
        "https://api.dexscreener.com/latest/dex/search?q=solana"
    ]
    
    seen_addresses = set()
    trouves = 0
    now_ms = time.time() * 1000

    try:
        # 1. Scanner les derniers tokens boostés / avec profil actif
        r_profiles = requests.get(endpoints[0], headers=HEADERS, timeout=10)
        token_addrs = []
        if r_profiles.status_code == 200:
            for item in r_profiles.json():
                if item.get("chainId") == "solana":
                    token_addrs.append(item.get("tokenAddress"))

        # Interroger les paires de ces tokens récents
        pairs = []
        if token_addrs:
            sample = ",".join(token_addrs[:25])
            r_tokens = requests.get(f"https://api.dexscreener.com/latest/dex/tokens/{sample}", headers=HEADERS, timeout=10)
            if r_tokens.status_code == 200:
                pairs.extend(r_tokens.json().get("pairs") or [])

        # Compléter avec la recherche générale Solana
        r_search = requests.get(endpoints[1], headers=HEADERS, timeout=10)
        if r_search.status_code == 200:
            pairs.extend(r_search.json().get("pairs") or [])

        for pair in pairs:
            if pair.get("chainId") != "solana":
                continue

            ca = pair.get("baseToken", {}).get("address", "")
            if not ca or ca in seen_addresses:
                continue

            created_at = pair.get("pairCreatedAt", 0)
            if not created_at:
                continue

            age_sec = (now_ms - created_at) / 1000
            age_min = age_sec / 60
            age_hours = age_min / 60

            if not (MIN_AGE_MIN <= age_min and age_hours <= MAX_AGE_HOURS):
                continue

            mc = pair.get("marketCap") or pair.get("fdv", 0)
            vol_5m = pair.get("volume", {}).get("m5", 0)
            liq = pair.get("liquidity", {}).get("usd", 0)
            dex_id = pair.get("dexId", "DEX").capitalize()

            # Application des filtres de trading
            if not (MIN_MC <= mc <= MAX_MC and liq >= MIN_LIQUIDITY and vol_5m >= MIN_VOLUME_5M):
                continue

            seen_addresses.add(ca)
            trouves += 1

            nom = pair.get("baseToken", {}).get("name", "Inconnu")
            sym = pair.get("baseToken", {}).get("symbol", "")
            price = pair.get("priceUsd", "0")
            txns_5m = pair.get("txns", {}).get("m5", {})
            buys = txns_5m.get("buys", 0)
            sells = txns_5m.get("sells", 0)

            # Format d'âge propre
            age_label = f"{age_min:.0f}m" if age_min < 60 else f"{age_hours:.1f}h"

            msg = (
                f"🔥 <b>MEMECOIN EN VUE</b> ({dex_id})\n\n"
                f"🪙 <b>{nom}</b> | <code>${sym}</code>\n"
                f"⏱️ <b>Âge :</b> {age_label}\n"
                f"💰 <b>MC :</b> ${mc:,.0f} | <b>Prix :</b> ${float(price):.6f}\n"
                f"💧 <b>Liq :</b> ${liq:,.0f} | <b>Vol 5m :</b> ${vol_5m:,.0f}\n"
                f"📊 <b>Transactions 5m :</b> 🟢 {buys} buys / 🔴 {sells} sells\n\n"
                f"📋 <b>CA :</b>\n<code>{ca}</code>"
            )

            # Boutons de trading direct (GMGN, Photon, Trojan Telegram bot, DexScreener)
            keyboard = {
                "inline_keyboard": [
                    [
                        {"text": "🟧 GMGN Sniper", "url": f"https://gmgn.ai/sol/token/{ca}"},
                        {"text": "⚡ Photon SOL", "url": f"https://photon-sol.tinyastro.io/en/lp/{pair.get('pairAddress', ca)}"}
                    ],
                    [
                        {"text": "🤖 Trojan Bot", "url": f"https://t.me/solana_trojanbot?start={ca}"},
                        {"text": "📊 DexScreener", "url": pair.get("url", f"https://dexscreener.com/solana/{ca}")}
                    ],
                    [
                        {"text": "📋 Copier Contrat (CA)", "callback_data": f"ca:{ca[:30]}"}
                    ]
                ]
            }

            send_telegram(msg, reply_markup=keyboard)

            if trouves >= 4:
                break

        if trouves == 0:
            send_telegram("ℹ️ <b>Aucun memecoin ne passe les filtres actuellement.</b>\n(Filtres : MC $10k-$500k, Liq > $4k, Vol 5m > $1.5k). Réessayez dans une minute !")
        print(f"[Action] Scan Memecoins terminé : {trouves} token(s) envoyés.")

    except Exception as e:
        print(f"[Erreur Scan] {e}")
        send_telegram(f"⚠️ Erreur lors du scan : {e}")

def main():
    print("=== Démarrage Scanner Memecoin Trading ===")
    try:
        requests.get(f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/deleteWebhook?drop_pending_updates=true", timeout=10)
    except Exception as e:
        print(f"[Webhook Error] {e}")

    keyboard_reply = {
        "keyboard": [[{"text": "s"}]],
        "resize_keyboard": True,
        "is_persistent": True
    }
    send_telegram("🟢 <b>Scanner Memecoin Solana Prêt !</b>\nAppuyez sur <b>s</b> pour trouver les memecoins chauds.", reply_markup=keyboard_reply)

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
                    scanner_memecoins()

                cb = item.get("callback_query", {})
                if cb:
                    cb_id = cb.get("id")
                    requests.post(
                        f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/answerCallbackQuery",
                        json={"callback_query_id": cb_id, "text": "Contrat sélectionné !", "show_alert": False},
                        timeout=5
                    )

        except Exception as e:
            print(f"[Erreur boucle] {e}")
            time.sleep(2)

if __name__ == "__main__":
    main()
