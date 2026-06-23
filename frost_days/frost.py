"""Coeur métier : sélection de station et calcul des jours de gel.

Un *jour de gel* est un jour où la température minimale TN a été <= 0 °C.

Le calcul, pour une commune + un département + une plage de dates :

1. on charge les observations TN du département (cache Parquet) ;
2. on restreint à la plage demandée ;
3. on évalue chaque station : taux de valeurs manquantes sur la période. Toute
   station avec > 35 % de valeurs manquantes est écartée ;
4. parmi les stations retenues, on garde la plus proche de la commune
   (distance de Haversine) ;
5. on calcule les statistiques de gel demandées.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from . import config, meteo
from .communes import Commune, find_commune
from .geo import haversine

_MONTHS_FR = [
    "", "janvier", "février", "mars", "avril", "mai", "juin",
    "juillet", "août", "septembre", "octobre", "novembre", "décembre",
]


def french_day_label(month: int, day: int) -> str:
    """Ex. (3, 31) -> '31 mars', (1, 1) -> '1er janvier'."""
    d = "1er" if day == 1 else str(day)
    return f"{d} {_MONTHS_FR[month]}"


@dataclass
class FrostReport:
    """Résultat complet d'une analyse de jours de gel."""

    commune: Commune
    start: pd.Timestamp
    end: pd.Timestamp

    # Station retenue
    station_id: str
    station_name: str
    station_lat: float
    station_lon: float
    station_alti: float
    station_distance_km: float
    station_missing_fraction: float

    # Résultats principaux
    total_frost_days: int
    n_years: float
    avg_frost_days_per_year: float

    # Tables détaillées
    daily: pd.DataFrame          # date, tn, is_frost
    per_year: pd.DataFrame       # year, n_frost, n_days_observed
    day_of_year: pd.DataFrame    # month, day, label, n_years, n_frost, freq_pct
    candidates: pd.DataFrame     # stations évaluées (proximité + qualité)

    def summary_text(self) -> str:
        """Résumé lisible en console."""
        c = self.commune
        lines = [
            f"Commune    : {c.nom} ({c.dep_code} – {c.dep_nom})"
            + (f"  [coord. {c.coord_source}]" if c.coord_source != "referentiel" else ""),
            f"Période    : {self.start.date()} → {self.end.date()}  ({self.n_years:.2f} ans)",
            f"Station    : {self.station_name} (#{self.station_id}), "
            f"{self.station_distance_km:.1f} km, {self.station_alti:.0f} m, "
            f"{self.station_missing_fraction:.1%} de valeurs manquantes",
            "",
            f"Jours de gel (TN <= {config.FROST_THRESHOLD_C:g}°C) sur la période : "
            f"{self.total_frost_days}",
            f"Moyenne par an : {self.avg_frost_days_per_year:.1f} jours",
        ]
        return "\n".join(lines)


# --------------------------------------------------------------------------- #
# Évaluation de la qualité des stations sur la période
# --------------------------------------------------------------------------- #
def evaluate_stations(
    df: pd.DataFrame, start: pd.Timestamp, end: pd.Timestamp
) -> pd.DataFrame:
    """Pour chaque station : nb d'observations TN valides et taux de manquants.

    Le taux de manquants est calculé par rapport au nombre de jours calendaires
    de la période demandée.
    """
    n_expected = (end - start).days + 1
    window = df[(df["date"] >= start) & (df["date"] <= end)]

    grp = window.groupby("num_poste", observed=True)
    table = grp.agg(
        nom_usuel=("nom_usuel", "first"),
        lat=("lat", "median"),
        lon=("lon", "median"),
        alti=("alti", "median"),
        n_tn=("tn", "count"),          # count ignore les NaN
    ).reset_index()

    table["n_expected"] = n_expected
    table["missing_fraction"] = 1.0 - table["n_tn"] / n_expected
    table["missing_fraction"] = table["missing_fraction"].clip(lower=0.0)
    return table


def select_station(
    commune: Commune,
    stations: pd.DataFrame,
    *,
    max_missing: float = config.MAX_MISSING_FRACTION,
    n_candidates: int = config.DEFAULT_N_CANDIDATES,
    method: str = "haversine",
):
    """Classe les stations par distance et renvoie (retenue, table_candidats).

    Les stations dépassant ``max_missing`` sont marquées comme exclues ; la
    station retenue est la plus proche parmi celles qui restent.
    """
    stations = stations.dropna(subset=["lat", "lon"]).copy()
    if stations.empty:
        raise ValueError("Aucune station avec coordonnées dans ce département.")

    stations["distance_km"] = haversine(
        commune.lat, commune.lon, stations["lat"].to_numpy(), stations["lon"].to_numpy()
    )
    stations = stations.sort_values("distance_km").reset_index(drop=True)
    stations["retenue_qualite"] = stations["missing_fraction"] <= max_missing

    candidates = stations.head(n_candidates).copy()

    eligible = stations[stations["retenue_qualite"]]
    if eligible.empty:
        best = stations.iloc[0]
        raise ValueError(
            "Aucune station ne respecte le seuil de "
            f"{max_missing:.0%} de valeurs manquantes près de {commune.nom}. "
            f"La plus proche ({best['nom_usuel']}) en compte "
            f"{best['missing_fraction']:.0%}."
        )
    chosen = eligible.iloc[0]
    return chosen, candidates


# --------------------------------------------------------------------------- #
# Statistiques de gel
# --------------------------------------------------------------------------- #
def _per_year(daily: pd.DataFrame) -> pd.DataFrame:
    g = daily.groupby(daily["date"].dt.year)
    out = g.agg(
        n_frost=("is_frost", "sum"),
        n_days_observed=("is_frost", "size"),
    ).reset_index(names="year")
    out["n_frost"] = out["n_frost"].astype(int)
    return out


def _day_of_year(daily: pd.DataFrame) -> pd.DataFrame:
    """Fréquence de gel par jour calendaire (hors 29 février)."""
    d = daily.copy()
    d["month"] = d["date"].dt.month
    d["day"] = d["date"].dt.day
    d["year"] = d["date"].dt.year
    d = d[~((d["month"] == 2) & (d["day"] == 29))]

    grp = d.groupby(["month", "day"])
    out = grp.agg(
        n_years=("year", "nunique"),
        n_frost=("is_frost", "sum"),
    ).reset_index()
    out["n_frost"] = out["n_frost"].astype(int)
    out["freq_pct"] = np.where(
        out["n_years"] > 0, 100.0 * out["n_frost"] / out["n_years"], np.nan
    )
    out["label"] = [french_day_label(m, j) for m, j in zip(out["month"], out["day"])]
    return out.sort_values(["month", "day"]).reset_index(drop=True)


def compute_frost_report(
    commune_name: str,
    department: str,
    start,
    end,
    *,
    max_missing: float = config.MAX_MISSING_FRACTION,
    n_candidates: int = config.DEFAULT_N_CANDIDATES,
    method: str = "haversine",
    verbose: bool = True,
) -> FrostReport:
    """Calcule le rapport complet des jours de gel pour une commune et une période."""
    start = pd.Timestamp(start)
    end = pd.Timestamp(end)
    if end < start:
        raise ValueError("La date de fin précède la date de début.")

    commune = find_commune(commune_name, department)
    df = meteo.load_department(commune.dep_code, verbose=verbose)

    stations = evaluate_stations(df, start, end)
    chosen, candidates = select_station(
        commune, stations, max_missing=max_missing,
        n_candidates=n_candidates, method=method,
    )

    # Série quotidienne de la station retenue, sur la période, TN non nulle.
    mask = (
        (df["num_poste"] == chosen["num_poste"])
        & (df["date"] >= start)
        & (df["date"] <= end)
        & df["tn"].notna()
    )
    daily = df.loc[mask, ["date", "tn"]].sort_values("date").reset_index(drop=True)
    daily["is_frost"] = daily["tn"] <= config.FROST_THRESHOLD_C

    per_year = _per_year(daily)
    day_of_year = _day_of_year(daily)

    total = int(daily["is_frost"].sum())
    n_years = (end - start).days / 365.25
    # Moyenne par an : moyenne des comptes annuels (robuste aux années partielles
    # quand la période couvre des années entières, comme 2014-2023).
    avg_per_year = float(per_year["n_frost"].mean()) if not per_year.empty else 0.0

    return FrostReport(
        commune=commune,
        start=start,
        end=end,
        station_id=str(chosen["num_poste"]),
        station_name=str(chosen["nom_usuel"]),
        station_lat=float(chosen["lat"]),
        station_lon=float(chosen["lon"]),
        station_alti=float(chosen["alti"]) if pd.notna(chosen["alti"]) else float("nan"),
        station_distance_km=float(chosen["distance_km"]),
        station_missing_fraction=float(chosen["missing_fraction"]),
        total_frost_days=total,
        n_years=n_years,
        avg_frost_days_per_year=avg_per_year,
        daily=daily,
        per_year=per_year,
        day_of_year=day_of_year,
        candidates=candidates,
    )
