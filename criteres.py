"""Critères de la voiture recherchée.

Pour ajouter ou retirer un critère, il suffit de modifier cette liste.
"aussi_appele" aide Claude à reconnaître le critère dans une annonce
écrite en français, en allemand ou en anglais.
"""

MODELE = "Mercedes-Benz GLA"

CRITERES = [
    {"nom": "Couleur blanche", "aussi_appele": "blanc, Weiß, Polarweiß, Digitalweiß, Manufaktur Opalithweiß, white"},
    {"nom": "Label Junge Sterne", "aussi_appele": "label occasion certifiée Mercedes en Allemagne, 'Junge Sterne Garantie'"},
    {"nom": "Pack Nuit", "aussi_appele": "Night-Paket, Night Package, Pack Night"},
    {"nom": "Phares MULTIBEAM LED (phares intelligents)", "aussi_appele": "Projecteurs MULTIBEAM LED, MULTIBEAM LED-Scheinwerfer, Adaptive Highbeam Assist"},
    {"nom": "Pack Premium", "aussi_appele": "Premium-Paket, Premium Package"},
    {"nom": "Pack stationnement avec caméra 360°", "aussi_appele": "Park-Paket mit 360°-Kamera, Pack Aide au stationnement, 360-Grad-Kamera, Rundumsicht"},
    {"nom": "Toit panoramique", "aussi_appele": "Panorama-Schiebedach, toit ouvrant panoramique, Panoramadach"},
    {"nom": "Recharge téléphone par induction", "aussi_appele": "Kabelloses Laden, Wireless Charging, chargeur sans fil, Ladeschale"},
    {"nom": "Apple CarPlay", "aussi_appele": "Smartphone-Integration, Smartphone-Integrationspaket, Android Auto / Apple CarPlay"},
    {"nom": "Volant chauffant", "aussi_appele": "Lenkradheizung, beheiztes Lenkrad"},
    {"nom": "Sièges chauffants", "aussi_appele": "Sitzheizung, sièges avant chauffants"},
    {"nom": "Boule de remorquage (attelage)", "aussi_appele": "Anhängerkupplung, AHK, crochet d'attelage, tow bar"},
    {"nom": "Pneus 4 saisons", "aussi_appele": "Ganzjahresreifen, Allwetterreifen, all-season, pneus toutes saisons"},
    {"nom": "Coffre électrique", "aussi_appele": "hayon électrique, EASY-PACK Heckklappe, elektrische Heckklappe"},
    {"nom": "Sièges électriques", "aussi_appele": "elektrisch einstellbare Sitze, Memory-Paket, sièges à réglage électrique"},
]
