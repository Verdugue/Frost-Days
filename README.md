# ❄️ Frost Days — Calcul des jours de gel par commune

Programme Python qui calcule le **nombre de jours de gel** pour une commune
française et une plage de dates, à partir des **données climatologiques
quotidiennes de Météo-France** (open data, data.gouv.fr).

> **Définition** — un *jour de gel* est un jour où la température minimale
> `TN` a été **≤ 0 °C**.

Utile pour les agriculteurs, jardiniers, climatologues, ou toute personne
intéressée par l'impact du gel sur les cultures et l'environnement.

---

## ✨ Fonctionnalités

À partir d'une **commune**, d'un **département** et d'une **plage de dates**, le
programme fournit :

- le **nombre total de jours de gel** sur la période ;
- le **nombre moyen de jours de gel par an** ;
- pour **chaque jour calendaire** de l'année, le nombre de gels en valeur
  **absolue** et **relative** (ex. *« le 31 mars a gelé 3 fois sur 10 ans,
  soit 30 % »*) — le 29 février est exclu car non pertinent ;
- des **graphiques** (saisonnalité, probabilité de gel jour par jour, carte des
  stations) via une **interface web Streamlit**.

---

## 🚀 Installation

```bash
git clone <url-du-repo>
cd frost_days
python -m pip install -r requirements.txt
```

Python ≥ 3.10 recommandé.

---

## 🖥️ Utilisation

### En ligne de commande

```bash
python -m frost_days.cli --commune "Briançon" --departement 05 \
    --start 2014-01-01 --end 2023-12-31
```

Options utiles : `--method {haversine,kdtree}`, `--max-missing 0.35`,
`--csv dossier_sortie`, `--top 15`.

Exemple de sortie :

```
Commune    : Briançon (05 – Hautes-Alpes)
Période    : 2014-01-01 → 2023-12-31  (10.00 ans)
Station    : VILLAR ST PANCRACE (#05183001), 2.3 km, 1310 m, 0.0% de valeurs manquantes

Jours de gel (TN <= 0°C) sur la période : 1310
Moyenne par an : 131.0 jours
```

### Interface graphique (Streamlit)

```bash
python -m streamlit run app/streamlit_app.py
```

> Sous Windows, préférez `python -m streamlit …` : la commande `streamlit` seule
> n'est disponible que si le dossier `Scripts` de Python est dans le `PATH`.

Saisir une commune, un département et une plage de dates, puis **Calculer**.

### En Python

```python
from frost_days import compute_frost_report

report = compute_frost_report("Briançon", "05", "2014-01-01", "2023-12-31")
print(report.total_frost_days, report.avg_frost_days_per_year)
report.day_of_year.head()
```

---

## 🧠 Méthode

1. **Géocodage de la commune** — le nom + département sont recherchés dans le
   référentiel des communes ; les coordonnées manquantes sont complétées par un
   dictionnaire de secours.
2. **Stations les plus proches** — distance **Haversine** (orthodromique, par
   défaut) ; une variante **KDTree** (scipy, sphère unité) est disponible pour
   les recherches très rapides.
3. **Filtrage qualité** — toute station avec **> 35 % de valeurs manquantes**
   `TN` sur la période demandée est écartée.
4. **Station retenue** — la **plus proche** parmi celles qui passent le filtre.
5. **Calcul du gel** — `TN ≤ 0 °C`, agrégé par période / année / jour calendaire.

### Volume des données & temps réel

Le jeu de données complet dépasse **100 millions de lignes** (1950 → aujourd'hui,
toute la France). On ne précalcule donc rien globalement : à la **première
requête** concernant un département, son fichier est téléchargé, réduit aux
colonnes utiles et à la fenêtre 2013-2024, puis stocké en **cache Parquet**. Les
requêtes suivantes sur ce département répondent en une fraction de seconde.

---

## 📁 Structure du projet

```
frost_days/
├── frost_days/              # package Python
│   ├── config.py            # URLs open data, chemins, seuils métier
│   ├── download.py          # téléchargement + cache disque
│   ├── geo.py               # Haversine & KDTree (stations proches)
│   ├── communes.py          # référentiel communes, géocodage, complétion coords
│   ├── meteo.py             # accès données Météo-France, cache Parquet par dép.
│   ├── frost.py             # coeur métier : sélection station + statistiques
│   ├── viz.py               # graphiques Plotly réutilisables
│   └── cli.py               # interface ligne de commande
├── app/streamlit_app.py     # interface graphique
├── notebooks/               # statistiques descriptives & contrôles qualité
├── scripts/
│   ├── prefetch.py          # pré-cache de départements
│   └── verify_against_export.py  # comparaison aux exports de référence
├── tests/                   # tests unitaires (pytest)
├── requirements.txt
└── pyproject.toml
```

---

## 📊 Sources de données

| Donnée | Source |
| --- | --- |
| Températures quotidiennes (TN) | [Météo-France — données climatologiques de base quotidiennes](https://www.data.gouv.fr/datasets/donnees-climatologiques-de-base-quotidiennes) (fichiers `BASE/QUOT/Q_<dep>_…_RR-T-Vent.csv.gz`) |
| Référentiel des communes | [Communes de France (CSV/Parquet…)](https://www.data.gouv.fr/datasets/communes-et-villes-de-france-en-csv-excel-json-parquet-et-feather) |

La période d'étude de référence est **2014 → 2023** (10 ans) ; le cache couvre
2013-2024 pour permettre aussi la vérification 2013-2023.

---

## ✅ Tests & vérification

```bash
python -m pytest tests/ -q
```

Pour comparer aux exports de référence fournis par l'enseignant :

```bash
python scripts/verify_against_export.py chemin/vers/export_reference.csv
```

---

## 🛠️ Notes techniques

- Les fichiers Météo-France sont en CSV `;`-séparés, encodage Latin-1, date
  `AAAAMMJJ` ; seules les colonnes `NUM_POSTE, NOM_USUEL, LAT, LON, ALTI,
  AAAAMMJJ, TN` sont conservées.
- Le cache (`data/`) est volontairement **ignoré par git** (régénérable).
- La recherche de station se fait par défaut **dans le département de la
  commune** ; une station de meilleure qualité plus proche dans un département
  voisin n'est pas considérée (amélioration possible).

---

## 📜 Licence des données

Données sous **Licence Ouverte / Open Licence (Etalab)** — Météo-France &
data.gouv.fr.
