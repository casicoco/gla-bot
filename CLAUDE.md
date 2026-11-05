# Préférences

- Pour créer un repo GitHub, donner directement la commande `gh repo create <nom> --private`
  (création sur GitHub uniquement).
- Ne jamais proposer de cloner un repo en local, sauf si ça sert vraiment à quelque chose
  (et dans ce cas, expliquer pourquoi).
- Toujours donner les lignes de commande (CLI : gh, railway, etc.) plutôt que des étapes
  à cliquer dans une interface web.

# Liens en attente (« gère les liens en attente »)

Le bot GitHub met en attente les annonces qu'il ne peut pas ouvrir (mobile.de bloque les
serveurs) dans `docs/en_attente.json`. Elles doivent être traitées depuis l'ordinateur de la
maison, dont la connexion est acceptée par mobile.de. Quand l'utilisateur dit
« gère les liens en attente » (ou équivalent) dans une session sur son ordinateur :

1. Si `.venv/` n'existe pas encore (première fois), installer :
   `python3 -m venv .venv && .venv/bin/pip install -r requirements.txt && .venv/bin/python -m playwright install chromium`
   (sur Windows : `.venv\Scripts\` au lieu de `.venv/bin/`).
2. Si `.env` n'existe pas, le créer depuis `.env.example` et demander à l'utilisateur de remplir
   `TELEGRAM_BOT_TOKEN`, `ANTHROPIC_API_KEY` et `ALLOWED_CHAT_IDS` lui-même (ne pas lui demander
   de coller les clés dans la conversation). Garder `NAVIGATEUR=chrome`.
3. Lancer : `git pull && .venv/bin/python traiter_attente.py`
4. Résumer en une ou deux phrases : combien de liens traités, combien encore bloqués.
   Les analyses partent toutes seules sur Telegram, pas besoin de les recopier.

Ne pas lancer `bot.py` sur l'ordinateur : le bot tourne déjà sur GitHub, et Telegram refuse deux
bots actifs en même temps. `traiter_attente.py` ne pose pas ce problème.
