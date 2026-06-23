"""Graphiques Plotly réutilisables (interface Streamlit et notebooks).

Chaque fonction prend un :class:`~frost_days.frost.FrostReport` et renvoie une
figure Plotly prête à afficher.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

from .frost import FrostReport, _MONTHS_FR

_BLUES = "Blues"


def fig_per_year(report: FrostReport) -> go.Figure:
    """Nombre de jours de gel par année + moyenne."""
    py = report.per_year
    fig = px.bar(
        py, x="year", y="n_frost",
        labels={"year": "Année", "n_frost": "Jours de gel"},
        title="Jours de gel par année",
        text="n_frost",
    )
    fig.add_hline(
        y=report.avg_frost_days_per_year, line_dash="dash", line_color="crimson",
        annotation_text=f"moyenne {report.avg_frost_days_per_year:.0f} j/an",
    )
    fig.update_traces(marker_color="#4a78b5", textposition="outside")
    fig.update_layout(xaxis=dict(tickmode="linear", dtick=1))
    return fig


def fig_monthly(report: FrostReport) -> go.Figure:
    """Nombre moyen de jours de gel par mois (moyenne sur les années)."""
    d = report.daily.copy()
    d["year"] = d["date"].dt.year
    d["month"] = d["date"].dt.month
    per_year_month = d.groupby(["year", "month"])["is_frost"].sum().reset_index()
    monthly = per_year_month.groupby("month")["is_frost"].mean().reindex(range(1, 13), fill_value=0)
    fig = px.bar(
        x=[_MONTHS_FR[m].capitalize() for m in range(1, 13)],
        y=monthly.values,
        labels={"x": "Mois", "y": "Jours de gel (moyenne/an)"},
        title="Saisonnalité du gel (moyenne par mois)",
    )
    fig.update_traces(marker_color="#4a78b5")
    return fig


def fig_day_of_year(report: FrostReport) -> go.Figure:
    """Fréquence de gel (%) pour chaque jour calendaire de l'année."""
    doy = report.day_of_year.copy()
    doy["date_2001"] = pd.to_datetime(
        {"year": 2001, "month": doy["month"], "day": doy["day"]}
    )
    doy = doy.sort_values("date_2001")
    fig = px.area(
        doy, x="date_2001", y="freq_pct",
        labels={"date_2001": "Jour de l'année", "freq_pct": "Fréquence de gel (%)"},
        title="Probabilité de gel au fil de l'année",
        custom_data=["label", "n_frost", "n_years"],
    )
    fig.update_traces(
        line_color="#2a5d9c", fillcolor="rgba(74,120,181,0.4)",
        hovertemplate="%{customdata[0]} : %{y:.0f}%<br>(%{customdata[1]}/%{customdata[2]} ans)<extra></extra>",
    )
    fig.update_xaxes(tickformat="%d %b", dtick="M1")
    fig.update_yaxes(range=[0, 100])
    return fig


def fig_calendar_heatmap(report: FrostReport) -> go.Figure:
    """Carte de chaleur mois × jour de la fréquence de gel."""
    doy = report.day_of_year
    grid = np.full((12, 31), np.nan)
    for _, r in doy.iterrows():
        grid[int(r["month"]) - 1, int(r["day"]) - 1] = r["freq_pct"]
    fig = go.Figure(
        go.Heatmap(
            z=grid,
            x=list(range(1, 32)),
            y=[_MONTHS_FR[m].capitalize() for m in range(1, 13)],
            colorscale=_BLUES, zmin=0, zmax=100,
            colorbar=dict(title="% gel"),
            hovertemplate="%{y} %{x} : %{z:.0f}%<extra></extra>",
        )
    )
    fig.update_layout(
        title="Fréquence de gel par jour calendaire",
        xaxis_title="Jour du mois", yaxis_title="Mois",
        yaxis=dict(autorange="reversed"),
    )
    return fig


def fig_map(report: FrostReport) -> go.Figure:
    """Carte : commune, station retenue et stations candidates."""
    cand = report.candidates.copy()
    cand["type"] = np.where(
        cand["num_poste"] == report.station_id, "Station retenue", "Station candidate"
    )
    cand["info"] = cand.apply(
        lambda r: f"{r['nom_usuel']} – {r['distance_km']:.1f} km – "
        f"{r['missing_fraction']:.0%} manquant",
        axis=1,
    )
    rows = [
        {"lat": report.commune.lat, "lon": report.commune.lon,
         "type": "Commune", "info": report.commune.nom},
    ]
    for _, r in cand.iterrows():
        rows.append({"lat": r["lat"], "lon": r["lon"], "type": r["type"], "info": r["info"]})
    pts = pd.DataFrame(rows)

    color_map = {
        "Commune": "#d62728",
        "Station retenue": "#2ca02c",
        "Station candidate": "#7f7f7f",
    }
    common = dict(
        lat="lat", lon="lon", color="type", hover_name="info",
        color_discrete_map=color_map, zoom=8, height=480,
    )
    # Plotly >= 5.24 fournit scatter_map (MapLibre) ; sinon scatter_mapbox.
    if hasattr(px, "scatter_map"):
        fig = px.scatter_map(pts, **common)
        fig.update_layout(map_style="open-street-map")
    else:
        fig = px.scatter_mapbox(pts, **common)
        fig.update_layout(mapbox_style="open-street-map")
    fig.update_traces(marker=dict(size=12))
    fig.update_layout(
        margin=dict(l=0, r=0, t=0, b=0),
        legend=dict(orientation="h", yanchor="bottom", y=1.01),
    )
    return fig
