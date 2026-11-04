#!/usr/bin/env python3
"""Écrit la liste dans le HTML pour Google, puis crée les pages de quartier et le sitemap."""
import argparse
import datetime as dt
import html
import json
import re
from pathlib import Path

from robot import CONFIG, RACINE, date_francaise, lire_json, normaliser

QUARTIERS_PAGES = [
    "Adétikopé", "Adidogomé", "Agoè", "Avédji", "Baguida", "Bè", "Djidjolé",
    "Hédzranawoé", "Kégué", "Nyékonakpoè", "Sanguéra", "Tokoin",
]


def echapper(texte):
    return html.escape(str(texte), quote=True)


def periode_texte(debut, fin):
    a, b = dt.date.fromisoformat(debut), dt.date.fromisoformat(fin)
    jour = "1er" if a.day == 1 else str(a.day)
    if (a.year, a.month) == (b.year, b.month):
        return f"du {jour} au {date_francaise(b)}"
    if a.year == b.year:
        return f"du {date_francaise(a).rsplit(' ', 1)[0]} au {date_francaise(b)}"
    return f"du {date_francaise(a)} au {date_francaise(b)}"


def slug(nom):
    return normaliser(nom).replace(" ", "-")


def lien_itineraire(p):
    from urllib.parse import quote

    return ("https://www.google.com/maps/search/?api=1&query="
            + quote(f"{p['nom']}, {p['adresse']}, Lomé, Togo"))


def carte(p):
    numero = p.get("telephone", "").removeprefix("+228 ")
    appel = (
        f'<a class="bouton principal" href="tel:{echapper(p["telephone"].replace(" ", ""))}" '
        f'aria-label="Appeler {echapper(p["nom"])} au {echapper(numero)}">'
        f'<svg class="icone" aria-hidden="true"><use href="#i-tel"></use></svg>{echapper(numero)}</a>'
        if numero else '<span class="bouton absent">Numéro indisponible</span>'
    )
    quartier = f'<p class="etiquette">{echapper(p["quartier"])}</p>' if p.get("quartier") else ""
    return (
        f'<li class="pharmacie"><div class="pharmacie-tete"><h2>{echapper(p["nom"])}</h2></div>{quartier}'
        f'<p class="lieu">{echapper(p["adresse"])}</p><div class="actions">{appel}'
        f'<a class="bouton secondaire" href="{echapper(lien_itineraire(p))}" '
        f'aria-label="Itinéraire vers {echapper(p["nom"])}">'
        f'<svg class="icone" aria-hidden="true"><use href="#i-route"></use></svg>Itinéraire</a></div></li>'
    )


def fiche_schema(p):
    fiche = {
        "@type": "Pharmacy",
        "name": p["nom"],
        "address": {
            "@type": "PostalAddress", "streetAddress": p["adresse"],
            "addressLocality": "Lomé", "addressCountry": "TG",
        },
    }
    if p.get("telephone"):
        fiche["telephone"] = p["telephone"].replace(" ", "")
    return fiche


def schema(url, titre, description, pharmacies, faq=None):
    graphe = [{"@type": "WebPage", "url": url, "name": titre, "description": description,
               "inLanguage": "fr"}]
    if pharmacies:
        graphe.append({
            "@type": "ItemList", "name": titre,
            "itemListElement": [
                {"@type": "ListItem", "position": i, "item": fiche_schema(p)}
                for i, p in enumerate(pharmacies, 1)
            ],
        })
    if faq:
        graphe.append({"@type": "FAQPage", "mainEntity": [
            {"@type": "Question", "name": q, "acceptedAnswer": {"@type": "Answer", "text": r}}
            for q, r in faq
        ]})
    corps = json.dumps({"@context": "https://schema.org", "@graph": graphe}, ensure_ascii=False)
    return f'<script type="application/ld+json">{corps.replace("</", "<\\/")}</script>'


def balises_tete(url, titre, description, image, verification):
    lignes = [
        f'<link rel="canonical" href="{echapper(url)}">',
        '<meta property="og:type" content="website">',
        '<meta property="og:locale" content="fr_TG">',
        f'<meta property="og:url" content="{echapper(url)}">',
        f'<meta property="og:title" content="{echapper(titre)}">',
        f'<meta property="og:description" content="{echapper(description)}">',
        f'<meta property="og:image" content="{echapper(image)}">',
        '<meta name="twitter:card" content="summary_large_image">',
    ]
    if verification:
        lignes.append(f'<meta name="google-site-verification" content="{echapper(verification)}">')
    return "\n".join(lignes)


def remplacer(texte, ancien, nouveau):
    if ancien not in texte:
        raise ValueError(f"Élément introuvable dans le modèle : {ancien}")
    return texte.replace(ancien, nouveau, 1)


def extraire_faq(modele):
    bloc = re.search(r'<section class="faq".*?</section>', modele, re.S)[0]
    paires = re.findall(r"<h3>(.*?)</h3>\s*<p>(.*?)</p>", bloc, re.S)
    nettoyer = lambda t: html.unescape(" ".join(re.sub(r"<[^>]+>", "", t).split()))
    return [(nettoyer(q), nettoyer(r)) for q, r in paires]


def generer_accueil(modele, garde, base, verification):
    confirme = garde.get("statut") == "confirme"
    pharmacies = garde["pharmacies"] if confirme else []
    texte = modele
    if confirme:
        periode = periode_texte(garde["debut"], garde["fin"])
        titre = f"Pharmacie de garde Lomé : liste {periode}"
        description = (
            f"Pharmacies de garde à Lomé {periode} : {len(pharmacies)} officines avec téléphone, "
            "adresse et itinéraire, d'après la liste de l'INAM."
        )
        texte = remplacer(texte, '<section id="recherche" hidden>', '<section id="recherche">')
        texte = remplacer(texte, '<ul id="liste" class="liste"></ul>',
                          f'<ul id="liste" class="liste">{"".join(map(carte, pharmacies))}</ul>')
        texte = remplacer(texte, "Chargement de la liste…", echapper(periode.capitalize()))
        texte = remplacer(texte, '<span id="faq-periode"></span>', f" {echapper(periode)}")
    else:
        titre = "Pharmacie de garde Lomé : liste de la semaine"
        description = ("Trouvez les pharmacies de garde à Lomé : téléphone, adresse et itinéraire, "
                       "d'après la liste de l'INAM.")
        texte = remplacer(texte, '<span id="faq-periode"></span>', "")
    texte = remplacer(texte, "<title>Garde Lomé</title>", f"<title>{echapper(titre)}</title>")
    texte = re.sub(r'<meta name="description" content="[^"]*">',
                   lambda _: f'<meta name="description" content="{echapper(description)}">', texte, count=1)
    tete = balises_tete(base, titre, description, f"{base}og.png", verification)
    tete += "\n" + schema(base, titre, description, pharmacies, extraire_faq(texte))
    return remplacer(texte, "</head>", f"{tete}\n</head>")


def page_quartier(quartier, modele, garde, base):
    confirme = garde.get("statut") == "confirme"
    locales = [p for p in garde["pharmacies"] if p.get("quartier") == quartier] if confirme else []
    url = f"{base}quartier/{slug(quartier)}/"
    periode = periode_texte(garde["debut"], garde["fin"]) if confirme else ""
    titre = f"Pharmacie de garde à {quartier}, Lomé"
    titre += f" : {periode}" if confirme else ""
    description = (
        f"Pharmacie de garde à {quartier} (Lomé) : téléphone, adresse et itinéraire, "
        "d'après la liste de l'INAM."
    )
    sprite = re.search(r'<svg width="0".*?</svg>\n', modele, re.S)[0]
    if locales:
        resume = f"{len(locales)} pharmacie{'s' if len(locales) > 1 else ''} de garde {periode}"
        liste = f'<ul id="liste" class="liste">{"".join(map(carte, locales))}</ul>'
    elif confirme:
        resume = periode.capitalize()
        liste = (f'<p id="liste" class="alerte-simple">Aucune pharmacie de garde n\'est indiquée à '
                 f'{echapper(quartier)} pour cette période. Consultez la liste complète de Lomé.</p>')
    else:
        resume = "Liste non confirmée"
        liste = ('<p id="liste" class="alerte-simple">La liste de cette période n\'est pas confirmée. '
                 'Consultez la page d\'accueil.</p>')
    autres = "".join(
        f'<li><a href="../{slug(q)}/">{echapper(q)}</a></li>' for q in QUARTIERS_PAGES if q != quartier
    )
    garde_fin = json.dumps(garde.get("fin") or "")
    return f"""<!doctype html>
<html lang="fr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>{echapper(titre)}</title>
<meta name="description" content="{echapper(description)}">
<meta name="theme-color" content="#07402f">
<link rel="stylesheet" href="../../style.css">
{balises_tete(url, titre, description, f"{base}og.png", "")}
{schema(url, titre, description, locales)}
</head>
<body data-etat="{'confirme' if confirme else 'doute'}">
{sprite}<header class="hero"><div class="hero-interieur"><div class="hero-texte">
<p class="marque"><a href="../../">Garde Lomé</a></p>
<h1>Pharmacie de garde à {echapper(quartier)}</h1>
<p id="statut">{echapper(resume)}</p>
</div></div></header>
<main class="page-quartier">
<p id="expire" class="alerte" hidden>Cette liste est dépassée. Consultez la page d'accueil.</p>
{liste}
<p class="conseil">Appelez avant de vous déplacer : une garde peut changer au dernier moment.</p>
<p class="retour"><a class="bouton principal" href="../../">Voir toutes les pharmacies de garde de Lomé</a></p>
<nav class="autres" aria-label="Autres quartiers"><h2>Autres quartiers</h2><ul>{autres}</ul></nav>
</main>
<footer><p>Source de la liste : <a href="{echapper(garde.get('source_url', ''))}">{echapper(garde.get('source', ''))}</a>. Ce site indépendant n'est pas géré par cette institution.</p></footer>
<script>
if ({garde_fin} && new Intl.DateTimeFormat("en-CA", {{ timeZone: "Africa/Lome" }}).format(new Date()) > {garde_fin}) {{
  document.getElementById("liste").hidden = true;
  document.getElementById("expire").hidden = false;
  document.getElementById("statut").textContent = "Liste non confirmée";
  document.body.dataset.etat = "doute";
}}
</script>
</body>
</html>
"""


def sitemap(urls, date):
    lignes = "".join(f"<url><loc>{echapper(u)}</loc><lastmod>{date}</lastmod></url>" for u in urls)
    return ('<?xml version="1.0" encoding="UTF-8"?>\n'
            f'<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{lignes}</urlset>\n')


def main():
    analyse = argparse.ArgumentParser()
    analyse.add_argument("--dossier", default=str(RACINE / "site"))
    dossier = Path(analyse.parse_args().dossier)

    config = lire_json(CONFIG)
    base = config["site_url"].rstrip("/") + "/"
    garde = lire_json(dossier / "data" / "garde.json")
    modele = (dossier / "index.html").read_text(encoding="utf-8")

    (dossier / "index.html").write_text(
        generer_accueil(modele, garde, base, config.get("google_site_verification", "")), encoding="utf-8"
    )
    urls = [base]
    for quartier in QUARTIERS_PAGES:
        cible = dossier / "quartier" / slug(quartier) / "index.html"
        cible.parent.mkdir(parents=True, exist_ok=True)
        cible.write_text(page_quartier(quartier, modele, garde, base), encoding="utf-8")
        urls.append(f"{base}quartier/{slug(quartier)}/")
    date = (garde.get("mise_a_jour_le") or garde.get("verifie_le", ""))[:10]
    (dossier / "sitemap.xml").write_text(sitemap(urls, date), encoding="utf-8")
    (dossier / "robots.txt").write_text(f"User-agent: *\nAllow: /\nSitemap: {base}sitemap.xml\n", encoding="utf-8")
    print(f"{len(urls)} pages préparées pour Google.")


if __name__ == "__main__":
    main()
