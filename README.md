# Bot Telegram : vérification d'annonces Mercedes GLA

On envoie au bot une annonce (lien, texte copié ou captures d'écran) et il répond
critère par critère : ✅ présent, ❌ absent, ❓ doute (avec la question à poser au vendeur).
Chaque annonce est ajoutée à la page de suivi : https://casicoco.github.io/gla-bot/

- `criteres.py` : la liste des critères (facile à modifier)
- `lecteur.py` : ouvre la page dans Chrome, accepte les cookies, déplie les « voir plus »
- `suivi.py` : enregistre chaque annonce dans `docs/annonces.json` (la page de suivi)

## Pourquoi le bot tourne à la maison

mobile.de bloque les serveurs (GitHub, hébergeurs…) mais accepte les connexions
de particuliers. Le bot tourne donc sur un ordinateur à la maison, qui doit rester allumé.

## Installation (une seule fois, Mac ou Linux)

```bash
gh repo clone casicoco/gla-bot ~/gla-bot
cd ~/gla-bot
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python -m playwright install chromium
cp .env.example .env
```

Puis remplir `.env` (token Telegram, clé Claude, identifiants autorisés).
Sur Windows, remplacer `.venv/bin/` par `.venv\Scripts\`.

## Lancer le bot

```bash
cd ~/gla-bot && git pull && .venv/bin/python bot.py
```

Laisser la fenêtre ouverte. Pour arrêter : Ctrl+C.

Ne pas lancer en même temps le workflow GitHub `bot.yml` (secours) : Telegram refuse deux
bots actifs en même temps.

## Astuce

Si un site bloque quand même la lecture, le bot le dit : il suffit d'envoyer des captures
d'écran de l'annonce ou de copier-coller son texte.
