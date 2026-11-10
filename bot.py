"""Bot Telegram qui vérifie les annonces de Mercedes GLA.

On envoie au bot un lien, un texte copié ou des captures d'écran
d'une annonce, et il répond critère par critère : ✅ oui, ❌ non, ❓ doute.
"""

import asyncio
import base64
import logging
import os
import re

import anthropic
import json

from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
    Update,
    WebAppInfo,
)
from telegram.constants import ChatAction
from telegram.ext import (
    CallbackQueryHandler,
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from pathlib import Path

# Charge les clés depuis le fichier .env s'il existe (utile sur ton ordinateur).
_env = Path(__file__).parent / ".env"
if _env.exists():
    for _ligne in _env.read_text().splitlines():
        if "=" in _ligne and not _ligne.lstrip().startswith("#"):
            _cle, _val = _ligne.split("=", 1)
            os.environ.setdefault(_cle.strip(), _val.strip())

from criteres import CRITERES, MODELE
from lecteur import lire, trouver_liens
import attente
import suivi
from suivi import enregistrer

logging.basicConfig(format="%(asctime)s %(levelname)s %(message)s", level=logging.INFO)
log = logging.getLogger("gla_bot")
# Les journaux de httpx affichent les adresses Telegram, qui contiennent le token du bot.
logging.getLogger("httpx").setLevel(logging.WARNING)

TELEGRAM_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
# Liste d'identifiants Telegram autorisés, séparés par des virgules.
# Vide = tout le monde peut utiliser le bot (déconseillé : ça coûte des appels API).
ALLOWED_IDS = {int(x) for x in os.environ.get("ALLOWED_CHAT_IDS", "").replace(" ", "").split(",") if x}

MODEL = "claude-opus-5-5"
_depot = os.environ.get("GITHUB_REPOSITORY", "")
if not _depot:  # sur l'ordinateur : on le déduit du dépôt git (ex. casicoco/gla-bot)
    import subprocess
    _origine = subprocess.run(["git", "remote", "get-url", "origin"], cwd=Path(__file__).parent,
                              capture_output=True, text=True).stdout
    _m = re.search(r"github\.com[:/]([^/]+/[^/.\s]+)", _origine)
    _depot = _m.group(1) if _m else ""
PAGE_SUIVI = f"https://{_depot.split('/')[0]}.github.io/{_depot.split('/')[1]}/" if "/" in _depot else ""
client = anthropic.AsyncAnthropic(max_retries=5)

liste_criteres = "\n".join(
    f"{i}. {c['nom']} (peut aussi s'écrire : {c['aussi_appele']})" for i, c in enumerate(CRITERES, 1)
)

SYSTEM_PROMPT = f"""Tu aides une personne à trouver une voiture d'occasion : un {MODELE}.
Elle t'envoie des annonces (lien, texte copié ou captures d'écran, souvent de sites allemands
comme mobile.de ou de sites français). Tu vérifies si l'annonce remplit ses critères.

Critères :
{liste_criteres}

Méthode :
- Quand un lien est envoyé, le contenu complet de la page t'est fourni (lu avec un navigateur,
  tous les « voir plus » déjà dépliés) avec une capture du haut de la page. Utilise-le en priorité.
- Si la page n'a pas pu être lue (site bloqué), essaie l'outil web_fetch. Si ça ne marche pas
  non plus, dis-le clairement et demande des captures d'écran de la liste d'équipements.
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


async def analyser(content: list[dict]) -> str | None:
    """Envoie l'annonce à Claude et renvoie le texte de la réponse (None si échec)."""
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
        return None
    texte = "\n".join(b.text for b in response.content if b.type == "text").strip()
    return texte or None


def clavier_suivi():
    """Bouton en bas de Telegram qui ouvre la page de suivi dans Telegram (modifiable)."""
    if not PAGE_SUIVI:
        return None
    return ReplyKeyboardMarkup(
        [[KeyboardButton("📋 Suivi des annonces", web_app=WebAppInfo(url=PAGE_SUIVI))]],
        resize_keyboard=True,
        is_persistent=True,
    )


def boutons_annonce(fiche: dict) -> InlineKeyboardMarkup:
    """Boutons 👍 / 👎 / 🗄 sous une annonce ; le choix actuel est coché."""
    i, interet, archivee = fiche["id"], fiche.get("interet"), fiche.get("archivee", False)
    return InlineKeyboardMarkup([[
        InlineKeyboardButton(("✓ " if interet == "oui" else "") + "👍 Intéresse", callback_data=f"s:{i}:interet:oui"),
        InlineKeyboardButton(("✓ " if interet == "non" else "") + "👎 Non", callback_data=f"s:{i}:interet:non"),
        InlineKeyboardButton(("✓ " if archivee else "") + "🗄 Archiver", callback_data=f"s:{i}:archivee:{'0' if archivee else '1'}"),
    ]])


async def bouton_annonce(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Clic sur 👍 / 👎 / 🗄 sous une annonce."""
    q = update.callback_query
    if ALLOWED_IDS and q.from_user.id not in ALLOWED_IDS:
        await q.answer()
        return
    try:
        _, ident, champ, valeur = q.data.split(":")
        ident = int(ident)
    except ValueError:
        await q.answer()
        return
    fiche = next((a for a in suivi.charger() if a["id"] == ident), {"id": ident})
    if champ == "interet":
        nouveau = None if fiche.get("interet") == valeur else valeur  # recliquer = annuler
        changement = {"id": ident, "interet": nouveau}
        texte_ok = {"oui": "👍 Noté : elle t'intéresse", "non": "👎 Noté : elle ne t'intéresse pas", None: "Choix annulé"}[nouveau]
    else:
        changement = {"id": ident, "archivee": valeur == "1"}
        texte_ok = "🗄 Annonce archivée" if valeur == "1" else "Annonce sortie des archives"
    await suivi.modifier([changement])
    await q.answer(texte_ok)
    fiche.update({k: v for k, v in changement.items() if k != "id"})
    try:
        await q.edit_message_reply_markup(boutons_annonce(fiche))
    except Exception:
        pass


async def depuis_la_page(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Données envoyées par la page de suivi ouverte dans Telegram (bouton « Enregistrer »)."""
    if not autorise(update):
        return
    try:
        donnees = json.loads(update.effective_message.web_app_data.data)
    except (ValueError, AttributeError):
        await update.effective_message.reply_text("Je n'ai pas compris les changements envoyés.")
        return
    changements = donnees.get("changements") if isinstance(donnees, dict) else None
    liens = donnees.get("liens") if isinstance(donnees, dict) else None
    n = await suivi.modifier(changements) if isinstance(changements, list) else 0
    liens = [l for l in (liens or []) if isinstance(l, str) and l.startswith(("http://", "https://"))][:5]
    if n:
        await update.effective_message.reply_text(
            f"✅ {n} changement(s) enregistré(s). La page sera à jour dans une à deux minutes.",
            reply_markup=clavier_suivi(),
        )
    for lien in liens:
        await traiter_texte(update, context, lien)
    if not n and not liens:
        await update.effective_message.reply_text("Aucun changement à enregistrer.", reply_markup=clavier_suivi())


async def ouvrir_suivi(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not autorise(update):
        return
    await update.message.reply_text(
        "Appuie sur « 📋 Suivi des annonces » en bas pour ouvrir le tableau. Depuis Telegram, tu peux "
        "marquer les voitures qui t'intéressent, les archiver, ajouter une note ou proposer un lien.",
        reply_markup=clavier_suivi(),
    )


async def enregistrer_et_annoncer(bot, chat_id: int, source: str, rapport: str, annoncer: bool = True):
    """Ajoute l'annonce au suivi et prévient sur Telegram.

    Renvoie la fiche, None si ce n'était pas une annonce, ou False si l'enregistrement a échoué.
    """
    try:
        fiche = await enregistrer(client, source, rapport)
    except Exception:
        log.exception("Erreur lors de l'enregistrement dans le suivi")
        return False
    if fiche and annoncer:
        lien = f"\nTableau de suivi : {PAGE_SUIVI}" if PAGE_SUIVI else ""
        await bot.send_message(
            chat_id,
            f"📋 Ajoutée au suivi (annonce n°{fiche['id']})\n"
            f"Décision : {fiche['decision']}\n{fiche['raison']}{lien}",
            reply_markup=boutons_annonce(fiche),
        )
    return fiche


async def traiter(bot, chat_id: int, content: list[dict], source: str = "",
                  envoyer_rapport: bool = True, annoncer: bool = True) -> dict:
    """Analyse une annonce, envoie le rapport sur Telegram et l'ajoute au suivi.

    Renvoie {"rapport": texte ou None, "enregistre": bool, "fiche": dict ou None}.
    """
    if envoyer_rapport:
        await bot.send_message(chat_id, "🔎 Je regarde l'annonce, ça prend environ une minute...")
        await bot.send_chat_action(chat_id, ChatAction.TYPING)
    try:
        rapport = await analyser(content)
    except anthropic.APIError:
        log.exception("Erreur API Claude")
        if envoyer_rapport:
            await bot.send_message(chat_id, "Oups, une erreur s'est produite. Réessaie dans quelques minutes.")
        return {"rapport": None, "enregistre": False, "fiche": None}
    if not rapport:
        if envoyer_rapport:
            await bot.send_message(chat_id, "Désolé, je n'ai pas pu lire cette annonce. Essaie avec des captures d'écran.")
        return {"rapport": None, "enregistre": False, "fiche": None}
    if envoyer_rapport:
        # Telegram limite un message à 4096 caractères.
        for i in range(0, len(rapport), 4000):
            await bot.send_message(chat_id, rapport[i : i + 4000])
    fiche = await enregistrer_et_annoncer(bot, chat_id, source, rapport, annoncer)
    return {"rapport": rapport, "enregistre": fiche is not False, "fiche": fiche or None}


async def repondre(update: Update, context: ContextTypes.DEFAULT_TYPE, content: list[dict], source: str = "") -> None:
    await traiter(context.bot, update.effective_chat.id, content, source)


async def contenu_des_liens(liens: list[str]) -> tuple[list[dict], list[str]]:
    """Ouvre chaque lien. Renvoie le contenu lisible et la liste des liens bloqués."""
    content: list[dict] = []
    bloques: list[str] = []
    for url in liens:
        try:
            page = await lire(url)
        except Exception:
            log.exception("Lecture impossible : %s", url[:80])
            bloques.append(url)
            continue
        if page.bloquee:
            bloques.append(url)
            continue
        if page.capture:
            content.append({
                "type": "image",
                "source": {"type": "base64", "media_type": "image/jpeg",
                           "data": base64.standard_b64encode(page.capture).decode()},
            })
        content.append({"type": "text", "text": f"Contenu de la page {url}\n\n{page.texte}"})
    return content, bloques


def autorise(update: Update) -> bool:
    return not ALLOWED_IDS or update.effective_user.id in ALLOWED_IDS


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    criteres = "\n".join(f"• {c['nom']}" for c in CRITERES)
    await update.message.reply_text(
        f"Bonjour ! Envoie-moi une annonce de {MODELE} :\n"
        "• un lien (mobile.de, autoscout24, leboncoin...)\n"
        "• ou le texte de l'annonce copié-collé\n"
        "• ou des captures d'écran (plusieurs d'un coup, c'est possible)\n\n"
        "Si un site bloque la lecture, je mets le lien en attente (/attente pour les voir).\n\n"
        f"Je vérifie ces critères :\n{criteres}\n\n"
        f"Ton identifiant Telegram : {update.effective_user.id}\n\n"
        "📋 Le bouton « Suivi des annonces » en bas ouvre le tableau de suivi.",
        reply_markup=clavier_suivi(),
    )


# Telegram coupe les messages trop longs (plus de 4 096 caractères) en plusieurs morceaux.
# On regroupe les morceaux qui arrivent à la suite avant d'analyser.
_morceaux: dict[int, dict] = {}
ATTENTE_MORCEAUX = 4  # secondes sans nouveau message avant d'analyser


async def texte(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not autorise(update):
        return
    chat = update.effective_chat.id
    groupe = _morceaux.get(chat)
    if groupe:  # suite d'un message coupé : le premier morceau s'occupe de tout
        groupe["textes"].append(update.message.text)
        groupe["dernier"] = asyncio.get_running_loop().time()
        return
    boucle = asyncio.get_running_loop()
    groupe = _morceaux[chat] = {"textes": [update.message.text], "dernier": boucle.time()}
    while boucle.time() - groupe["dernier"] < ATTENTE_MORCEAUX:
        await asyncio.sleep(0.5)
    _morceaux.pop(chat, None)
    await traiter_texte(update, context, "\n".join(groupe["textes"]))


async def traiter_texte(update: Update, context: ContextTypes.DEFAULT_TYPE, message: str) -> None:
    liens = trouver_liens(message)[:3]
    reste = message
    for url in liens:
        reste = reste.replace(url, "")
    # Texte d'annonce collé (par exemple recopié depuis Chrome) : il contient déjà tout,
    # inutile d'ouvrir le lien (et mobile.de le bloquerait).
    texte_colle = len(reste.strip()) > 1000
    if not liens and len(reste.strip()) < 300:
        # Simple question ou message court, pas une annonce : pas d'analyse (ni d'appel payant).
        await update.message.reply_text(
            "Pour vérifier une annonce, envoie-moi son lien, son texte complet copié-collé, "
            "ou des captures d'écran.\n\n"
            "Pour voir et modifier le tableau de suivi, appuie sur la barre « 📋 Suivi des annonces » "
            "tout en bas de la conversation (sous le champ où tu écris).",
            reply_markup=clavier_suivi(),
        )
        return
    content, bloques = ([], []) if texte_colle else await contenu_des_liens(liens)

    for url in bloques:
        nb = await attente.ajouter(update.effective_chat.id, url, message)
    if bloques:
        await update.message.reply_text(
            "⏳ Ce site bloque la lecture depuis le serveur (mobile.de fait ça). "
            f"J'ai mis le lien en attente ({nb} lien(s) en attente en tout).\n"
            "Il sera traité dès qu'on lancera le bot depuis l'ordinateur de la maison. "
            "Tu recevras la réponse ici. En attendant, tu peux aussi m'envoyer des captures d'écran."
        )
        # Rien d'autre à analyser : pas de page lue et le message n'est que le lien.
        if not content and len(reste.strip()) < 40:
            return

    content.append({"type": "text", "text": "Message envoyé :\n\n" + message})
    await repondre(update, context, content, message)


async def voir_attente(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not autorise(update):
        return
    await asyncio.to_thread(suivi.synchroniser)
    liens = attente.charger()
    if not liens:
        await update.message.reply_text("✅ Aucun lien en attente.")
        return
    lignes = "\n".join(f"{i}. {l['date']} : {l['url'][:80]}…" for i, l in enumerate(liens, 1))
    await update.message.reply_text(
        f"⏳ {len(liens)} lien(s) en attente :\n{lignes}\n\n"
        "Pour les traiter, sur l'ordinateur : python traiter_attente.py"
    )


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
        await repondre(update, context, [bloc, {"type": "text", "text": "Captures de l'annonce. " + legende}], legende)
        return

    # Album : on attend que toutes les photos arrivent, puis on analyse une seule fois.
    album = _albums.setdefault(msg.media_group_id, {"blocs": [], "legende": ""})
    album["blocs"].append(bloc)
    album["legende"] += legende
    if len(album["blocs"]) == 1:
        await asyncio.sleep(3)
        album = _albums.pop(msg.media_group_id)
        content = album["blocs"] + [{"type": "text", "text": "Captures de l'annonce. " + album["legende"]}]
        await repondre(update, context, content, album["legende"])


def main() -> None:
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).concurrent_updates(True).build()
    app.add_handler(CommandHandler(["start", "aide"], start))
    app.add_handler(CommandHandler("attente", voir_attente))
    app.add_handler(CommandHandler("suivi", ouvrir_suivi))
    app.add_handler(MessageHandler(filters.StatusUpdate.WEB_APP_DATA, depuis_la_page))
    app.add_handler(CallbackQueryHandler(bouton_annonce, pattern=r"^s:"))
    app.add_handler(MessageHandler(filters.PHOTO | filters.Document.IMAGE, photo))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, texte))
    log.info("Bot démarré")
    app.run_polling()


if __name__ == "__main__":
    main()
