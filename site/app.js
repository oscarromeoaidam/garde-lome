"use strict";

const FUSEAU = "Africa/Lome";
const el = (id) => document.getElementById(id);
const moisAnnee = new Intl.DateTimeFormat("fr-FR", { month: "long", year: "numeric", timeZone: "UTC" });
const jourSemaine = new Intl.DateTimeFormat("fr-FR", { weekday: "long", day: "numeric", timeZone: "UTC" });
const dateComplete = new Intl.DateTimeFormat("fr-FR", { weekday: "long", day: "numeric", month: "long", year: "numeric", timeZone: "UTC" });
const dateHeure = new Intl.DateTimeFormat("fr-FR", { day: "numeric", month: "long", hour: "2-digit", minute: "2-digit", timeZone: FUSEAU });

let donnees = null;
let position = null;
let quartierChoisi = "";

function aujourdhui() {
  return new Intl.DateTimeFormat("en-CA", { timeZone: FUSEAU }).format(new Date());
}

function enDate(iso) {
  return new Date(`${iso}T00:00:00Z`);
}

function periode(debut, fin) {
  const a = enDate(debut);
  const b = enDate(fin);
  const premier = (texte) => texte.replace(/ 1 /, " 1er ").replace(/ 1$/, " 1er");
  if (debut.slice(0, 7) === fin.slice(0, 7)) {
    return `Du ${premier(jourSemaine.format(a))} au ${premier(jourSemaine.format(b))} ${moisAnnee.format(b)}`;
  }
  return `Du ${premier(dateComplete.format(a))} au ${premier(dateComplete.format(b))}`;
}

function simplifier(texte) {
  return texte.normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();
}

function dessinerCroix() {
  const croix = el("croix");
  const taille = 11;
  for (let ligne = 0; ligne < taille; ligne++) {
    for (let colonne = 0; colonne < taille; colonne++) {
      const point = document.createElement("span");
      if ((ligne >= 4 && ligne <= 6) || (colonne >= 4 && colonne <= 6)) {
        point.className = "led";
        point.style.animationDelay = `${(Math.abs(ligne - 5) + Math.abs(colonne - 5)) * 45}ms`;
      }
      croix.append(point);
    }
  }
}

function distanceKm(a, b) {
  const rad = (x) => (x * Math.PI) / 180;
  const dLat = rad(b.lat - a.lat);
  const dLon = rad(b.lon - a.lon);
  const h = Math.sin(dLat / 2) ** 2
    + Math.cos(rad(a.lat)) * Math.cos(rad(b.lat)) * Math.sin(dLon / 2) ** 2;
  return 2 * 6371 * Math.asin(Math.sqrt(h));
}

function icone(nom) {
  const espace = "http://www.w3.org/2000/svg";
  const svg = document.createElementNS(espace, "svg");
  svg.setAttribute("class", "icone");
  svg.setAttribute("aria-hidden", "true");
  const use = document.createElementNS(espace, "use");
  use.setAttribute("href", `#${nom}`);
  svg.append(use);
  return svg;
}

function bouton(texte, classe, nomIcone, lien, etiquette) {
  const noeud = document.createElement(lien ? "a" : "span");
  noeud.className = `bouton ${classe}`;
  if (nomIcone) noeud.append(icone(nomIcone));
  noeud.append(texte);
  if (lien) noeud.href = lien;
  if (etiquette) noeud.setAttribute("aria-label", etiquette);
  return noeud;
}

function lienItineraire(p) {
  const cible = `${p.nom}, ${p.adresse}, Lomé, Togo`;
  return `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(cible)}`;
}

function actions(p) {
  const zone = document.createElement("div");
  zone.className = "actions";
  const numero = (p.telephone || "").replace(/^\+228\s*/, "");
  if (donnees.demo) {
    const appel = bouton(numero || "Appeler", "principal", "i-tel");
    const route = bouton("Itinéraire", "secondaire", "i-route");
    appel.setAttribute("aria-disabled", "true");
    route.setAttribute("aria-disabled", "true");
    zone.append(appel, route);
    return zone;
  }
  zone.append(
    numero
      ? bouton(numero, "principal", "i-tel", `tel:${p.telephone.replace(/[^+\d]/g, "")}`, `Appeler ${p.nom} au ${numero}`)
      : bouton("Numéro indisponible", "absent"),
    bouton("Itinéraire", "secondaire", "i-route", lienItineraire(p), `Itinéraire vers ${p.nom}`),
  );
  return zone;
}

function carte(p) {
  const li = document.createElement("li");
  li.className = "pharmacie";

  const tete = document.createElement("div");
  tete.className = "pharmacie-tete";
  const titre = document.createElement("h2");
  titre.textContent = p.nom;
  tete.append(titre);
  if (position && p.lat != null) {
    const distance = document.createElement("p");
    distance.className = "distance";
    distance.textContent = `${distanceKm(position, p).toFixed(1).replace(".", ",")} km`;
    tete.append(distance);
  }
  li.append(tete);

  if (p.quartier) {
    const etiquette = document.createElement("p");
    etiquette.className = "etiquette";
    etiquette.textContent = p.quartier;
    li.append(etiquette);
  }

  const lieu = document.createElement("p");
  lieu.className = "lieu";
  lieu.textContent = p.adresse;
  li.append(lieu);

  if (p.a_verifier) {
    const note = document.createElement("p");
    note.className = "a-verifier";
    note.textContent = "Coordonnées à vérifier : cette pharmacie n'est pas encore dans notre annuaire.";
    li.append(note);
  }
  li.append(actions(p));
  return li;
}

function resultats() {
  const mots = simplifier(el("texte").value).split(/\s+/).filter(Boolean);
  const trouvees = donnees.pharmacies.filter((p) => {
    if (quartierChoisi && p.quartier !== quartierChoisi) return false;
    const contenu = simplifier(`${p.nom} ${p.adresse} ${p.quartier}`);
    return mots.every((mot) => contenu.includes(mot));
  });
  if (!position) return trouvees;
  const rang = (p) => (p.lat != null ? distanceKm(position, p) : Infinity);
  return [...trouvees].sort((a, b) => rang(a) - rang(b));
}

function reinitialiser() {
  el("texte").value = "";
  choisirQuartier("");
}

function messageVide() {
  const li = document.createElement("li");
  li.className = "vide";
  const texte = document.createElement("p");
  texte.textContent = "Aucune pharmacie de garde ne correspond à cette recherche.";
  const action = document.createElement("button");
  action.type = "button";
  action.textContent = "Voir toutes les pharmacies";
  action.addEventListener("click", reinitialiser);
  li.append(texte, action);
  return li;
}

function afficherListe() {
  const pharmacies = resultats();
  el("liste").replaceChildren(...(pharmacies.length ? pharmacies.map(carte) : [messageVide()]));
  const n = pharmacies.length;
  let message = n > 1 ? `${n} pharmacies de garde` : n === 1 ? "1 pharmacie de garde" : "";
  if (n && quartierChoisi) message += ` à ${quartierChoisi}. Certaines adresses ne précisent pas le quartier : regardez aussi « Tous ».`;
  if (n && position) {
    const sansPosition = pharmacies.filter((p) => p.lat == null).length;
    message = sansPosition
      ? `Classées par distance. Les ${sansPosition} dernières n'ont pas de position connue, et l'une d'elles peut être plus proche : lisez leur adresse.`
      : "Classées de la plus proche à la plus éloignée.";
  }
  el("aide").textContent = message;
}

function choisirQuartier(quartier) {
  quartierChoisi = quartier;
  for (const puce of el("quartiers").children) {
    puce.setAttribute("aria-pressed", String(puce.dataset.quartier === quartier));
  }
  afficherListe();
}

function puce(libelle, valeur, nombre) {
  const noeud = document.createElement("button");
  noeud.type = "button";
  noeud.className = "puce";
  noeud.dataset.quartier = valeur;
  noeud.setAttribute("aria-pressed", String(valeur === quartierChoisi));
  const compte = document.createElement("small");
  compte.textContent = nombre;
  noeud.append(libelle, compte);
  noeud.addEventListener("click", () => choisirQuartier(valeur));
  return noeud;
}

function remplirQuartiers() {
  const comptes = new Map();
  for (const { quartier } of donnees.pharmacies) {
    if (quartier) comptes.set(quartier, (comptes.get(quartier) || 0) + 1);
  }
  const noms = [...comptes.keys()].sort((a, b) => a.localeCompare(b, "fr"));
  el("quartiers").replaceChildren(
    puce("Tous", "", donnees.pharmacies.length),
    ...noms.map((nom) => puce(nom, nom, comptes.get(nom))),
  );
}

function localiser() {
  const aide = el("aide");
  if (!navigator.geolocation) {
    aide.textContent = "Votre position n'est pas disponible. Cherchez par nom ou par quartier.";
    return;
  }
  aide.textContent = "Recherche de votre position…";
  navigator.geolocation.getCurrentPosition(
    (pos) => {
      position = { lat: pos.coords.latitude, lon: pos.coords.longitude };
      el("proche").setAttribute("aria-pressed", "true");
      el("texte").value = "";
      choisirQuartier("");
    },
    () => { aide.textContent = "Votre position n'est pas disponible. Cherchez par nom ou par quartier."; },
    { timeout: 10000, maximumAge: 300000 },
  );
}

function montrerDoute(message) {
  document.body.dataset.etat = "doute";
  el("statut").textContent = "Liste non confirmée";
  if (message) el("doute-texte").textContent = message;
  el("doute").hidden = false;
}

function afficherCredits() {
  const credits = el("credits");
  if (donnees.source_url) {
    const lien = document.createElement("a");
    lien.href = donnees.source_url;
    lien.textContent = donnees.source;
    credits.append("Source de la liste : ", lien, ". Ce site indépendant n'est pas géré par cette institution.");
  } else if (donnees.source) {
    credits.append(`Source de la liste : ${donnees.source}.`);
  }
  if (donnees.licence_annuaire) credits.append(` Positions ${donnees.licence_annuaire}.`);
}

function afficher() {
  el("demo").hidden = !donnees.demo;
  const jour = aujourdhui();
  if (donnees.mise_a_jour_le) {
    el("maj").textContent = `Mise à jour le ${dateHeure.format(new Date(donnees.mise_a_jour_le))}`;
  }
  afficherCredits();

  if (donnees.statut !== "confirme") {
    montrerDoute();
    return;
  }
  if (jour < donnees.debut || jour > donnees.fin) {
    montrerDoute(`La dernière liste confirmée couvrait la période : ${periode(donnees.debut, donnees.fin).toLowerCase()}. Elle n'est plus affichée.`);
    return;
  }
  document.body.dataset.etat = "confirme";
  el("statut").textContent = periode(donnees.debut, donnees.fin);
  el("recherche").hidden = false;
  remplirQuartiers();
  afficherListe();
}

async function demarrer() {
  dessinerCroix();
  el("texte").addEventListener("input", afficherListe);
  el("proche").addEventListener("click", localiser);
  try {
    const reponse = await fetch("data/garde.json", { cache: "no-cache" });
    if (!reponse.ok) throw new Error(String(reponse.status));
    donnees = await reponse.json();
    afficher();
  } catch {
    montrerDoute("La liste n'a pas pu être chargée. Vérifiez votre connexion, puis rechargez la page.");
  }
}

demarrer();
