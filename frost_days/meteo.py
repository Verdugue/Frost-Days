"""Accès aux données météo Météo-France (BASE/QUOT), par département.

Le volume brut est énorme (1950 → aujourd'hui, > 100 M de lignes au total). On
ne précalcule donc rien globalement : à la première demande concernant un
département, on télécharge son fichier, on ne garde que les colonnes utiles et
la fenêtre 2013→2024, puis on écrit un cache Parquet compact. Les requêtes
suivantes lisent ce cache en une fraction de seconde.

Colonnes du cache : ``num_poste, nom_usuel, lat, lon, alti, date, tn``.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from . import config
from .download import ensure_file

_CACHE_START_INT = int(config.CACHE_START.replace("-", ""))
_READ_DTYPE = {"NUM_POSTE": "string", "NOM_USUEL": "string", "AAAAMMJJ": "string"}


def _dep_urls(dep: str) -> list[tuple[str, Path]]:
    """(url, fichier_local) pour les fichiers 'previous' puis 'latest' d'un département."""
    out = []
    for tmpl in (config.METEO_PREVIOUS_TEMPLATE, config.METEO_LATEST_TEMPLATE):
        fname = tmpl.format(dep=dep)
        out.append((config.METEO_BASE_URL + fname, config.METEO_CACHE_DIR / fname))
    return out


def _parse_source(path: Path) -> pd.DataFrame:
    """Lit un .csv.gz Météo-France par morceaux et garde la fenêtre utile."""
    pieces: list[pd.DataFrame] = []
    reader = pd.read_csv(
        path,
        sep=";",
        usecols=config.METEO_USECOLS,
        dtype=_READ_DTYPE,
        compression="gzip",
        chunksize=1_000_000,
    )
    for chunk in reader:
        ymd = pd.to_numeric(chunk["AAAAMMJJ"], errors="coerce")
        chunk = chunk[ymd >= _CACHE_START_INT]
        if chunk.empty:
            continue
        pieces.append(chunk)

    if not pieces:
        return pd.DataFrame(
            columns=["num_poste", "nom_usuel", "lat", "lon", "alti", "date", "tn"]
        )

    df = pd.concat(pieces, ignore_index=True)
    out = pd.DataFrame(
        {
            "num_poste": df["NUM_POSTE"].astype("string"),
            "nom_usuel": df["NOM_USUEL"].astype("string"),
            "lat": pd.to_numeric(df["LAT"], errors="coerce"),
            "lon": pd.to_numeric(df["LON"], errors="coerce"),
            "alti": pd.to_numeric(df["ALTI"], errors="coerce"),
            "date": pd.to_datetime(df["AAAAMMJJ"], format="%Y%m%d", errors="coerce"),
            "tn": pd.to_numeric(df["TN"], errors="coerce"),
        }
    )
    return out.dropna(subset=["date"])


def build_department_cache(dep: str, *, verbose: bool = True) -> Path:
    """Construit (si nécessaire) le cache Parquet d'un département et renvoie son chemin."""
    cache_path = config.METEO_CACHE_DIR / f"Q_{dep}_{config.CACHE_START[:4]}_{config.CACHE_END[:4]}.parquet"
    if cache_path.exists() and cache_path.stat().st_size > 0:
        return cache_path

    frames = []
    for url, local in _dep_urls(dep):
        try:
            src = ensure_file(url, local, label=local.name, verbose=verbose)
        except Exception as exc:  # le fichier "latest" peut manquer : on continue
            if "previous" in local.name:
                raise FileNotFoundError(
                    f"Impossible de récupérer les données du département {dep} ({url})."
                ) from exc
            continue
        frames.append(_parse_source(src))

    if not frames:
        raise FileNotFoundError(f"Aucune donnée météo pour le département {dep}.")

    df = pd.concat(frames, ignore_index=True)
    df = df.sort_values(["num_poste", "date"]).reset_index(drop=True)
    df.to_parquet(cache_path, index=False)
    return cache_path


def load_department(dep: str, *, verbose: bool = True) -> pd.DataFrame:
    """Renvoie toutes les observations TN d'un département sur la fenêtre de cache."""
    cache_path = build_department_cache(dep, verbose=verbose)
    return pd.read_parquet(cache_path)


def station_table(df: pd.DataFrame) -> pd.DataFrame:
    """Table des stations (1 ligne / station) avec coordonnées et amplitude temporelle."""
    grp = df.groupby("num_poste", observed=True)
    table = grp.agg(
        nom_usuel=("nom_usuel", "first"),
        lat=("lat", "median"),
        lon=("lon", "median"),
        alti=("alti", "median"),
        premiere_obs=("date", "min"),
        derniere_obs=("date", "max"),
        n_obs=("tn", "size"),
    ).reset_index()
    return table
