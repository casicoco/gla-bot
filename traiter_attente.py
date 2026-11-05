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
from bot import TELEGRAM_TOKEN, contenu_des_liens, enregistrer_et_annoncer, traiter

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
            if lien.get("rapport"):
                # Analyse déjà envoyée sur Telegram, seul l'ajout au suivi avait échoué.
                fiche = await enregistrer_et_annoncer(bot, lien["chat_id"], lien["message"], lien["rapport"])
                resultat = {"rapport": lien["rapport"], "enregistre": fiche is not False}
            else:
                content, bloques = await contenu_des_liens([lien["url"]])
                if bloques:
                    print("   ❌ Toujours bloqué, je le garde en attente.")
                    continue
                content.append({"type": "text", "text": "Message envoyé :\n\n" + lien["message"]})
                resultat = await traiter(
                    bot, lien["chat_id"], content, lien["message"],
                    envoyer_rapport=not lien.get("deja_envoye", False),
                )

            async with suivi.verrou:
                suivi.synchroniser()
                liste = attente.charger()
                if resultat["enregistre"]:
                    print("   ✅ Analysé et ajouté au suivi.")
                    liste = [l for l in liste if l["url"] != lien["url"]]
                    attente.sauver(liste, "Lien en attente traité depuis l'ordinateur")
                elif resultat["rapport"]:
                    print("   ⚠️ Analyse envoyée, mais l'ajout au suivi a échoué. Je réessaierai la prochaine fois.")
                    for l in liste:
                        if l["url"] == lien["url"]:
                            l["rapport"] = resultat["rapport"]
                    attente.sauver(liste, "Lien en attente : ajout au suivi à refaire")
                else:
                    print("   ❌ L'analyse a échoué, je le garde en attente.")

    print(f"\nTerminé. Il reste {len(attente.charger())} lien(s) en attente.")


if __name__ == "__main__":
    asyncio.run(main())
