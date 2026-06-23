"""Tests du coeur métier (sélection de station + statistiques de gel).

On utilise des données synthétiques en mémoire : aucun accès réseau.
"""

import numpy as np
import pandas as pd

from frost_days import config
from frost_days.communes import Commune
from frost_days.frost import (
    _day_of_year,
    _per_year,
    evaluate_stations,
    select_station,
)


def _synthetic_station(num_poste, nom, lat, lon, dates, tn):
    return pd.DataFrame(
        {
            "num_poste": num_poste,
            "nom_usuel": nom,
            "lat": lat,
            "lon": lon,
            "alti": 100.0,
            "date": dates,
            "tn": tn,
        }
    )


def test_evaluate_stations_missing_fraction():
    # Station A : 366 jours, tous renseignés -> 0 % manquant.
    dates = pd.date_range("2020-01-01", "2020-12-31", freq="D")
    tn = np.where(dates.month == 1, -5.0, 10.0)
    df = _synthetic_station("A", "STATION_A", 43.0, 5.0, dates, tn)
    table = evaluate_stations(df, pd.Timestamp("2020-01-01"), pd.Timestamp("2020-12-31"))
    row = table.iloc[0]
    assert row["n_tn"] == 366
    assert abs(row["missing_fraction"]) < 1e-9


def test_evaluate_stations_with_gaps():
    # 200 jours renseignés sur 366 attendus -> ~45 % manquant (> seuil).
    dates = pd.date_range("2020-01-01", "2020-12-31", freq="D")
    tn = np.full(len(dates), -1.0)
    tn[200:] = np.nan
    df = _synthetic_station("B", "STATION_B", 43.0, 5.0, dates, tn)
    table = evaluate_stations(df, pd.Timestamp("2020-01-01"), pd.Timestamp("2020-12-31"))
    frac = table.iloc[0]["missing_fraction"]
    assert frac > config.MAX_MISSING_FRACTION


def test_select_station_skips_high_missing():
    """La station la plus proche est exclue si trop de valeurs manquantes."""
    stations = pd.DataFrame(
        {
            "num_poste": ["near", "far"],
            "nom_usuel": ["PROCHE", "LOIN"],
            "lat": [43.001, 43.10],
            "lon": [5.001, 5.10],
            "alti": [100.0, 120.0],
            "n_tn": [10, 360],
            "n_expected": [366, 366],
            "missing_fraction": [0.97, 0.02],
        }
    )
    commune = Commune("00000", "Test", "83", "Var", 43.0, 5.0, 1000.0, "referentiel")
    chosen, candidates = select_station(commune, stations)
    assert chosen["num_poste"] == "far"  # la proche est écartée (97 % manquant)
    assert len(candidates) == 2


def test_per_year_counts():
    dates = pd.date_range("2020-01-01", "2021-12-31", freq="D")
    tn = np.where(dates.month == 1, -5.0, 10.0)  # janvier gèle
    daily = pd.DataFrame({"date": dates, "tn": tn})
    daily["is_frost"] = daily["tn"] <= 0
    py = _per_year(daily).set_index("year")
    assert py.loc[2020, "n_frost"] == 31
    assert py.loc[2021, "n_frost"] == 31


def test_day_of_year_excludes_feb_29():
    dates = pd.date_range("2020-01-01", "2020-12-31", freq="D")  # année bissextile
    tn = np.full(len(dates), -2.0)
    daily = pd.DataFrame({"date": dates, "tn": tn})
    daily["is_frost"] = daily["tn"] <= 0
    doy = _day_of_year(daily)
    assert not (((doy["month"] == 2) & (doy["day"] == 29)).any())
    assert len(doy) == 365
    # Tous gelés -> fréquence 100 % partout.
    assert (doy["freq_pct"] == 100.0).all()


def test_day_of_year_relative_frequency():
    # Deux ans : le 5 janvier gèle 1 fois sur 2 -> 50 %.
    dates = pd.date_range("2020-01-01", "2021-12-31", freq="D")
    daily = pd.DataFrame({"date": dates, "tn": 10.0})
    daily.loc[daily["date"] == pd.Timestamp("2020-01-05"), "tn"] = -3.0
    daily["is_frost"] = daily["tn"] <= 0
    doy = _day_of_year(daily)
    jan5 = doy[(doy["month"] == 1) & (doy["day"] == 5)].iloc[0]
    assert jan5["n_years"] == 2
    assert jan5["n_frost"] == 1
    assert jan5["freq_pct"] == 50.0
