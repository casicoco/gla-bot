"""Cherche de nouvelles annonces depuis l'ordinateur de la maison.

Ouvre chaque recherche de recherches.txt avec Chrome (mobile.de accepte la connexion
de la maison), repère les annonces qui ne sont pas encore suivies, les analyse,
les ajoute au tableau de suivi, puis envoie UN message récapitulatif sur Telegram.

    python rechercher.py            # 10 nouvelles annonces au maximum
    python rechercher.py --max 20

Chaque annonce analysée coûte un appel à Claude : la limite évite les mauvaises surprises.
"""

import argparse
import asyncio
from pathlib import Path

from telegram import Bot

import attente
import suivi
from bot import ALLOWED_IDS, PAGE_SUIVI, TELEGRAM_TOKEN, contenu_des_liens, traiter
from lecteur import liens_annonces

FICHIER_RECHERCHES = Path(__file__).parent / "recherches.txt"
ORDRE = {"À contacter": 0, "À étudier": 1, "À écarter": 2}


def charger_recherches() -> list[str]:
    lignes = FICHIER_RECHERCHES.read_text().splitlines() if FICHIER_RECHERCHES.exists() else []
    return [l.strip() for l in lignes if l.strip() and not l.strip().startswith("#")]


def recapitulatif(fiches: list[dict], bloques: int, restants: int) -> str:
    if not fiches:
        texte = "🔎 Recherche terminée : aucune nouvelle annonce."
    else:
        texte = f"🔎 Recherche terminée : {len(fiches)} nouvelle(s) annonce(s) ajoutée(s) au suivi.\n"
        for f in sorted(fiches, key=lambda f: (ORDRE.get(f["decision"], 9), f.get("prix") or 1e9)):
            prix = f"{f['prix']:,} €".replace(",", " ") if f.get("prix") else "prix ?"
            texte += f"\n• {f['decision']} : {f['titre']}, {f.get('annee') or '?'}, {prix}\n  {f['url']}"
    if bloques:
        texte += f"\n\n⚠️ {bloques} annonce(s) n'ont pas pu être ouvertes."
    if restants:
        texte += f"\n\n{restants} autre(s) annonce(s) trouvée(s), à analyser au prochain passage."
    if PAGE_SUIVI:
        texte += f"\n\nTableau de suivi : {PAGE_SUIVI}"
    return texte


async def main(maximum: int) -> None:
    suivi.synchroniser()
    recherches = charger_recherches()
    if not recherches:
        print("Aucune recherche dans recherches.txt.")
        return

    connus = {suivi._cle_url(a.get("url", "")) for a in suivi.charger()}
    connus |= {suivi._cle_url(l["url"]) for l in attente.charger()}
    nouveaux: list[str] = []
    for r in recherches:
        try:
            liens, bloquee = await liens_annonces(r)
        except Exception as e:
            print(f"❌ Recherche impossible ({type(e).__name__}) : {r[:80]}")
            continue
        if bloquee:
            print(f"❌ Page de recherche bloquée : {r[:80]}")
            continue
        neufs = [l for l in liens if suivi._cle_url(l) not in connus]
        print(f"🔎 {len(liens)} annonces trouvées, dont {len(neufs)} nouvelles : {r[:80]}")
        for l in neufs:
            connus.add(suivi._cle_url(l))
            nouveaux.append(l)

    a_traiter, restants = nouveaux[:maximum], max(0, len(nouveaux) - maximum)
    fiches, bloques = [], 0
    chat = next(iter(ALLOWED_IDS), 0)
    async with Bot(TELEGRAM_TOKEN) as bot:
        for i, url in enumerate(a_traiter, 1):
            print(f"\n[{i}/{len(a_traiter)}] {url[:100]}")
            content, bloques_ici = await contenu_des_liens([url])
            if bloques_ici:
                bloques += 1
                print("   ❌ Annonce bloquée.")
                continue
            content.append({"type": "text", "text": f"Annonce trouvée par la recherche automatique : {url}"})
            res = await traiter(bot, chat, content, source=url, envoyer_rapport=False, annoncer=False)
            if res["fiche"]:
                fiches.append(res["fiche"])
                print(f"   ✅ {res['fiche']['decision']} : {res['fiche']['titre']}")
            else:
                print("   ⚠️ Analyse ou enregistrement impossible.")

        message = recapitulatif(fiches, bloques, restants)
        print("\n" + message)
        for chat_id in ALLOWED_IDS:
            for i in range(0, len(message), 4000):
                await bot.send_message(chat_id, message[i : i + 4000])


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--max", type=int, default=10, help="nombre maximum de nouvelles annonces à analyser")
    asyncio.run(main(parser.parse_args().max))
