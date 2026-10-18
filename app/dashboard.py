"""
Dashboard de resultados — lector puro del artefacto de corrida.

ADR-0004: este módulo NO calcula nada. No importa `run_backtest`, ni
`screen_universe`, ni `train`: solo `botcito_core.reporting`. Un dashboard que
recalcula es una segunda implementación del pipeline que diverge en silencio, y un
número que el backtest no produjo es indistinguible de uno correcto hasta que
alguien opera con él. La frontera está verificada en
`tests/test_spec_009_reporting.py::test_ac4_dashboard_es_lector_puro`.

Todo el render vive dentro de `main()`: importar este módulo no debe tener efectos
(es el error de `botcito_core/monitoring.py`, que no se puede importar).

Uso:  uv run streamlit run app/dashboard.py
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from botcito_core.reporting import list_runs, read_run

RUNS_DIR = Path(__file__).resolve().parents[1] / "runs"

# Paleta validada con el validador de la skill dataviz: PASS en los 5 checks contra
# la superficie clara (#ffffff) y la oscura (#0e1117) de Streamlit.
# Serie azul vs crítico rojo: ΔE normal 31.6 / CVD 23.8 en claro.
SERIE = "#2a78d6"
SERIE_DARK = "#3987e5"
CRITICO = "#d03b3b"
GRID = "#c3c2b7"
MUTED = "#898781"

COLUMNAS_SCREENING = {
    "par": "Par",
    "p_value": "p-value crudo",
    "p_value_corregido": "p-value corregido (BH)",
    "rechaza_h0_fdr": "Pasa FDR",
    "cumple_filtros_locales": "Filtros locales",
    "valido": "Válido",
    "half_life_dias": "Half-life (d)",
    "hedge_ratio": "Hedge ratio",
}


def _color_serie() -> str:
    """El paso de azul correspondiente al tema activo del visor."""
    try:
        return SERIE_DARK if st.get_option("theme.base") == "dark" else SERIE
    except Exception:  # pragma: no cover - Streamlit sin runtime
        return SERIE


def _figura_linea(fechas: list[str], valores: list[float], nombre: str,
                  titulo_y: str) -> go.Figure:
    """
    Una serie por figura. Nunca dos escalas en un mismo eje: el spread está en
    dólares y el z-score en desviaciones estándar, así que van en figuras separadas
    con el eje x compartido visualmente, no en un eje doble.
    """
    figura = go.Figure()
    figura.add_trace(
        go.Scatter(
            x=fechas,
            y=valores,
            mode="lines",
            name=nombre,
            line={"color": _color_serie(), "width": 2},
            hovertemplate=f"%{{x}}<br>{nombre}: %{{y:.4f}}<extra></extra>",
        )
    )
    figura.update_layout(
        height=280,
        margin={"l": 0, "r": 0, "t": 28, "b": 0},
        title={"text": nombre, "font": {"size": 14}},
        showlegend=False,  # una sola serie: el título la nombra
        hovermode="x unified",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        yaxis={"title": titulo_y, "gridcolor": GRID, "zeroline": False},
        xaxis={"gridcolor": GRID, "showgrid": False},
    )
    return figura


def _marcar_umbrales(figura: go.Figure, modelo: dict) -> go.Figure:
    """Umbrales del modelo sobre el gráfico de z-score, con etiqueta directa."""
    entrada = float(modelo["entry_threshold"])
    salida = float(modelo["exit_threshold"])
    stop = float(modelo["stop_loss_threshold"])

    figura.add_hrect(
        y0=-salida, y1=salida,
        fillcolor=MUTED, opacity=0.12, line_width=0,
        annotation_text="zona de cierre", annotation_position="top left",
        annotation_font={"size": 10, "color": MUTED},
    )
    for signo in (1, -1):
        figura.add_hline(
            y=signo * entrada, line={"color": MUTED, "width": 1, "dash": "dash"},
            annotation_text="entrada" if signo == 1 else None,
            annotation_position="right",
            annotation_font={"size": 10, "color": MUTED},
        )
        figura.add_hline(
            y=signo * stop, line={"color": CRITICO, "width": 1, "dash": "dash"},
            annotation_text="stop" if signo == 1 else None,
            annotation_position="right",
            annotation_font={"size": 10, "color": CRITICO},
        )
    return figura


def _tabla_screening(screening: list[dict]) -> pd.DataFrame:
    """Aplana el bloque de screening a una tabla ordenable."""
    filas = []
    for entrada in screening:
        cointegracion = entrada.get("cointegracion") or {}
        filas.append(
            {
                "par": entrada.get("par"),
                "p_value": cointegracion.get("p_value"),
                "p_value_corregido": entrada.get("p_value_corregido"),
                "rechaza_h0_fdr": entrada.get("rechaza_h0_fdr"),
                "cumple_filtros_locales": entrada.get("cumple_filtros_locales"),
                "valido": entrada.get("valido"),
                "half_life_dias": entrada.get("half_life_dias"),
                "hedge_ratio": entrada.get("hedge_ratio"),
            }
        )
    tabla = pd.DataFrame(filas)
    if not tabla.empty:
        tabla = tabla.sort_values("p_value", na_position="last")
    return tabla.rename(columns=COLUMNAS_SCREENING)


def _metricas(backtest: dict) -> None:
    """Fila de stat tiles. Lo que no existe en la corrida se muestra como '—'."""
    def fmt(valor, patron="{:.4f}"):
        return "—" if valor is None else patron.format(valor)

    columnas = st.columns(6)
    columnas[0].metric("Sharpe", fmt(backtest.get("sharpe_ratio")))
    columnas[1].metric("Retorno total", fmt(backtest.get("total_return"), "{:.2%}"))
    columnas[2].metric("PnL", fmt(backtest.get("total_pnl"), "{:,.2f}"))
    columnas[3].metric("Max drawdown", fmt(backtest.get("max_drawdown"), "{:.2%}"))
    columnas[4].metric("Win rate", fmt(backtest.get("win_rate"), "{:.1%}"))
    columnas[5].metric("Trades", str(backtest.get("total_trades", "—")))

    factor = backtest.get("annualization_factor")
    st.caption(
        f"Factor de anualización de la corrida: {factor if factor is not None else '—'}"
    )


def main() -> None:
    st.set_page_config(page_title="botcito · resultados", page_icon="📈", layout="wide")
    st.title("Resultados de corrida")

    artefactos = list_runs(RUNS_DIR)
    if not artefactos:
        st.info(
            f"No hay artefactos en `{RUNS_DIR}`.\n\n"
            "Corré el pipeline con `notebooks/02_pipeline_run.ipynb`, que escribe "
            "la corrida con `botcito_core.reporting.write_run`."
        )
        return

    nombres = [ruta.name for ruta in artefactos]
    elegido = st.sidebar.selectbox("Corrida", nombres, index=0)
    ruta = artefactos[nombres.index(elegido)]

    try:
        run = read_run(ruta)
    except (ValueError, FileNotFoundError) as error:
        st.error(f"No se pudo leer `{ruta.name}`: {error}")
        return

    # --- Advertencias primero: antes de cualquier número ---------------------
    advertencias = run.get("advertencias") or []
    if advertencias:
        st.warning(
            "**Esta corrida tiene resultados degradados:**\n\n"
            + "\n".join(f"- {texto}" for texto in advertencias)
        )

    # --- Contexto de la corrida ---------------------------------------------
    fuente = run["data_source"]
    cabecera = st.columns(3)
    cabecera[0].markdown(
        f"**Corrida:** `{run['run_id']}`  \n**Creada:** {run['created_at'][:19]}"
    )
    cabecera[1].markdown(
        f"**Fuente:** {fuente.get('provider')} · {fuente.get('interval')}  \n"
        f"**Rango:** {fuente.get('start')} → {fuente.get('end')}  \n"
        f"**Tickers:** {len(fuente.get('tickers') or [])}"
    )
    split = run["split"]
    cabecera[2].markdown(
        f"**Train hasta:** {split.get('train_end')}  \n"
        f"**Val:** {split.get('val_start')} → {split.get('val_end')}  \n"
        f"**Test:** {split.get('test_start')} → {split.get('test_end')}"
    )
    with st.expander("Parámetros de la corrida"):
        st.json(run["params"])

    # --- Screening -----------------------------------------------------------
    st.subheader("Screening")
    tabla = _tabla_screening(run["screening"])
    total = len(tabla)
    n_validos = int(tabla[COLUMNAS_SCREENING["valido"]].sum()) if total else 0
    crudos = tabla[COLUMNAS_SCREENING["p_value"]]
    alpha = run["params"].get("alpha", 0.05)
    n_crudos = int((crudos < alpha).sum()) if total else 0

    resumen = st.columns(3)
    resumen[0].metric("Pares evaluados", f"{total:,}")
    resumen[1].metric(f"Pasarían sin corregir (α={alpha})", f"{n_crudos:,}")
    resumen[2].metric("Válidos tras BH-FDR", f"{n_validos:,}")
    st.caption(
        "Las dos columnas de p-value van juntas a propósito: con m tests, el primero "
        "del ranking necesita p ≤ α/m. Es la diferencia entre un candidato y un "
        "falso positivo del multiple testing."
    )

    solo_validos = st.checkbox("Mostrar solo los válidos", value=False)
    vista = tabla[tabla[COLUMNAS_SCREENING["valido"]] == True] if solo_validos else tabla  # noqa: E712
    st.dataframe(vista, width="stretch", hide_index=True)

    # --- Detalle por par -----------------------------------------------------
    backtests = run.get("backtests") or []
    if not backtests:
        st.info("Esta corrida no incluye backtests.")
        return

    st.subheader("Detalle por par")
    etiquetas = [f"{b['par']} · {b['periodo']}" for b in backtests]
    seleccion = st.selectbox("Par", etiquetas, index=0)
    backtest = backtests[etiquetas.index(seleccion)]

    modelos = {f"{m['ticker_a']}/{m['ticker_b']}": m for m in run.get("models") or []}
    modelo = modelos.get(backtest["par"])

    _metricas(backtest)

    series = backtest.get("series") or {}
    fechas = series.get("fechas") or []

    if series.get("zscore"):
        figura = _figura_linea(fechas, series["zscore"], "Z-score del spread", "z")
        if modelo:
            _marcar_umbrales(figura, modelo)
        st.plotly_chart(figura, width="stretch", theme="streamlit")
    else:
        st.info("Esta corrida no guardó la serie de z-score.")

    if series.get("spread"):
        st.plotly_chart(
            _figura_linea(fechas, series["spread"], "Spread (A − β·B)", "spread"),
            width="stretch",
            theme="streamlit",
        )

    if series.get("equity_curve"):
        st.plotly_chart(
            _figura_linea(fechas, series["equity_curve"], "Curva de equity", "equity"),
            width="stretch",
            theme="streamlit",
        )

    trades = backtest.get("trades") or []
    st.markdown(f"**Trades** ({len(trades)})")
    if trades:
        st.dataframe(pd.DataFrame(trades), width="stretch", hide_index=True)
    else:
        st.caption("Sin trades registrados en este período.")

    if modelo:
        with st.expander("Modelo del par"):
            st.json(modelo)


if __name__ == "__main__":
    main()
