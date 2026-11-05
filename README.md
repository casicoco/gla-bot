# Bot Telegram : vérification d'annonces Mercedes GLA

On envoie au bot une annonce (lien, texte copié ou captures d'écran) et il répond
critère par critère : ✅ présent, ❌ absent, ❓ doute (avec la question à poser au vendeur).

Les critères sont dans `criteres.py` (faciles à modifier).

## Mise en place

1. **Créer le bot Telegram** : dans Telegram, écrire à `@BotFather`, envoyer `/newbot`,
   choisir un nom. BotFather donne un *token*.
2. **Clé Claude** : créer une clé sur https://platform.claude.com (section API keys).
3. **Installer et lancer** :

```bash

python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # puis remplir les valeurs
set -a && source .env && set +a
python bot.py
```

4. Dans Telegram, ouvrir le bot et envoyer `/start` : il affiche l'identifiant Telegram.
   Mettre l'identifiant de maman (et le tien) dans `ALLOWED_CHAT_IDS`, puis relancer.
   Comme ça, personne d'autre ne peut utiliser le bot (et consommer la clé API).

## Le faire tourner en permanence

Le bot doit tourner en continu pour répondre. Options : un ordinateur toujours allumé,
un Raspberry Pi, ou un hébergeur (Railway, Render, Fly.io...) avec la commande `python bot.py`
et les 3 variables d'environnement.

## Astuce

Certains sites (mobile.de notamment) bloquent parfois la lecture automatique des pages.
Dans ce cas le bot le dit : il suffit d'envoyer des captures d'écran de la liste d'équipements.
