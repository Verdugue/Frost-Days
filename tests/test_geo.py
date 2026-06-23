"""Tests des fonctions géographiques (distances et plus proche station)."""

import numpy as np

from frost_days import geo


def test_haversine_paris_lyon():
    d = float(geo.haversine(48.8566, 2.3522, 45.7640, 4.8357))
    assert 390 < d < 395  # ~392 km


def test_haversine_zero_distance():
    assert float(geo.haversine(43.0, 5.0, 43.0, 5.0)) == 0.0


def test_nearest_methods_agree():
    st_lat = np.array([48.85, 45.76, 43.30, 47.21])
    st_lon = np.array([2.35, 4.83, 5.37, -1.55])
    idx_h, dist_h = geo.nearest_stations(48.86, 2.33, st_lat, st_lon, k=3, method="haversine")
    idx_k, dist_k = geo.nearest_stations(48.86, 2.33, st_lat, st_lon, k=3, method="kdtree")
    # Le plus proche doit être identique et la distance cohérente.
    assert idx_h[0] == idx_k[0] == 0
    assert abs(dist_h[0] - dist_k[0]) < 1e-6


def test_nearest_is_sorted():
    st_lat = np.array([48.85, 45.76, 43.30])
    st_lon = np.array([2.35, 4.83, 5.37])
    _, dist = geo.nearest_stations(48.86, 2.33, st_lat, st_lon, method="haversine")
    assert list(dist) == sorted(dist)
