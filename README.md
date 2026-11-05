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

## Hébergement : GitHub Actions

Le bot tourne en continu sur GitHub Actions (`.github/workflows/bot.yml`), gratuitement
car le repo est public. Il répond en environ une minute. GitHub coupe un job au bout
de 6 heures : le bot s'arrête donc tout seul toutes les ~5 h 45 et un nouveau lancement
prend le relais (quelques minutes de coupure au maximum, aucun message perdu).

Enregistrer les clés en secrets du repo :

```bash
gh secret set TELEGRAM_BOT_TOKEN --repo casicoco/gla-bot
gh secret set ANTHROPIC_API_KEY --repo casicoco/gla-bot
gh secret set ALLOWED_CHAT_IDS --repo casicoco/gla-bot --body "<id1>,<id2>"
```

Relancer le bot à la main (s'il ne répond plus) :

```bash
gh workflow run bot.yml --repo casicoco/gla-bot
```

Bon à savoir : GitHub met en pause les tâches planifiées d'un repo sans aucun commit
pendant 60 jours. Il suffit alors de la réactiver avec
`gh workflow enable bot.yml --repo casicoco/gla-bot`.

## Astuce

Certains sites (mobile.de notamment) bloquent parfois la lecture automatique des pages.
Dans ce cas le bot le dit : il suffit d'envoyer des captures d'écran de la liste d'équipements.
