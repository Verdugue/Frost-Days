"""Constantes et chemins du projet Frost Days.

Tout ce qui dépend de l'environnement (URLs open data, dossiers de cache,
seuils métier) est centralisé ici pour rester facile à ajuster.
"""

from __future__ import annotations

from pathlib import Path

# --------------------------------------------------------------------------- #
# Arborescence du projet
# --------------------------------------------------------------------------- #
PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data"
REFERENCE_DIR = DATA_DIR / "reference"
METEO_CACHE_DIR = DATA_DIR / "meteo"

for _d in (DATA_DIR, REFERENCE_DIR, METEO_CACHE_DIR):
    _d.mkdir(parents=True, exist_ok=True)

# --------------------------------------------------------------------------- #
# Sources de données (data.gouv.fr / Météo-France)
# --------------------------------------------------------------------------- #
# Données climatologiques de base quotidiennes (BASE/QUOT), fichiers RR-T-Vent.
# Un fichier par département. Le fichier "previous" couvre 1950 -> 2024,
# le fichier "latest" couvre l'année courante et la précédente.
METEO_BASE_URL = (
    "https://object.files.data.gouv.fr/meteofrance/data/synchro_ftp/BASE/QUOT/"
)
METEO_PREVIOUS_TEMPLATE = "Q_{dep}_previous-1950-2024_RR-T-Vent.csv.gz"
METEO_LATEST_TEMPLATE = "Q_{dep}_latest-2025-2026_RR-T-Vent.csv.gz"

# Description des champs (métadonnées).
METEO_FIELDS_URL = METEO_BASE_URL + "Q_descriptif_champs_RR-T-Vent.csv"

# Référentiel des communes de France (avec coordonnées du centre).
COMMUNES_URL = (
    "https://static.data.gouv.fr/resources/"
    "communes-et-villes-de-france-en-csv-excel-json-parquet-et-feather/"
    "20260617-160519/communes-france-2026.parquet"
)
COMMUNES_FILE = REFERENCE_DIR / "communes-france-2026.parquet"

# --------------------------------------------------------------------------- #
# Paramètres métier
# --------------------------------------------------------------------------- #
# Un jour de gel : température minimale TN <= 0 °C.
FROST_THRESHOLD_C = 0.0

# Une station avec plus de 35 % de valeurs manquantes sur la période demandée
# est écartée du calcul.
MAX_MISSING_FRACTION = 0.35

# Fenêtre de données mise en cache pour chaque département. Le challenge cible
# 2014-2023, et la vérification 2013-2023 : on couvre largement.
CACHE_START = "2013-01-01"
CACHE_END = "2024-12-31"

# Nombre de stations candidates remontées par défaut autour d'une commune.
DEFAULT_N_CANDIDATES = 8

# --------------------------------------------------------------------------- #
# Colonnes utiles dans les fichiers Météo-France (le reste est ignoré).
# --------------------------------------------------------------------------- #
METEO_USECOLS = ["NUM_POSTE", "NOM_USUEL", "LAT", "LON", "ALTI", "AAAAMMJJ", "TN"]

# Communes connues sans coordonnées dans le référentiel : valeurs de secours.
MISSING_CITIES_LAT_LON = {
    "Marseille": [43.295, 5.372],
    "Paris": [48.866, 2.333],
    "Culey": [48.755, 5.266],
    "Les Hauts-Talican": [49.3436, 2.0193],
    "Lyon": [45.75, 4.85],
    "Bihorel": [49.4542, 1.1162],
    "Saint-Lucien": [48.6480, 1.6229],
    "L'Oie": [46.7982, -1.1302],
    "Sainte-Florence": [46.7965, -1.1520],
}
