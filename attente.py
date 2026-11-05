"""Liens en attente : annonces que le bot n'a pas pu ouvrir depuis GitHub
(mobile.de bloque les serveurs). On les traite plus tard depuis l'ordinateur
de la maison avec : python traiter_attente.py
"""

import asyncio
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import suivi

FICHIER = Path(__file__).parent / "docs" / "en_attente.json"


def charger() -> list[dict]:
    try:
        return json.loads(FICHIER.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return []


def sauver(liens: list[dict], message: str) -> None:
    FICHIER.parent.mkdir(exist_ok=True)
    FICHIER.write_text(json.dumps(liens, ensure_ascii=False, indent=2))
    try:
        suivi.pousser(message, [FICHIER])
    except subprocess.CalledProcessError as e:
        suivi.log.error("Impossible de pousser les liens en attente : %s", e.stderr)


async def ajouter(chat_id: int, url: str, message: str) -> int:
    """Met un lien en attente (sans doublon). Renvoie le nombre de liens en attente."""
    async with suivi.verrou:
        await asyncio.to_thread(suivi.synchroniser)
        liens = charger()
        if not any(l["url"] == url for l in liens):
            liens.append({
                "url": url,
                "chat_id": chat_id,
                "message": message,
                "date": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M"),
            })
            await asyncio.to_thread(sauver, liens, "Lien mis en attente")
        return len(liens)
