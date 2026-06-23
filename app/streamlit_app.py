"""Interface graphique Frost Days (Streamlit).

Lancement :  streamlit run app/streamlit_app.py
"""

from __future__ import annotations

import datetime as dt
import sys
from pathlib import Path

import pandas as pd
import streamlit as st

# Rend le package importable quand on lance via `streamlit run app/...`.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from frost_days import config, viz  # noqa: E402
from frost_days.communes import resolve_department  # noqa: E402
from frost_days.frost import compute_frost_report  # noqa: E402

st.set_page_config(page_title="Frost Days", page_icon="❄️", layout="wide")


@st.cache_data(show_spinner=False)
def run_report(commune, dep, start, end, max_missing, method):
    """Calcule le rapport (mis en cache par jeu de paramètres)."""
    return compute_frost_report(
        commune, dep, start, end,
        max_missing=max_missing, method=method, verbose=False,
    )


st.title("❄️ Frost Days — jours de gel par commune")
st.caption(
    "Nombre de jours de gel (température minimale **TN ≤ 0 °C**) à partir des "
    "données climatologiques quotidiennes de Météo-France (open data, data.gouv.fr)."
)

with st.sidebar:
    st.header("Paramètres")
    commune = st.text_input("Commune", value="Briançon")
    departement = st.text_input("Département (code ou nom)", value="05")

    today = dt.date(2023, 12, 31)
    default_start = dt.date(2014, 1, 1)
    date_range = st.date_input(
        "Plage de dates",
        value=(default_start, today),
        min_value=dt.date(2013, 1, 1),
        max_value=dt.date(2024, 12, 31),
        format="YYYY-MM-DD",
    )

    with st.expander("Options avancées"):
        max_missing = st.slider(
            "Seuil de valeurs manquantes par station", 0.0, 1.0,
            value=config.MAX_MISSING_FRACTION, step=0.05,
            help="Une station dépassant ce taux sur la période est écartée.",
        )
        method = st.radio(
            "Recherche de station", ["haversine", "kdtree"], index=0,
            help="Haversine = distance exacte ; KDTree = approximation rapide.",
        )

    run = st.button("Calculer", type="primary", width='stretch')

# Une fois le calcul demandé, on mémorise l'intention : ainsi le résultat reste
# affiché même si la page se rafraîchit (ex. pendant un téléchargement long).
if run:
    st.session_state["calcul_demande"] = True

if not st.session_state.get("calcul_demande"):
    st.info("Renseignez une commune, un département et une plage de dates, puis cliquez sur **Calculer**.")
    st.stop()

if not isinstance(date_range, (tuple, list)) or len(date_range) != 2:
    st.warning("Sélectionnez une **plage** de dates (début et fin).")
    st.stop()

start, end = date_range
if resolve_department(departement) is None:
    st.error(f"Département introuvable : {departement!r}.")
    st.stop()

try:
    with st.spinner("Téléchargement / calcul en cours (le premier appel d'un département peut prendre ~1 min)…"):
        report = run_report(commune, departement, str(start), str(end), max_missing, method)
except (ValueError, FileNotFoundError) as exc:
    st.error(str(exc))
    st.stop()

# --------------------------------------------------------------------------- #
# En-tête : indicateurs clés
# --------------------------------------------------------------------------- #
c = report.commune
st.subheader(f"{c.nom} ({c.dep_code} — {c.dep_nom})")

m1, m2, m3, m4 = st.columns(4)
m1.metric("Jours de gel (total)", f"{report.total_frost_days}")
m2.metric("Moyenne par an", f"{report.avg_frost_days_per_year:.1f} j")
m3.metric("Période", f"{report.n_years:.1f} ans")
m4.metric("Station retenue", report.station_name, f"{report.station_distance_km:.1f} km")

st.caption(
    f"Station #{report.station_id} · altitude {report.station_alti:.0f} m · "
    f"{report.station_missing_fraction:.1%} de valeurs manquantes sur la période"
    + (f" · coordonnées commune : {c.coord_source}" if c.coord_source != "referentiel" else "")
)

# --------------------------------------------------------------------------- #
# Graphiques
# --------------------------------------------------------------------------- #
left, right = st.columns(2)
left.plotly_chart(viz.fig_per_year(report), width='stretch')
right.plotly_chart(viz.fig_monthly(report), width='stretch')

st.plotly_chart(viz.fig_day_of_year(report), width='stretch')
st.plotly_chart(viz.fig_calendar_heatmap(report), width='stretch')

# --------------------------------------------------------------------------- #
# Détails : jours les plus gélifs, stations, carte
# --------------------------------------------------------------------------- #
tab_jours, tab_stations, tab_carte = st.tabs(
    ["📅 Jours les plus gélifs", "📡 Stations évaluées", "🗺️ Carte"]
)

with tab_jours:
    doy = report.day_of_year.sort_values(["freq_pct", "n_frost"], ascending=False)
    show = doy[["label", "n_frost", "n_years", "freq_pct"]].rename(
        columns={"label": "Jour", "n_frost": "Années avec gel",
                 "n_years": "Années observées", "freq_pct": "Fréquence (%)"}
    )
    st.dataframe(show, width='stretch', hide_index=True,
                 column_config={"Fréquence (%)": st.column_config.NumberColumn(format="%.0f %%")})

with tab_stations:
    cand = report.candidates.copy()
    cand = cand[["nom_usuel", "num_poste", "distance_km", "alti",
                 "missing_fraction", "retenue_qualite"]].rename(
        columns={"nom_usuel": "Station", "num_poste": "ID", "distance_km": "Distance (km)",
                 "alti": "Altitude (m)", "missing_fraction": "Valeurs manquantes",
                 "retenue_qualite": "Sous le seuil ?"}
    )
    st.dataframe(cand, width='stretch', hide_index=True,
                 column_config={"Distance (km)": st.column_config.NumberColumn(format="%.1f"),
                                "Valeurs manquantes": st.column_config.NumberColumn(format="%.0f %%")})
    st.caption("La station retenue est la plus proche dont le taux de valeurs manquantes est sous le seuil.")

with tab_carte:
    st.plotly_chart(viz.fig_map(report), width='stretch')

# --------------------------------------------------------------------------- #
# Téléchargements
# --------------------------------------------------------------------------- #
st.divider()
tag = f"{c.nom}_{c.dep_code}".replace(" ", "_")
d1, d2, d3 = st.columns(3)
d1.download_button("⬇️ Données quotidiennes (CSV)",
                   report.daily.to_csv(index=False).encode("utf-8"),
                   file_name=f"{tag}_quotidien.csv", mime="text/csv")
d2.download_button("⬇️ Par année (CSV)",
                   report.per_year.to_csv(index=False).encode("utf-8"),
                   file_name=f"{tag}_par_annee.csv", mime="text/csv")
d3.download_button("⬇️ Par jour calendaire (CSV)",
                   report.day_of_year.to_csv(index=False).encode("utf-8"),
                   file_name=f"{tag}_par_jour.csv", mime="text/csv")
