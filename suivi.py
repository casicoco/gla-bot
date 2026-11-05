"""Base de suivi des annonces.

Après chaque analyse, on transforme le rapport en fiche structurée, on l'ajoute
à docs/annonces.json, puis on pousse le fichier sur GitHub. La page
docs/index.html (GitHub Pages) affiche le tableau comparatif.
"""

import asyncio
import json
import logging
import os
import re
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
verrou = asyncio.Lock()  # une seule écriture à la fois dans les fichiers du repo


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


def _cle_url(url: str) -> str:
    """Identifiant stable d'un lien : l'id de l'annonce (mobile.de) ou le lien sans paramètres."""
    if not url:
        return ""
    m = re.search(r"[?&]id=(\d+)", url)
    return m.group(1) if m else url.split("?")[0].rstrip("/")


def meme_voiture(a: dict, b: dict) -> bool:
    """Même annonce si même lien, ou même prix, kilométrage et année."""
    if _cle_url(a.get("url", "")) and _cle_url(a.get("url", "")) == _cle_url(b.get("url", "")):
        return True
    cles = ("prix", "kilometrage", "annee")
    return all(a.get(k) is not None and a.get(k) == b.get(k) for k in cles)


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


def synchroniser() -> None:
    """Récupère la dernière version des fichiers (l'autre bot a pu les modifier)."""
    racine = FICHIER.parent.parent
    if (racine / ".git").exists():
        subprocess.run(["git", "pull", "--rebase", "--autostash", "origin", "main"],
                       cwd=racine, capture_output=True)


def pousser(message: str, fichiers: list[Path] | None = None) -> None:
    """Pousse docs/annonces.json sur GitHub pour mettre à jour la page de suivi."""
    racine = FICHIER.parent.parent
    if not (racine / ".git").exists():
        return
    cmds = []
    if os.environ.get("GITHUB_ACTIONS"):
        cmds += [
            ["git", "config", "user.name", "gla-bot"],
            ["git", "config", "user.email", "gla-bot@users.noreply.github.com"],
        ]
    cmds += [
        ["git", "add", *[str(f) for f in (fichiers or [FICHIER])]],
        ["git", "commit", "-m", message],
        ["git", "pull", "--rebase", "--autostash", "origin", "main"],
        ["git", "push", "origin", "HEAD:main"],
    ]
    for cmd in cmds:
        subprocess.run(cmd, cwd=racine, check=True, capture_output=True)


async def enregistrer(client: anthropic.AsyncAnthropic, source: str, rapport: str) -> Optional[dict]:
    """Ajoute (ou met à jour) l'annonce dans la base. Renvoie la fiche, ou None si rien à enregistrer."""
    async with verrou:
        await asyncio.to_thread(synchroniser)
        annonces = charger()
        fiche = await _extraire(client, source, rapport, annonces)
        if not fiche.est_une_annonce:
            return None
        data = fiche.model_dump(exclude={"est_une_annonce"})
        data["date"] = datetime.now(timezone.utc).strftime("%Y-%m-%d")

        existante = next((a for a in annonces if meme_voiture(a, data)), None)
        if existante:
            data["id"] = existante["id"]
            annonces[annonces.index(existante)] = data
        else:
            data["id"] = max((a["id"] for a in annonces), default=0) + 1
            annonces.append(data)

        FICHIER.parent.mkdir(exist_ok=True)
        FICHIER.write_text(json.dumps(annonces, ensure_ascii=False, indent=2))
        try:
            await asyncio.to_thread(pousser, f"Annonce #{data['id']} : {data['titre']}")
        except subprocess.CalledProcessError as e:
            log.error("Impossible de pousser la base : %s", e.stderr)
        return data
