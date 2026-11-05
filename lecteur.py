"""Lit une page d'annonce avec un vrai navigateur (Chromium via Playwright).

Pourquoi : l'outil web de Claude refuse les liens trop longs et ne clique pas
sur les boutons « voir plus ». Ici, on ouvre la page comme une personne,
on accepte les cookies, on déplie tous les « voir plus », puis on récupère
le texte complet et une capture d'écran.
"""

import logging
import os
import re
from dataclasses import dataclass
from typing import Optional

from playwright.async_api import async_playwright

log = logging.getLogger("gla_bot")

URL_RE = re.compile(r"https?://\S+")

COOKIES_RE = (
    r"tout accepter|accepter et fermer|accepter|j'accepte|alle akzeptieren|akzeptieren|"
    r"einverstanden|zustimmen|accept all|accept|agree|ok, verstanden"
)

# Clique sur tous les boutons « voir plus » visibles qui ne quittent pas la page.
JS_DEPLIER = r"""
() => {
  const re = /(voir|afficher|lire|montrer|tout afficher|en savoir) (plus|la suite|tout)|tout voir|plus de d[ée]tails|mehr (anzeigen|lesen|details|ausstattung)|alle (anzeigen|ausstattung|merkmale)|weiterlesen|ausklappen|show (more|all)|see (more|all)|read more|view (more|all)|^\s*(mehr|plus|more)\s*$/i;
  let n = 0;
  for (const el of document.querySelectorAll('button, a, summary, [role="button"], span, div, label')) {
    const t = (el.innerText || el.getAttribute('aria-label') || '').trim();
    if (!t || t.length > 40 || !re.test(t)) continue;
    if (el.tagName === 'A') {
      const h = el.getAttribute('href') || '';
      if (h && !h.startsWith('#') && !h.startsWith('javascript')) continue;
    }
    if (el.dataset.glaClique) continue;
    const r = el.getBoundingClientRect();
    if (r.width === 0 || r.height === 0) continue;
    el.dataset.glaClique = '1';
    try { el.click(); n++; } catch (e) {}
  }
  for (const d of document.querySelectorAll('details:not([open])')) { d.open = true; n++; }
  return n;
}
"""

BLOQUE_RE = re.compile(
    r"access denied|zugriff verweigert|captcha|are you a robot|êtes-vous un robot|unusual traffic|"
    r"ungewöhnlich|verify you are human|request blocked",
    re.I,
)


@dataclass
class Page:
    url: str
    texte: str
    capture: Optional[bytes]
    bloquee: bool


def trouver_liens(message: str) -> list[str]:
    return [u.rstrip(").,;!?»\"'") for u in URL_RE.findall(message or "")]


async def _ouvrir(p, url: str):
    """Ouvre la page comme une personne : accepte les cookies et fait défiler. Renvoie (navigateur, page)."""
    # NAVIGATEUR=chrome : utilise le Google Chrome installé (mieux accepté par mobile.de).
    # AFFICHER=1 : montre la fenêtre du navigateur (pratique pour voir ce qu'il fait).
    canal = os.environ.get("NAVIGATEUR") or None
    navigateur = await p.chromium.launch(
        channel=canal,
        executable_path=None if canal else (os.environ.get("CHROMIUM_PATH") or None),
        headless=os.environ.get("AFFICHER", "0") != "1",
        args=["--disable-blink-features=AutomationControlled"],
    )
    try:
        contexte = await navigateur.new_context(
            locale="fr-FR",
            viewport={"width": 1280, "height": 1600},
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"
            ),
        )
        page = await contexte.new_page()
        await page.goto(url, wait_until="domcontentloaded", timeout=45_000)
        await page.wait_for_timeout(3000)

        # Bandeau cookies (parfois dans une iframe).
        for cadre in page.frames:
            try:
                bouton = cadre.get_by_role("button", name=re.compile(COOKIES_RE, re.I)).first
                if await bouton.is_visible(timeout=500):
                    await bouton.click(timeout=2000)
                    await page.wait_for_timeout(1500)
                    break
            except Exception:
                pass

        # Faire défiler pour charger les sections paresseuses.
        for _ in range(6):
            await page.mouse.wheel(0, 2500)
            await page.wait_for_timeout(400)
        return navigateur, page
    except Exception:
        await navigateur.close()
        raise


async def lire(url: str) -> Page:
    async with async_playwright() as p:
        navigateur, page = await _ouvrir(p, url)
        try:
            total = 0
            for _ in range(4):
                n = await page.evaluate(JS_DEPLIER)
                total += n
                if not n:
                    break
                await page.wait_for_timeout(1200)
            log.info("%d « voir plus » dépliés sur %s", total, url[:80])

            await page.evaluate("window.scrollTo(0, 0)")
            texte = await page.inner_text("body")
            capture = await page.screenshot(type="jpeg", quality=70)
            bloquee = len(texte) < 800 or bool(BLOQUE_RE.search(texte[:3000]))
            return Page(url=page.url, texte=texte, capture=capture, bloquee=bloquee)
        finally:
            await navigateur.close()


# Forme des liens vers une annonce, selon le site.
ANNONCE_RE = re.compile(
    r"mobile\.de/.*(details\.html\?.*\bid=\d+|d%C3%A9tails\.html\?.*\bid=\d+|détails\.html\?.*\bid=\d+)"
    r"|autoscout24\.[a-z.]+/(angebote|offres|annunci|ofertas)/"
    r"|leboncoin\.fr/(ad/)?voitures/\d+"
    r"|lacentrale\.fr/auto-occasion-annonce-"
    r"|importemoi\.fr/vehicule/",
    re.I,
)


async def liens_annonces(url_recherche: str) -> tuple[list[str], bool]:
    """Ouvre une page de résultats et renvoie (liens des annonces trouvées, page bloquée ?)."""
    async with async_playwright() as p:
        navigateur, page = await _ouvrir(p, url_recherche)
        try:
            texte = await page.inner_text("body")
            if len(texte) < 800 or BLOQUE_RE.search(texte[:3000]):
                return [], True
            hrefs = await page.evaluate("() => [...document.querySelectorAll('a[href]')].map(a => a.href)")
            vus, liens = set(), []
            for h in hrefs:
                if ANNONCE_RE.search(h):
                    cle = h.split("#")[0]
                    if cle not in vus:
                        vus.add(cle)
                        liens.append(cle)
            log.info("%d annonces trouvées sur %s", len(liens), url_recherche[:80])
            return liens, False
        finally:
            await navigateur.close()
