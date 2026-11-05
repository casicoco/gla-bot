# Bot Telegram : vérification d'annonces Mercedes GLA

On envoie au bot une annonce (lien, texte copié ou captures d'écran) et il répond
critère par critère : ✅ présent, ❌ absent, ❓ doute (avec la question à poser au vendeur).
Chaque annonce est ajoutée à la page de suivi : https://casicoco.github.io/gla-bot/

- `criteres.py` : la liste des critères (facile à modifier)
- `lecteur.py` : ouvre la page dans Chrome, accepte les cookies, déplie les « voir plus »
- `suivi.py` : enregistre chaque annonce dans `docs/annonces.json` (la page de suivi)

## Fonctionnement

Le bot tourne en continu sur GitHub Actions (`.github/workflows/bot.yml`).
mobile.de bloque les serveurs : quand un lien ne s'ouvre pas, le bot le met
**en attente** (`docs/en_attente.json`, visible sur la page de suivi et avec `/attente`
dans Telegram). On les traite ensuite depuis l'ordinateur de la maison, dont la
connexion est acceptée par mobile.de. Les réponses arrivent sur Telegram comme d'habitude.

## Traiter les liens en attente (ordinateur de la maison)

Première fois seulement (Mac ou Linux) :

```bash
gh repo clone casicoco/gla-bot ~/gla-bot
cd ~/gla-bot && python3 -m venv .venv && .venv/bin/pip install -r requirements.txt && .venv/bin/python -m playwright install chromium
cp .env.example .env
```

Remplir `.env` (mêmes clés que sur GitHub, garder `NAVIGATEUR=chrome`).
Sur Windows, remplacer `.venv/bin/` par `.venv\Scripts\`.

Ensuite, à chaque fois :

```bash
cd ~/gla-bot && git pull && .venv/bin/python traiter_attente.py
```

Le script s'arrête tout seul quand tous les liens sont traités. Le bot sur GitHub peut
continuer à tourner pendant ce temps.

## Astuce

Si un site bloque même depuis la maison, le lien reste en attente : il suffit alors
d'envoyer des captures d'écran de l'annonce ou de copier-coller son texte.
