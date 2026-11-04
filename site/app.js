"use strict";

const FUSEAU = "Africa/Lome";
const el = (id) => document.getElementById(id);
const dateJour = new Intl.DateTimeFormat("fr-FR", { dateStyle: "long", timeZone: "UTC" });
const dateHeure = new Intl.DateTimeFormat("fr-FR", { dateStyle: "long", timeStyle: "short", timeZone: FUSEAU });

let donnees = null;
let position = null;

function aujourdhui() {
  return new Intl.DateTimeFormat("en-CA", { timeZone: FUSEAU }).format(new Date());
}

function dessinerCroix() {
  const croix = el("croix");
  for (let ligne = 0; ligne < 9; ligne++) {
    for (let colonne = 0; colonne < 9; colonne++) {
      const point = document.createElement("span");
      if ((ligne >= 3 && ligne <= 5) || (colonne >= 3 && colonne <= 5)) point.className = "led";
      croix.append(point);
    }
  }
}

function formaterJour(iso) {
  return dateJour.format(new Date(`${iso}T00:00:00Z`)).replace(/^1 /, "1er ");
}

function distanceKm(a, b) {
  const rad = (x) => (x * Math.PI) / 180;
  const dLat = rad(b.lat - a.lat);
  const dLon = rad(b.lon - a.lon);
  const h = Math.sin(dLat / 2) ** 2
    + Math.cos(rad(a.lat)) * Math.cos(rad(b.lat)) * Math.sin(dLon / 2) ** 2;
  return 2 * 6371 * Math.asin(Math.sqrt(h));
}

function bouton(texte, classe, lien) {
  const noeud = document.createElement(lien ? "a" : "span");
  noeud.className = `bouton ${classe}`;
  noeud.textContent = texte;
  if (lien) noeud.href = lien;
  else noeud.setAttribute("aria-disabled", "true");
  return noeud;
}

function lienItineraire(p) {
  const cible = p.lat != null ? `${p.lat},${p.lon}` : `${p.nom} ${p.adresse} Lomé Togo`;
  return `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(cible)}`;
}

function carte(p) {
  const li = document.createElement("li");
  li.className = "pharmacie";

  const titre = document.createElement("h2");
  titre.textContent = p.nom;
  li.append(titre);

  const distance = document.createElement("p");
  distance.className = "distance";
  if (position && p.lat != null) {
    const km = distanceKm(position, p);
    distance.textContent = `${km.toFixed(1).replace(".", ",")} km`;
  }
  li.append(distance);

  const lieu = document.createElement("p");
  lieu.className = "lieu";
  lieu.textContent = [p.quartier, p.adresse].filter(Boolean).join(", ");
  lieu.style.gridColumn = "1 / -1";
  li.append(lieu);

  if (p.telephone) {
    const tel = document.createElement("p");
    tel.className = "telephone";
    tel.textContent = p.telephone;
    tel.style.gridColumn = "1 / -1";
    li.append(tel);
  }
  if (p.a_verifier) {
    const note = document.createElement("p");
    note.className = "a-verifier";
    note.textContent = "Coordonnées à vérifier : cette pharmacie n'est pas encore dans notre annuaire.";
    note.style.gridColumn = "1 / -1";
    li.append(note);
  }

  const actions = document.createElement("div");
  actions.className = "actions";
  if (donnees.demo) {
    actions.append(bouton("Appeler", "principal"), bouton("Itinéraire", "secondaire"));
  } else {
    if (p.telephone) {
      actions.append(bouton("Appeler", "principal", `tel:${p.telephone.replace(/[^+\d]/g, "")}`));
    }
    actions.append(bouton("Itinéraire", "secondaire", lienItineraire(p)));
  }
  li.append(actions);
  return li;
}

function afficherListe() {
  const choix = el("quartier").value;
  let pharmacies = donnees.pharmacies.filter((p) => !choix || p.quartier === choix);
  if (position) {
    const rang = (p) => (p.lat != null ? distanceKm(position, p) : Infinity);
    pharmacies = [...pharmacies].sort((a, b) => rang(a) - rang(b));
  }
  el("liste").replaceChildren(...pharmacies.map(carte));
  const n = pharmacies.length;
  el("aide").textContent = n > 1 ? `${n} pharmacies de garde` : n === 1 ? "1 pharmacie de garde"
    : "Aucune pharmacie de garde dans ce quartier. Choisissez « Tous les quartiers ».";
}

function remplirQuartiers() {
  const quartiers = [...new Set(donnees.pharmacies.map((p) => p.quartier).filter(Boolean))]
    .sort((a, b) => a.localeCompare(b, "fr"));
  const options = ["", ...quartiers].map((q) => new Option(q || "Tous les quartiers", q));
  el("quartier").replaceChildren(...options);
}

function localiser() {
  const aide = el("aide");
  if (!navigator.geolocation) {
    aide.textContent = "Votre position n'est pas disponible. Choisissez un quartier.";
    return;
  }
  aide.textContent = "Recherche de votre position…";
  navigator.geolocation.getCurrentPosition(
    (pos) => {
      position = { lat: pos.coords.latitude, lon: pos.coords.longitude };
      el("quartier").value = "";
      afficherListe();
      el("aide").textContent = "Pharmacies de garde classées de la plus proche à la plus éloignée.";
    },
    () => { aide.textContent = "Votre position n'est pas disponible. Choisissez un quartier."; },
    { timeout: 10000, maximumAge: 300000 },
  );
}

function montrerDoute(message) {
  document.body.dataset.etat = "doute";
  el("statut").textContent = "Liste non confirmée";
  if (message) el("doute-texte").textContent = message;
  el("doute").hidden = false;
}

function afficher() {
  el("demo").hidden = !donnees.demo;
  const jour = aujourdhui();
  if (donnees.mise_a_jour_le) {
    el("maj").textContent = `Mise à jour le ${dateHeure.format(new Date(donnees.mise_a_jour_le))}`;
  }
  const credits = [donnees.source && `Source de la liste : ${donnees.source}.`];
  if (donnees.licence_annuaire) credits.push(`Adresses ${donnees.licence_annuaire}.`);
  el("credits").textContent = credits.filter(Boolean).join(" ");

  if (donnees.statut !== "confirme") {
    montrerDoute();
    return;
  }
  if (jour < donnees.debut || jour > donnees.fin) {
    montrerDoute(`La dernière liste confirmée couvrait la période du ${formaterJour(donnees.debut)} au ${formaterJour(donnees.fin)}. Elle n'est plus affichée.`);
    return;
  }
  document.body.dataset.etat = "confirme";
  el("statut").textContent = `Valable du ${formaterJour(donnees.debut)} au ${formaterJour(donnees.fin)}`;
  el("recherche").hidden = false;
  remplirQuartiers();
  afficherListe();
}

async function demarrer() {
  dessinerCroix();
  el("quartier").addEventListener("change", afficherListe);
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
