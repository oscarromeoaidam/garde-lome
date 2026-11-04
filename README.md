# Garde Lomé

Site qui affiche les pharmacies de garde à Lomé et se met à jour tout seul.

Vous n'avez rien à installer. GitHub lance le robot chaque jour et héberge le site gratuitement.

## Comment ça marche

1. Chaque jour à 6 h 17, le robot lit la source indiquée dans `robot/config.json`.
2. Il trouve la période de garde et les pharmacies. Si la lecture simple échoue et qu'une clé IA existe, il utilise l'IA.
3. Il relie chaque nom à une fiche de `data/annuaire.json`.
4. Il contrôle la date, le nombre de pharmacies et les noms inconnus.
5. Si tout est bon, il publie `site/data/garde.json`.

En cas de problème :

- La liste précédente reste affichée tant que ses dates sont valables.
- Une fois ses dates dépassées, le site affiche « Liste non confirmée » et ne montre aucune pharmacie.
- Le lancement GitHub apparaît en échec, et GitHub vous envoie normalement un e-mail.

## Mettre le site en ligne (15 minutes)

1. Créez un compte sur github.com, puis un dépôt **public** nommé `garde-lome`, avec la branche `main`.
2. Dézippez le projet, puis glissez **tout** son contenu dans le dépôt (Add file > Upload files). Vérifiez que le dossier `.github` apparaît bien.
3. Allez dans Settings > Pages. Sous « Source », choisissez **GitHub Actions**.
4. Allez dans l'onglet Actions, ouvrez **Mise à jour des gardes**, puis cliquez sur **Run workflow**.
5. Quand le lancement est vert, votre site est à l'adresse `https://VOTRE-NOM.github.io/garde-lome/`.

Le site tourne alors en démonstration, avec des pharmacies fictives et un bandeau d'avertissement.

## Passer aux vraies données

**1. Remplir l'annuaire.** Dans Actions, lancez **Importer l'annuaire**. Le robot récupère les pharmacies de Lomé sur OpenStreetMap. Pour ajouter ou corriger une fiche, modifiez `data/annuaire-complements.json` :

```json
{
  "pharmacies": [
    {"id": "ajout-1", "nom": "Pharmacie Exemple", "quartier": "Tokoin", "adresse": "Rue...", "telephone": "+228 ...", "lat": null, "lon": null}
  ]
}
```

Relancez ensuite **Importer l'annuaire**.

**2. Choisir la source de la liste.** Dans `robot/config.json` :

- Si la liste est en ligne, mettez son adresse dans `url` et son nom dans `nom`.
- Si elle circule en PDF ou en photo, déposez le fichier dans `sources/` et mettez son chemin dans `fichier`. Le robot fait le reste, mais il faut déposer chaque nouvelle liste.

Vérifiez que vous avez le droit de réutiliser cette liste.

**3. Quitter la démonstration.** Toujours dans `robot/config.json`, mettez `"demo": false`.

Faites valider le résultat avec la vraie liste pendant quelques semaines avant d'annoncer le site au public.

## Activer l'IA (facultatif et payant)

La lecture simple suffit quand la liste est en texte et contient une phrase du type « du 7 au 14 novembre 2026 ». L'IA sert pour une photo, un scan ou une mise en page difficile.

1. Créez une clé API sur console.anthropic.com.
2. Ajoutez-la dans Settings > Secrets and variables > Actions, sous le nom `ANTHROPIC_API_KEY`.

Le texte de l'IA passe par les mêmes contrôles et le même rapprochement avec l'annuaire. Vérifiez que le modèle de `robot/config.json` est toujours disponible.

## Structure du projet

| Élément | Rôle |
|---|---|
| `site/` | Le site public |
| `site/data/garde.json` | La liste publiée par le robot |
| `robot/robot.py` | Le robot quotidien |
| `robot/importer_annuaire.py` | L'import depuis OpenStreetMap |
| `robot/config.json` | La source et les règles de contrôle |
| `data/annuaire.json` | L'annuaire réel, rempli par l'import |
| `data/annuaire-demo.json` | L'annuaire fictif de la démonstration |
| `.github/workflows/` | L'automatisation GitHub |

## Tests

```
cd robot
python -m unittest test_robot
```

Les adresses de l'annuaire proviennent d'OpenStreetMap et doivent rester créditées. Le site le fait automatiquement en bas de page.
