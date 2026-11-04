#!/usr/bin/env python3
"""Remplit data/annuaire.json avec les pharmacies de Lomé présentes sur OpenStreetMap."""
import argparse
import json
import sys
import urllib.parse
import urllib.request
from pathlib import Path

from robot import ecrire_json, normaliser

RACINE = Path(__file__).resolve().parent.parent
SORTIE = RACINE / "data" / "annuaire.json"
COMPLEMENTS = RACINE / "data" / "annuaire-complements.json"
OVERPASS = "https://overpass-api.de/api/interpreter"
REQUETE = (
    '[out:json][timeout:60];area["ISO3166-1"="TG"]->.togo;'
    'nwr["amenity"="pharmacy"](6.10,1.08,6.32,1.36)(area.togo);out center tags;'
)
MINIMUM = 10


def telecharger():
    corps = urllib.parse.urlencode({"data": REQUETE}).encode()
    demande = urllib.request.Request(
        OVERPASS, data=corps, headers={"User-Agent": "garde-lome-robot"}
    )
    with urllib.request.urlopen(demande, timeout=120) as reponse:
        return json.load(reponse)


def convertir(element):
    tags = element.get("tags", {})
    nom = (tags.get("name") or "").strip()
    if not nom:
        return None
    centre = element.get("center", element)
    rue = " ".join(p for p in (tags.get("addr:housenumber"), tags.get("addr:street")) if p)
    return {
        "id": f"osm-{element['type']}-{element['id']}",
        "nom": nom if normaliser(nom).startswith("pharmacie") else f"Pharmacie {nom}",
        "quartier": tags.get("addr:suburb") or tags.get("addr:quarter")
        or tags.get("addr:neighbourhood") or "",
        "adresse": rue,
        "telephone": tags.get("phone") or tags.get("contact:phone") or "",
        "lat": centre.get("lat"),
        "lon": centre.get("lon"),
    }


def appliquer_complements(pharmacies, complements):
    """Une ligne de complément corrige une fiche de même nom, ou en ajoute une."""
    par_nom = {normaliser(p["nom"]): p for p in pharmacies}
    for ajout in complements:
        fiche = par_nom.get(normaliser(ajout["nom"]))
        if fiche:
            fiche.update({cle: valeur for cle, valeur in ajout.items() if valeur})
        else:
            pharmacies.append(ajout)
    return pharmacies


def main():
    analyse = argparse.ArgumentParser()
    analyse.add_argument("--depuis", help="fichier JSON Overpass déjà téléchargé")
    options = analyse.parse_args()

    if options.depuis:
        donnees = json.loads(Path(options.depuis).read_text(encoding="utf-8"))
    else:
        donnees = telecharger()

    pharmacies = [p for p in map(convertir, donnees.get("elements", [])) if p]
    if len(pharmacies) < MINIMUM:
        print(f"Import refusé : seulement {len(pharmacies)} pharmacies trouvées.")
        return 1

    complements = json.loads(COMPLEMENTS.read_text(encoding="utf-8"))["pharmacies"]
    pharmacies = appliquer_complements(pharmacies, complements)
    pharmacies.sort(key=lambda p: normaliser(p["nom"]))
    ecrire_json(SORTIE, {
        "source": "OpenStreetMap",
        "licence": "© contributeurs OpenStreetMap, licence ODbL",
        "pharmacies": pharmacies,
    })
    print(f"{len(pharmacies)} pharmacies enregistrées.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
