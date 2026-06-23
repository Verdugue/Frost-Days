"""Référentiel des communes : chargement, géocodage et résolution de noms.

On télécharge (et met en cache) le fichier des communes de France, on complète
les coordonnées manquantes, et on fournit des utilitaires pour retrouver une
commune à partir d'un nom + département saisis par l'utilisateur.
"""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass
from functools import lru_cache

import pandas as pd

from . import config
from .download import ensure_file


# --------------------------------------------------------------------------- #
# Normalisation de texte (insensible à la casse / aux accents / tirets)
# --------------------------------------------------------------------------- #
def normalize(text: str) -> str:
    """Minuscule, sans accents, tirets/apostrophes -> espaces, espaces compactés."""
    if text is None:
        return ""
    text = str(text)
    text = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = text.lower()
    for ch in "-'’.,()":
        text = text.replace(ch, " ")
    return " ".join(text.split())


@dataclass
class Commune:
    """Résultat d'une recherche de commune."""

    code_insee: str
    nom: str
    dep_code: str
    dep_nom: str
    lat: float
    lon: float
    population: float
    coord_source: str  # "referentiel" ou "secours" (dictionnaire de complétion)


# --------------------------------------------------------------------------- #
# Chargement du référentiel
# --------------------------------------------------------------------------- #
@lru_cache(maxsize=1)
def load_communes() -> pd.DataFrame:
    """Charge le référentiel des communes (téléchargé puis mis en cache).

    Renvoie un DataFrame avec colonnes normalisées : ``code_insee``, ``nom``,
    ``nom_norm``, ``dep_code``, ``dep_nom``, ``lat``, ``lon``, ``population``,
    ``coord_source``.
    """
    path = ensure_file(config.COMMUNES_URL, config.COMMUNES_FILE, label="référentiel communes")
    df = pd.read_parquet(path)

    out = pd.DataFrame(
        {
            "code_insee": df["code_insee"].astype(str),
            "nom": df["nom_standard"].astype(str),
            "dep_code": df["dep_code"].astype(str),
            "dep_nom": df["dep_nom"].astype(str),
            # Coordonnées du centre, repli sur celles de la mairie si besoin.
            "lat": df["latitude_centre"].fillna(df.get("latitude_mairie")),
            "lon": df["longitude_centre"].fillna(df.get("longitude_mairie")),
            "population": pd.to_numeric(df.get("population"), errors="coerce"),
        }
    )
    out["coord_source"] = "referentiel"

    # Complétion des coordonnées manquantes via le dictionnaire de secours.
    missing_norm = {normalize(k): v for k, v in config.MISSING_CITIES_LAT_LON.items()}
    needs = out["lat"].isna() | out["lon"].isna()
    for idx in out.index[needs]:
        key = normalize(out.at[idx, "nom"])
        if key in missing_norm:
            lat, lon = missing_norm[key]
            out.at[idx, "lat"] = lat
            out.at[idx, "lon"] = lon
            out.at[idx, "coord_source"] = "secours"

    out["nom_norm"] = out["nom"].map(normalize)
    return out


# --------------------------------------------------------------------------- #
# Résolution département / commune
# --------------------------------------------------------------------------- #
def resolve_department(user_input: str) -> str | None:
    """Transforme une saisie (code ou nom) en code département officiel.

    Accepte ``"5"``, ``"05"``, ``"Hautes-Alpes"``, ``"hautes alpes"``, etc.
    """
    if user_input is None:
        return None
    raw = str(user_input).strip()
    communes = load_communes()
    valid_codes = set(communes["dep_code"].unique())

    # Code direct (en gérant le zéro initial pour la métropole).
    candidate = raw.upper()
    if candidate in valid_codes:
        return candidate
    if candidate.isdigit():
        padded = candidate.zfill(2)
        if padded in valid_codes:
            return padded

    # Sinon, correspondance sur le nom du département.
    target = normalize(raw)
    dep_map = (
        communes[["dep_code", "dep_nom"]]
        .drop_duplicates()
        .assign(nom_norm=lambda d: d["dep_nom"].map(normalize))
    )
    exact = dep_map[dep_map["nom_norm"] == target]
    if not exact.empty:
        return exact.iloc[0]["dep_code"]
    contains = dep_map[dep_map["nom_norm"].str.contains(target, regex=False)]
    if not contains.empty:
        return contains.iloc[0]["dep_code"]
    return None


def find_commune(name: str, department: str) -> Commune:
    """Retrouve une commune par nom + département.

    Stratégie : on filtre sur le département, puis on cherche une correspondance
    exacte (nom normalisé), à défaut un préfixe, à défaut une inclusion. En cas
    d'ambiguïté on retient la commune la plus peuplée.
    """
    communes = load_communes()
    dep_code = resolve_department(department)
    if dep_code is None:
        raise ValueError(f"Département introuvable : {department!r}")

    subset = communes[communes["dep_code"] == dep_code]
    target = normalize(name)

    exact = subset[subset["nom_norm"] == target]
    if not exact.empty:
        match = exact
    else:
        prefix = subset[subset["nom_norm"].str.startswith(target)]
        if not prefix.empty:
            match = prefix
        else:
            contains = subset[subset["nom_norm"].str.contains(target, regex=False)]
            if contains.empty:
                raise ValueError(
                    f"Commune introuvable : {name!r} dans le département {dep_code}."
                )
            match = contains

    row = match.sort_values("population", ascending=False, na_position="last").iloc[0]
    if pd.isna(row["lat"]) or pd.isna(row["lon"]):
        raise ValueError(
            f"La commune {row['nom']} ({dep_code}) n'a pas de coordonnées exploitables."
        )

    return Commune(
        code_insee=str(row["code_insee"]),
        nom=str(row["nom"]),
        dep_code=str(row["dep_code"]),
        dep_nom=str(row["dep_nom"]),
        lat=float(row["lat"]),
        lon=float(row["lon"]),
        population=float(row["population"]) if pd.notna(row["population"]) else float("nan"),
        coord_source=str(row["coord_source"]),
    )


def list_communes_in_department(department: str) -> pd.DataFrame:
    """Liste (triée par population) des communes d'un département — utile pour l'UI."""
    dep_code = resolve_department(department)
    if dep_code is None:
        return pd.DataFrame(columns=["nom", "code_insee", "population"])
    subset = load_communes()
    subset = subset[subset["dep_code"] == dep_code]
    return subset.sort_values("population", ascending=False)[
        ["nom", "code_insee", "population", "lat", "lon"]
    ].reset_index(drop=True)
