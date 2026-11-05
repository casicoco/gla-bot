# Prompt pour Claude avec accès à Chrome

Copier tout le texte sous la ligne dans Claude (avec l'extension Chrome), en remplaçant
la liste des liens.

---

Je cherche une Mercedes GLA d'occasion pour ma mère. Ouvre une par une, dans mon Chrome,
les annonces ci-dessous et vérifie les critères.

Annonces à vérifier :
- <colle ici le lien 1>
- <colle ici le lien 2>

Pour chaque annonce :
1. Ouvre la page. Accepte le bandeau de cookies si besoin.
2. Clique sur tous les « voir plus », « afficher plus », « mehr anzeigen », « alle anzeigen »,
   « Weiterlesen » pour déplier la liste complète des équipements et la description.
3. Lis toute la page : caractéristiques (couleur, année, kilométrage, prix), liste
   d'équipements (« Ausstattung ») et description du vendeur (« Fahrzeugbeschreibung »).
4. Passe à l'annonce suivante tranquillement, sans enchaîner trop vite.

Si une page affiche « Zugriff verweigert », « Access denied », un captcha ou une
vérification anti-robot : arrête-toi, ne cherche pas à contourner, et dis-le-moi.

Critères (le nom allemand entre parenthèses aide à les repérer) :
1. Couleur blanche (Weiß, Polarweiß, Digitalweiß, Opalithweiß)
2. Label Junge Sterne (occasion certifiée Mercedes)
3. Pack Nuit (Night-Paket)
4. Phares MULTIBEAM LED (MULTIBEAM LED-Scheinwerfer)
5. Pack Premium (Premium-Paket ; « AMG Line Advanced Plus » est proche, à signaler)
6. Pack stationnement avec caméra 360° (Park-Paket mit 360°-Kamera)
7. Toit panoramique (Panorama-Schiebedach)
8. Recharge du téléphone par induction (Kabelloses Laden, Induktionsladeschale)
9. Apple CarPlay (Smartphone-Integration)
10. Volant chauffant (Lenkradheizung)
11. Sièges chauffants (Sitzheizung)
12. Boule de remorquage (Anhängerkupplung, AHK)
13. Pneus 4 saisons (Ganzjahresreifen, Allwetterreifen)
14. Coffre électrique (EASY-PACK Heckklappe, elektrische Heckklappe)
15. Sièges électriques (elektrisch einstellbare Sitze, Memory-Paket)

Réponds pour chaque annonce, en français simple :

### <modèle, année, kilométrage, prix>
✅ / ❌ / ❓ <critère> : <précision courte>  (une ligne par critère, ❓ dès qu'il y a un doute)
Bilan : X critères sur 15 confirmés
À demander au vendeur : <les doutes, sous forme de questions>

Puis, juste en dessous, un bloc de texte brut à copier, qui commence par « Annonce : »
et contient : le lien, le titre, le prix, l'année, le kilométrage, la couleur, le vendeur
et sa ville, puis la liste COMPLÈTE des équipements recopiée telle qu'elle est sur la page
(sans traduire ni résumer), et la description du vendeur. Ce bloc sert à mon bot, qui
fait sa propre vérification : il doit contenir tout ce qui est écrit sur la page.
