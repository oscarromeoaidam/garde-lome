import datetime as dt
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import importer_annuaire
import robot

AUJ = dt.date(2026, 11, 10)
ANNUAIRE = [
    {"id": str(i), "nom": f"Pharmacie {n}", "quartier": q, "adresse": "", "telephone": "1"}
    for i, (n, q) in enumerate([
        ("de la Paix", "Bè"), ("Saint Joseph", "Tokoin"), ("Espérance", "Agoè"),
        ("du Marché", "Kégué"), ("Lumière", "Bè"),
    ])
]
ANNUAIRE_COMPLET = {"licence": "", "pharmacies": ANNUAIRE}
REGLES = {"min_pharmacies": 3, "max_pharmacies": 60, "duree_max_jours": 14,
          "max_inconnues_pct": 10, "variation_max_pct": 50}
BONNE_LISTE = """Pharmacies de garde du 7 au 14 novembre 2026
Bè : Pharmacie de la Paix
Tokoin : PHARMACIE SAINT-JOSEPH
Agoè : Pharmacie Esperance
"""


def config_avec(texte):
    dossier = tempfile.mkdtemp()
    chemin = Path(dossier) / "liste.txt"
    chemin.write_text(texte, encoding="utf-8")
    return {"demo": False, "source": {"nom": "Test", "fichier": str(chemin)},
            "controles": REGLES, "ia": {"modele": "test"}}


def publier(config, precedente=None, jour=AUJ):
    with mock.patch.dict("os.environ", {}, clear=True):
        return robot.publier(config, ANNUAIRE_COMPLET, precedente, jour, "2026-11-10T06:00:00+00:00")


class Dates(unittest.TestCase):
    def periode(self, texte):
        return robot.trouver_periodes(texte, AUJ)[0][1:]

    def test_meme_mois(self):
        self.assertEqual(self.periode("du 7 au 14 novembre 2026"),
                         (dt.date(2026, 11, 7), dt.date(2026, 11, 14)))

    def test_deux_mois_et_jours(self):
        self.assertEqual(self.periode("du samedi 28 février au samedi 7 mars 2026"),
                         (dt.date(2026, 2, 28), dt.date(2026, 3, 7)))

    def test_changement_annee(self):
        self.assertEqual(self.periode("du 30 décembre 2026 au 6 janvier 2027"),
                         (dt.date(2026, 12, 30), dt.date(2027, 1, 6)))
        self.assertEqual(self.periode("du 30 décembre au 6 janvier 2027"),
                         (dt.date(2026, 12, 30), dt.date(2027, 1, 6)))

    def test_chiffres(self):
        self.assertEqual(self.periode("Du 07/11/2026 au 14/11/2026"),
                         (dt.date(2026, 11, 7), dt.date(2026, 11, 14)))

    def test_date_impossible_ignoree(self):
        self.assertEqual(robot.trouver_periodes("du 31 au 32 novembre 2026", AUJ), [])


class Rapprochement(unittest.TestCase):
    def test_variantes(self):
        trouvees, inconnues = robot.rapprocher(
            [{"nom": "Pharmacie La Paix"}, {"nom": "PHARMACIE ST JOSEPH"}, {"nom": "Pharmacie Lumiere"}],
            ANNUAIRE)
        self.assertEqual([f["id"] for f in trouvees], ["0", "4"])
        self.assertEqual(inconnues, [{"nom": "PHARMACIE ST JOSEPH"}])

    def test_nom_voisin_refuse(self):
        fiches = [{"nom": "Pharmacie Sainte Marie", "quartier": ""},
                  {"nom": "Pharmacie Sainte Maria", "quartier": ""}]
        self.assertEqual(robot.rapprocher([{"nom": "Pharmacie Sainte Mari"}], fiches)[0], [])

    def test_homonymes_departages_par_quartier(self):
        fiches = [{"id": "a", "nom": "Pharmacie Paix", "quartier": "Bè"},
                  {"id": "b", "nom": "Pharmacie Paix", "quartier": "Agoè"}]
        self.assertEqual(robot.rapprocher([{"nom": "Pharmacie Paix", "quartier": "agoe"}], fiches)[0], [fiches[1]])
        self.assertEqual(robot.rapprocher([{"nom": "Pharmacie Paix"}], fiches)[0], [])


class Publication(unittest.TestCase):
    def test_liste_correcte(self):
        resultat, alertes = publier(config_avec(BONNE_LISTE))
        self.assertEqual(resultat["statut"], "confirme")
        self.assertEqual(len(resultat["pharmacies"]), 3)
        self.assertEqual(alertes, [])

    def test_plusieurs_periodes(self):
        texte = ("Du 31 octobre au 7 novembre 2026\nPharmacie du Marché\nPharmacie Lumière\n"
                 "Du 7 au 14 novembre 2026\n" + BONNE_LISTE.split("\n", 1)[1] +
                 "Du 14 au 21 novembre 2026\nPharmacie du Marché\n")
        resultat, _ = publier(config_avec(texte))
        noms = {p["nom"] for p in resultat["pharmacies"]}
        self.assertEqual(len(noms), 3)
        self.assertNotIn("Pharmacie du Marché", noms)

    def test_liste_perimee(self):
        resultat, alertes = publier(config_avec(BONNE_LISTE.replace("7 au 14 novembre", "1 au 6 novembre")))
        self.assertEqual(resultat["statut"], "non_confirme")
        self.assertEqual(resultat["pharmacies"], [])
        self.assertTrue(alertes)

    def test_trop_peu(self):
        resultat, _ = publier(config_avec("du 7 au 14 novembre 2026\nPharmacie de la Paix\n"))
        self.assertEqual(resultat["statut"], "non_confirme")

    def test_trop_inconnues(self):
        resultat, _ = publier(config_avec(BONNE_LISTE + "Pharmacie Introuvable\nPharmacie Fantome\n"))
        self.assertEqual(resultat["statut"], "non_confirme")

    def test_inconnue_tolere_et_signalee(self):
        grand = [dict(f, nom=f"Pharmacie N{i}xq{i}") for i, f in enumerate(ANNUAIRE * 2)]
        lignes = "".join(f"{f['nom']}\n" for f in grand) + "Pharmacie Introuvable\n"
        config = config_avec("du 7 au 14 novembre 2026\n" + lignes)
        with mock.patch.dict("os.environ", {}, clear=True):
            resultat, alertes = robot.publier(config, {"licence": "", "pharmacies": grand}, None, AUJ, "x")
        self.assertEqual(resultat["statut"], "confirme")
        self.assertTrue(any(p.get("a_verifier") for p in resultat["pharmacies"]))
        self.assertEqual(len(alertes), 1)

    def test_source_vide_garde_liste_encore_valable(self):
        precedente, _ = publier(config_avec(BONNE_LISTE))
        resultat, alertes = publier(config_avec("page en travaux"), precedente)
        self.assertEqual(resultat["statut"], "confirme")
        self.assertEqual(resultat["pharmacies"], precedente["pharmacies"])
        self.assertTrue(alertes)

    def test_source_vide_liste_expiree(self):
        precedente, _ = publier(config_avec(BONNE_LISTE))
        resultat, _ = publier(config_avec("page en travaux"), precedente, dt.date(2026, 11, 15))
        self.assertEqual(resultat["statut"], "non_confirme")

    def test_fichier_manquant(self):
        config = config_avec(BONNE_LISTE)
        config["source"]["fichier"] = "/inexistant.txt"
        resultat, alertes = publier(config)
        self.assertEqual(resultat["statut"], "non_confirme")
        self.assertTrue(alertes)

    def test_variation_brutale(self):
        precedente = {"statut": "confirme", "debut": "2026-01-01", "fin": "2026-01-07",
                      "pharmacies": [{}] * 20}
        resultat, _ = publier(config_avec(BONNE_LISTE), precedente)
        self.assertEqual(resultat["statut"], "non_confirme")

    def test_date_inchangee_si_liste_identique(self):
        premiere, _ = publier(config_avec(BONNE_LISTE))
        premiere["mise_a_jour_le"] = "AVANT"
        seconde, _ = publier(config_avec(BONNE_LISTE), premiere)
        self.assertEqual(seconde["mise_a_jour_le"], "AVANT")


class Lecture(unittest.TestCase):
    def test_html_ignore_les_scripts(self):
        texte = robot.html_vers_texte(
            "<script>var a='Pharmacie Piege';</script><h1>Du 7 au 14 novembre 2026</h1>"
            "<ul><li>Pharmacie de la Paix</li><li>Pharmacie Lumière</li></ul>")
        self.assertNotIn("Piege", texte)
        self.assertEqual(len(robot.extraire_sans_ia(texte, AUJ).candidats), 2)


class Ia(unittest.TestCase):
    def test_reponse_valide(self):
        reponse = json.dumps({"debut": "2026-11-07", "fin": "2026-11-14",
                              "pharmacies": [{"nom": "Pharmacie de la Paix", "quartier": "Bè"}]})
        liste = robot.lire_reponse_ia(f"```json\n{reponse}\n```")
        self.assertEqual(liste.debut, dt.date(2026, 11, 7))
        self.assertEqual(len(liste.candidats), 1)

    def test_nom_invente_reste_inconnu(self):
        reponse = json.dumps({"debut": "2026-11-07", "fin": "2026-11-14", "pharmacies": [
            {"nom": "Pharmacie Inventee"}, {"nom": "Pharmacie Autre"}, {"nom": "Pharmacie Tierce"}]})
        config = config_avec("photo illisible")
        with mock.patch.dict("os.environ", {"ANTHROPIC_API_KEY": "k"}), \
                mock.patch.object(robot, "appeler_ia", return_value=reponse):
            resultat, _ = robot.publier(config, ANNUAIRE_COMPLET, None, AUJ, "x")
        self.assertEqual(resultat["statut"], "non_confirme")

    def test_ia_prend_le_relais(self):
        reponse = json.dumps({"debut": "2026-11-07", "fin": "2026-11-14", "pharmacies": [
            {"nom": "Pharmacie de la Paix"}, {"nom": "Pharmacie Lumière"}, {"nom": "Pharmacie Espérance"}]})
        config = config_avec("texte sans date lisible")
        with mock.patch.dict("os.environ", {"ANTHROPIC_API_KEY": "k"}), \
                mock.patch.object(robot, "appeler_ia", return_value=reponse) as appel:
            resultat, _ = robot.publier(config, ANNUAIRE_COMPLET, None, AUJ, "x")
        self.assertEqual(resultat["statut"], "confirme")
        self.assertIn("<document>", appel.call_args[0][0][0]["text"])

    def test_reponse_ia_invalide(self):
        config = config_avec("rien")
        with mock.patch.dict("os.environ", {"ANTHROPIC_API_KEY": "k"}), \
                mock.patch.object(robot, "appeler_ia", return_value="désolé"):
            resultat, alertes = robot.publier(config, ANNUAIRE_COMPLET, None, AUJ, "x")
        self.assertEqual(resultat["statut"], "non_confirme")
        self.assertTrue(alertes)


class Annuaire(unittest.TestCase):
    def test_conversion_osm(self):
        fiche = importer_annuaire.convertir({
            "type": "way", "id": 5, "center": {"lat": 6.1, "lon": 1.2},
            "tags": {"name": "La Paix", "addr:suburb": "Bè", "phone": "+228 1"}})
        self.assertEqual(fiche["nom"], "Pharmacie La Paix")
        self.assertEqual(fiche["lat"], 6.1)
        self.assertEqual(fiche["quartier"], "Bè")

    def test_sans_nom(self):
        self.assertIsNone(importer_annuaire.convertir({"type": "node", "id": 1, "tags": {}}))

    def test_complements(self):
        base = [{"nom": "Pharmacie Paix", "telephone": ""}]
        resultat = importer_annuaire.appliquer_complements(
            base, [{"nom": "PHARMACIE PAIX", "telephone": "9"}, {"nom": "Pharmacie Neuve"}])
        self.assertEqual(resultat[0]["telephone"], "9")
        self.assertEqual(len(resultat), 2)


if __name__ == "__main__":
    unittest.main()
