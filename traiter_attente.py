"""Traite les liens en attente depuis l'ordinateur de la maison.

Le bot sur GitHub met en attente les annonces qu'il n'arrive pas à ouvrir
(mobile.de bloque les serveurs). Ce script, lancé à la main sur l'ordinateur,
les ouvre avec Chrome, envoie l'analyse sur Telegram, les ajoute au suivi,
puis vide la liste. Le bot sur GitHub peut continuer à tourner pendant ce temps.

    python traiter_attente.py
"""

import asyncio
import logging

from telegram import Bot

import attente
import suivi
from bot import TELEGRAM_TOKEN, contenu_des_liens, traiter

log = logging.getLogger("gla_bot")


async def main() -> None:
    suivi.synchroniser()
    liens = attente.charger()
    if not liens:
        print("✅ Aucun lien en attente.")
        return
    print(f"⏳ {len(liens)} lien(s) en attente.")

    async with Bot(TELEGRAM_TOKEN) as bot:
        for lien in liens:
            print(f"\n→ {lien['url'][:100]}")
            content, bloques = await contenu_des_liens([lien["url"]])
            if bloques:
                print("   ❌ Toujours bloqué, je le garde en attente.")
                continue
            content.append({"type": "text", "text": "Message envoyé :\n\n" + lien["message"]})
            await traiter(bot, lien["chat_id"], content, lien["message"])
            print("   ✅ Analysé, réponse envoyée sur Telegram.")
            # Retire ce lien tout de suite (au cas où le script serait interrompu).
            async with suivi.verrou:
                suivi.synchroniser()
                restants = [l for l in attente.charger() if l["url"] != lien["url"]]
                attente.sauver(restants, "Lien en attente traité depuis l'ordinateur")

    print(f"\nTerminé. Il reste {len(attente.charger())} lien(s) en attente.")


if __name__ == "__main__":
    asyncio.run(main())
