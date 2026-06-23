"""Distances géographiques et recherche des stations les plus proches.

Deux approches sont fournies, comme suggéré dans l'énoncé :

* ``haversine`` : distance orthodromique exacte (à vol d'oiseau) sur une sphère.
  C'est la méthode utilisée par défaut car la plus précise.
* ``cKDTree`` (scipy) : recherche approximative très rapide. Les coordonnées
  (lat, lon) sont projetées sur la sphère unité en 3D pour que la distance
  euclidienne de l'arbre respecte l'ordre des distances réelles.

Le nombre de stations par département étant modeste (quelques dizaines à
quelques centaines), Haversine vectorisé est déjà instantané ; le KDTree est
surtout utile si l'on veut interroger l'ensemble des stations de France.
"""

from __future__ import annotations

import numpy as np

EARTH_RADIUS_KM = 6371.0088


def haversine(lat1, lon1, lat2, lon2) -> np.ndarray:
    """Distance orthodromique en kilomètres.

    Les arguments peuvent être des scalaires ou des tableaux numpy ; la
    fonction est entièrement vectorisée (broadcasting numpy).
    """
    lat1, lon1, lat2, lon2 = map(np.asarray, (lat1, lon1, lat2, lon2))
    phi1, phi2 = np.radians(lat1), np.radians(lat2)
    dphi = np.radians(lat2 - lat1)
    dlambda = np.radians(lon2 - lon1)
    a = np.sin(dphi / 2.0) ** 2 + np.cos(phi1) * np.cos(phi2) * np.sin(dlambda / 2.0) ** 2
    return 2.0 * EARTH_RADIUS_KM * np.arcsin(np.sqrt(a))


def _to_unit_sphere(lat, lon) -> np.ndarray:
    """Projette des (lat, lon) en degrés vers des coordonnées 3D unitaires."""
    lat_r, lon_r = np.radians(lat), np.radians(lon)
    x = np.cos(lat_r) * np.cos(lon_r)
    y = np.cos(lat_r) * np.sin(lon_r)
    z = np.sin(lat_r)
    return np.column_stack([x, y, z])


def nearest_by_haversine(lat, lon, st_lat, st_lon, k=None):
    """Indices des stations triées par distance Haversine croissante.

    Renvoie ``(indices, distances_km)`` ; ``k`` limite éventuellement le nombre
    de résultats.
    """
    st_lat = np.asarray(st_lat, dtype=float)
    st_lon = np.asarray(st_lon, dtype=float)
    dist = haversine(lat, lon, st_lat, st_lon)
    order = np.argsort(dist, kind="stable")
    if k is not None:
        order = order[:k]
    return order, dist[order]


def nearest_by_kdtree(lat, lon, st_lat, st_lon, k=None):
    """Variante KDTree (scipy) sur la sphère unité — très rapide.

    L'ordre obtenu est cohérent avec la distance réelle ; la distance renvoyée
    est recalculée en km via Haversine pour rester interprétable.
    """
    from scipy.spatial import cKDTree

    st_lat = np.asarray(st_lat, dtype=float)
    st_lon = np.asarray(st_lon, dtype=float)
    tree = cKDTree(_to_unit_sphere(st_lat, st_lon))
    kk = len(st_lat) if k is None else min(k, len(st_lat))
    point = _to_unit_sphere(np.array([lat]), np.array([lon]))
    _, idx = tree.query(point, k=kk)
    idx = np.atleast_1d(idx[0])
    dist_km = haversine(lat, lon, st_lat[idx], st_lon[idx])
    return idx, dist_km


def nearest_stations(lat, lon, st_lat, st_lon, k=None, method="haversine"):
    """Point d'entrée unique : ``method`` vaut ``"haversine"`` ou ``"kdtree"``."""
    if method == "kdtree":
        return nearest_by_kdtree(lat, lon, st_lat, st_lon, k=k)
    if method == "haversine":
        return nearest_by_haversine(lat, lon, st_lat, st_lon, k=k)
    raise ValueError(f"Méthode inconnue : {method!r} (attendu 'haversine' ou 'kdtree')")
