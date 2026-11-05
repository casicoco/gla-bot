"""Base de suivi des annonces.

Après chaque analyse, on transforme le rapport en fiche structurée, on l'ajoute
à docs/annonces.json, puis on pousse le fichier sur GitHub. La page
docs/index.html (GitHub Pages) affiche le tableau comparatif.
"""

import asyncio
import json
import logging
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal, Optional

import anthropic
from pydantic import BaseModel, Field

from criteres import CRITERES, MODELE

log = logging.getLogger("gla_bot")

FICHIER = Path(__file__).parent / "docs" / "annonces.json"
MODEL = "claude-opus-5-5"
_verrou = asyncio.Lock()


class StatutCritere(BaseModel):
    critere: str = Field(description="Nom exact du critère, tel que dans la liste")
    statut: Literal["oui", "non", "doute"]
    detail: str = Field(description="Précision courte, ou chaîne vide")


class Fiche(BaseModel):
    est_une_annonce: bool = Field(description="False si le rapport dit que l'annonce n'a pas pu être lue")
    titre: str = Field(description="Ex. 'Mercedes GLA 200 AMG Line'")
    annee: Optional[int]
    kilometrage: Optional[int] = Field(description="En km")
    prix: Optional[int] = Field(description="En euros")
    vendeur: str = Field(description="Concession ou particulier, ville et pays si connus, sinon chaîne vide")
    url: str = Field(description="Lien de l'annonce si connu, sinon chaîne vide")
    criteres: list[StatutCritere]
    points_forts: list[str]
    points_faibles: list[str]
    questions_vendeur: list[str]
    decision: Literal["À contacter", "À étudier", "À écarter"]
    raison: str = Field(description="2 ou 3 phrases simples qui justifient la décision, en comparant aux autres annonces")


def charger() -> list[dict]:
    try:
        return json.loads(FICHIER.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return []


def _resume(annonces: list[dict]) -> str:
    if not annonces:
        return "Aucune autre annonce pour l'instant."
    lignes = []
    for a in annonces:
        oui = sum(c["statut"] == "oui" for c in a["criteres"])
        lignes.append(
            f"- #{a['id']} {a['titre']}, {a.get('annee')}, {a.get('kilometrage')} km, {a.get('prix')} €, "
            f"{oui}/{len(CRITERES)} critères confirmés, décision : {a['decision']}"
        )
    return "\n".join(lignes)


async def _extraire(client: anthropic.AsyncAnthropic, source: str, rapport: str, annonces: list[dict]) -> Fiche:
    noms = "\n".join(f"- {c['nom']}" for c in CRITERES)
    prompt = f"""Voici le rapport d'analyse d'une annonce de {MODELE}, et ce que la personne a envoyé.
Transforme-le en fiche de suivi.

Critères (un statut par critère, dans cet ordre, noms exacts) :
{noms}

Décision :
- "À contacter" : bonne candidate, mérite un appel au vendeur.
- "À étudier" : intéressante mais doutes importants ou prix à discuter.
- "À écarter" : pas un GLA, mauvaise couleur, trop de critères manquants, ou nettement moins
  bien que d'autres annonces pour un prix comparable.
Compare avec les annonces déjà suivies pour justifier la décision.

Annonces déjà suivies :
{_resume(annonces)}

Ce que la personne a envoyé :
{source or "(captures d'écran)"}

Rapport :
{rapport}"""
    response = await client.messages.parse(
        model=MODEL,
        max_tokens=16000,
        output_config={"effort": "low"},
        messages=[{"role": "user", "content": prompt}],
        output_format=Fiche,
    )
    return response.parsed_output


def _pousser(message: str) -> None:
    """Pousse docs/annonces.json sur GitHub (seulement quand le bot tourne dans GitHub Actions)."""
    if not os.environ.get("GITHUB_ACTIONS"):
        return
    racine = FICHIER.parent.parent
    cmds = [
        ["git", "config", "user.name", "gla-bot"],
        ["git", "config", "user.email", "gla-bot@users.noreply.github.com"],
        ["git", "add", str(FICHIER)],
        ["git", "commit", "-m", message],
        ["git", "pull", "--rebase", "origin", "main"],
        ["git", "push", "origin", "HEAD:main"],
    ]
    for cmd in cmds:
        subprocess.run(cmd, cwd=racine, check=True, capture_output=True)


async def enregistrer(client: anthropic.AsyncAnthropic, source: str, rapport: str) -> Optional[dict]:
    """Ajoute (ou met à jour) l'annonce dans la base. Renvoie la fiche, ou None si rien à enregistrer."""
    async with _verrou:
        annonces = charger()
        fiche = await _extraire(client, source, rapport, annonces)
        if not fiche.est_une_annonce:
            return None
        data = fiche.model_dump(exclude={"est_une_annonce"})
        data["date"] = datetime.now(timezone.utc).strftime("%Y-%m-%d")

        existante = next((a for a in annonces if data["url"] and a.get("url") == data["url"]), None)
        if existante:
            data["id"] = existante["id"]
            annonces[annonces.index(existante)] = data
        else:
            data["id"] = max((a["id"] for a in annonces), default=0) + 1
            annonces.append(data)

        FICHIER.parent.mkdir(exist_ok=True)
        FICHIER.write_text(json.dumps(annonces, ensure_ascii=False, indent=2))
        try:
            await asyncio.to_thread(_pousser, f"Annonce #{data['id']} : {data['titre']}")
        except subprocess.CalledProcessError as e:
            log.error("Impossible de pousser la base : %s", e.stderr)
        return data
