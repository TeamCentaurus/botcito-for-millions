"""
Piezas compartidas por las páginas de walk-forward (`app/pages/`).

Solo formato y gráficos: nada de cómputo (ADR-0004). Importar no tiene efectos.
"""

from __future__ import annotations

import plotly.graph_objects as go
import streamlit as st

# Misma paleta validada que app/dashboard.py
SERIE = "#2a78d6"
SERIE_DARK = "#3987e5"
CRITICO = "#d03b3b"
GRID = "#c3c2b7"
MUTED = "#898781"

HORIZONTES = ("1", "5", "10", "20")


def color_serie() -> str:
    try:
        return SERIE_DARK if st.get_option("theme.base") == "dark" else SERIE
    except Exception:  # pragma: no cover - Streamlit sin runtime
        return SERIE


def layout(figura: go.Figure, titulo: str, titulo_y: str, alto: int = 300) -> go.Figure:
    figura.update_layout(
        height=alto,
        margin={"l": 0, "r": 0, "t": 32, "b": 0},
        title={"text": titulo, "font": {"size": 14}},
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        yaxis={"title": titulo_y, "gridcolor": GRID, "zeroline": False},
        xaxis={"showgrid": False},
        legend={"orientation": "h", "y": -0.15},
    )
    return figura


def z(b: dict, clave: str = "pooled") -> float:
    """Desvíos de la nula de permutación (negativo = reversión)."""
    return (b[f"{clave}_ic"] - b[f"{clave}_null_media"]) / b[f"{clave}_null_sd"]


def figura_ic_anual(b: dict, titulo: str) -> go.Figure:
    """IC de cada año contra la banda ±2σ de su nula (que NO está centrada en 0)."""
    filas = b["por_anio"]
    anios = [f["anio"] for f in filas]
    media = [f["null_media"] for f in filas]
    sup = [f["null_media"] + 2 * f["null_sd"] for f in filas]
    inf = [f["null_media"] - 2 * f["null_sd"] for f in filas]
    figura = go.Figure()
    figura.add_trace(go.Scatter(x=anios + anios[::-1], y=sup + inf[::-1], fill="toself",
                                fillcolor="rgba(137,135,129,0.18)", line={"width": 0},
                                name="nula ±2σ", hoverinfo="skip"))
    figura.add_trace(go.Scatter(x=anios, y=media, mode="lines", name="media de la nula",
                                line={"color": MUTED, "width": 2, "dash": "dash"},
                                hovertemplate="%{x}: nula %{y:.3f}<extra></extra>"))
    figura.add_trace(go.Scatter(
        x=anios, y=[f["ic"] for f in filas], mode="lines+markers", name="IC real",
        line={"color": color_serie(), "width": 2},
        marker={"size": 9, "line": {"width": 2, "color": "rgba(255,255,255,0.9)"}},
        customdata=[f["p"] for f in filas],
        hovertemplate="%{x}: IC %{y:.3f} · p %{customdata:.3f}<extra></extra>"))
    figura.add_hline(y=0, line={"color": GRID, "width": 1})
    return layout(figura, titulo, "IC")


def figura_curva(curva: dict, titulo: str) -> go.Figure:
    figura = go.Figure(go.Scatter(
        x=curva["fechas"], y=curva["pnl_acumulado"], mode="lines",
        line={"color": color_serie(), "width": 2},
        hovertemplate="%{x}<br>acumulado %{y:.3f}<extra></extra>"))
    figura.add_hline(y=0, line={"color": GRID, "width": 1})
    figura.update_layout(showlegend=False, hovermode="x unified")
    return layout(figura, titulo, "retorno acumulado (bruto)", alto=280)


def figura_pvalues(a: dict, titulo: str) -> go.Figure:
    """p-values por acción ordenados, con la recta de BH y p = 0.05."""
    pares = sorted(zip(a["p"], a["tickers"], strict=True))
    n = len(pares)
    rango = list(range(1, n + 1))
    figura = go.Figure()
    figura.add_trace(go.Scatter(x=rango, y=[0.05 * i / n for i in rango], mode="lines",
                                name="umbral BH (5 %)",
                                line={"color": CRITICO, "width": 2}, hoverinfo="skip"))
    figura.add_hline(y=0.05, line={"color": MUTED, "width": 1, "dash": "dash"},
                     annotation_text="p = 0.05", annotation_position="top left",
                     annotation_font={"size": 10, "color": MUTED})
    figura.add_trace(go.Scatter(
        x=rango, y=[p for p, _ in pares], mode="markers", name="p-value por acción",
        marker={"size": 8, "color": color_serie(),
                "line": {"width": 2, "color": "rgba(255,255,255,0.9)"}},
        text=[t for _, t in pares],
        hovertemplate="%{text} · p %{y:.3f}<extra></extra>"))
    figura.update_yaxes(type="log", range=[-3.1, 0.05])
    figura = layout(figura, titulo, "p-value")
    figura.update_xaxes(title="rango de la acción")
    return figura


def figura_sectores(ic: dict, titulo: str) -> go.Figure:
    orden = sorted(ic.items(), key=lambda x: x[1])
    figura = go.Figure(go.Bar(
        x=[v for _, v in orden], y=[s for s, _ in orden], orientation="h",
        marker={"color": color_serie(), "cornerradius": 4},
        hovertemplate="%{y}: IC %{x:.3f}<extra></extra>"))
    figura.add_vline(x=0, line={"color": MUTED, "width": 1})
    figura.update_layout(showlegend=False, bargap=0.35)
    figura = layout(figura, titulo, "", alto=360)
    figura.update_xaxes(title="IC medio a 5 días", showgrid=True, gridcolor=GRID)
    return figura
