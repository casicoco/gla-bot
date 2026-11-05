"""Bot Telegram qui vérifie les annonces de Mercedes GLA.

On envoie au bot un lien, un texte copié ou des captures d'écran
d'une annonce, et il répond critère par critère : ✅ oui, ❌ non, ❓ doute.
"""

import asyncio
import base64
import logging
import os
import sys

import anthropic
from telegram import Update
from telegram.constants import ChatAction
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from criteres import CRITERES, MODELE

logging.basicConfig(format="%(asctime)s %(levelname)s %(message)s", level=logging.INFO)
log = logging.getLogger("gla_bot")

TELEGRAM_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
# Liste d'identifiants Telegram autorisés, séparés par des virgules.
# Vide = tout le monde peut utiliser le bot (déconseillé : ça coûte des appels API).
ALLOWED_IDS = {int(x) for x in os.environ.get("ALLOWED_CHAT_IDS", "").replace(" ", "").split(",") if x}

MODEL = "claude-opus-5-5"
client = anthropic.AsyncAnthropic()

liste_criteres = "\n".join(
    f"{i}. {c['nom']} (peut aussi s'écrire : {c['aussi_appele']})" for i, c in enumerate(CRITERES, 1)
)

SYSTEM_PROMPT = f"""Tu aides une personne à trouver une voiture d'occasion : un {MODELE}.
Elle t'envoie des annonces (lien, texte copié ou captures d'écran, souvent de sites allemands
comme mobile.de ou de sites français). Tu vérifies si l'annonce remplit ses critères.

Critères :
{liste_criteres}

Méthode :
- Si un lien est fourni, lis la page avec l'outil web_fetch. Si la page est inaccessible ou vide,
  dis-le clairement et demande des captures d'écran de la liste d'équipements.
- Lis toute la liste d'équipements. Les annonces allemandes utilisent les noms allemands.
- ✅ = l'annonce le mentionne clairement.
- ❌ = absent de l'annonce alors que la liste d'équipements semble complète, ou clairement contredit
  (ex. autre couleur).
- ❓ = doute : pas mentionné mais la liste semble incomplète, mention ambiguë, ou seulement déduit
  (ex. inclus normalement dans un pack). Explique toujours le doute en quelques mots.
- Ne devine jamais : en cas d'hésitation, mets ❓.
- Vérifie aussi que c'est bien un GLA (et pas un GLB, GLC...). Sinon, signale-le en premier.

Réponds en français simple, pour une personne non technicienne, en texte brut pour Telegram
(pas de Markdown, pas de tableaux, pas de **). Format exact :

🚗 <modèle, année, kilométrage et prix si trouvés>

✅ / ❌ / ❓ <critère> : <précision courte si utile>
(une ligne par critère, dans l'ordre de la liste)

Bilan : <X critères sur {len(CRITERES)} confirmés>

⚠️ Points à vérifier avec le vendeur :
- <chaque doute, sous forme de question à poser>
(omets cette section s'il n'y a aucun doute)
"""

TOOLS = [{"type": "web_fetch_20260209", "name": "web_fetch", "max_uses": 5}]

# Regroupe les photos envoyées ensemble (album Telegram) avant analyse.
_albums: dict[str, dict] = {}


async def analyser(content: list[dict]) -> str:
    """Envoie l'annonce à Claude et renvoie le texte de la réponse."""
    messages = [{"role": "user", "content": content}]
    for _ in range(5):  # boucle seulement si l'API met le tour en pause (outil web)
        async with client.beta.messages.stream(
            model=MODEL,
            max_tokens=16000,
            system=SYSTEM_PROMPT,
            tools=TOOLS,
            output_config={"effort": "high"},
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
            messages=messages,
        ) as stream:
            response = await stream.get_final_message()
        if response.stop_reason == "pause_turn":
            messages.append({"role": "assistant", "content": response.content})
            continue
        break

    if response.stop_reason == "refusal":
        return "Désolé, je n'ai pas pu analyser cette annonce. Essaie avec des captures d'écran."
    texte = "\n".join(b.text for b in response.content if b.type == "text").strip()
    return texte or "Je n'ai rien pu lire dans cette annonce. Essaie avec des captures d'écran."


async def repondre(update: Update, context: ContextTypes.DEFAULT_TYPE, content: list[dict]) -> None:
    chat_id = update.effective_chat.id
    await context.bot.send_message(chat_id, "🔎 Je regarde l'annonce, ça prend environ une minute...")
    await context.bot.send_chat_action(chat_id, ChatAction.TYPING)
    try:
        texte = await analyser(content)
    except anthropic.APIError:
        log.exception("Erreur API Claude")
        texte = "Oups, une erreur s'est produite. Réessaie dans quelques minutes."
    # Telegram limite un message à 4096 caractères.
    for i in range(0, len(texte), 4000):
        await context.bot.send_message(chat_id, texte[i : i + 4000])


def autorise(update: Update) -> bool:
    return not ALLOWED_IDS or update.effective_user.id in ALLOWED_IDS


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    criteres = "\n".join(f"• {c['nom']}" for c in CRITERES)
    await update.message.reply_text(
        f"Bonjour ! Envoie-moi une annonce de {MODELE} :\n"
        "• un lien (mobile.de, autoscout24, leboncoin...)\n"
        "• ou le texte de l'annonce copié-collé\n"
        "• ou des captures d'écran (plusieurs d'un coup, c'est possible)\n\n"
        f"Je vérifie ces critères :\n{criteres}\n\n"
        f"Ton identifiant Telegram : {update.effective_user.id}"
    )


async def texte(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not autorise(update):
        return
    await repondre(update, context, [{"type": "text", "text": "Voici l'annonce :\n\n" + update.message.text}])


async def _image_block(context: ContextTypes.DEFAULT_TYPE, file_id: str, media_type: str) -> dict:
    fichier = await context.bot.get_file(file_id)
    data = await fichier.download_as_bytearray()
    return {
        "type": "image",
        "source": {"type": "base64", "media_type": media_type, "data": base64.standard_b64encode(data).decode()},
    }


async def photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not autorise(update):
        return
    msg = update.message
    if msg.photo:
        bloc = await _image_block(context, msg.photo[-1].file_id, "image/jpeg")
    else:  # image envoyée comme fichier
        bloc = await _image_block(context, msg.document.file_id, msg.document.mime_type or "image/jpeg")
    legende = msg.caption or ""

    if not msg.media_group_id:
        await repondre(update, context, [bloc, {"type": "text", "text": "Captures de l'annonce. " + legende}])
        return

    # Album : on attend que toutes les photos arrivent, puis on analyse une seule fois.
    album = _albums.setdefault(msg.media_group_id, {"blocs": [], "legende": ""})
    album["blocs"].append(bloc)
    album["legende"] += legende
    if len(album["blocs"]) == 1:
        await asyncio.sleep(3)
        album = _albums.pop(msg.media_group_id)
        content = album["blocs"] + [{"type": "text", "text": "Captures de l'annonce. " + album["legende"]}]
        await repondre(update, context, content)


async def traiter_en_attente(app) -> None:
    """Mode GitHub Actions : lit les messages reçus depuis le dernier passage,
    répond à chacun, confirme leur lecture à Telegram, puis s'arrête."""
    async with app:
        updates = await app.bot.get_updates(timeout=0)
        log.info("%d message(s) en attente", len(updates))
        if not updates:
            return
        # En parallèle, pour que les photos d'un même album soient regroupées.
        await asyncio.gather(*(app.process_update(u) for u in updates), return_exceptions=True)
        # Marque ces messages comme lus pour ne pas y répondre deux fois.
        await app.bot.get_updates(offset=updates[-1].update_id + 1, timeout=0)


def main() -> None:
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).concurrent_updates(True).build()
    app.add_handler(CommandHandler(["start", "aide"], start))
    app.add_handler(MessageHandler(filters.PHOTO | filters.Document.IMAGE, photo))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, texte))
    if "--once" in sys.argv:
        asyncio.run(traiter_en_attente(app))
        return
    log.info("Bot démarré")
    app.run_polling()


if __name__ == "__main__":
    main()
