"""
Walk-forward de SPEC-011 — lector puro de `research/wf011/resultado.json`.

Mismo criterio que `app/dashboard.py` (ADR-0004): esta página NO calcula nada, solo
muestra lo que escribió `research/wf011/walk_forward.py`. Si falta un número, se
agrega al script y se vuelve a correr; no se recalcula acá.

Uso:  uv run streamlit run app/dashboard.py   → página "walk forward 011" en la barra
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import wf_comun as C  # noqa: E402

HORIZONTES = C.HORIZONTES
_z, _figura_ic_anual, _figura_curva = C.z, C.figura_ic_anual, C.figura_curva
_figura_sectores, figura_pvalues = C.figura_sectores, C.figura_pvalues

RESULTADO = Path(__file__).resolve().parents[2] / "research" / "wf011" / "resultado.json"








def _nombre(k, train) -> str:
    t = "expansiva" if train in (None, "expansiva") else f"{train} d"
    return f"K={k} · train {t}"


def _configs(res: dict) -> dict[str, dict]:
    """Principal + variantes, con la misma forma para la tabla y los gráficos."""
    p = res["principal"]
    out = {_nombre(p["k"], p["train"]) + " (Avellaneda-Lee)": {
        "A": p["A"], "B": p["B"],
        "r2": sorted(a["r2_mediana"] for a in p["por_anio"])[len(p["por_anio"]) // 2],
    }}
    for v in res["variantes"]:
        out[_nombre(v["k"], v["train"])] = {"A": v["A"], "B": v["B"], "r2": v["r2_mediana"]}
    return out


def _tabla_configs(configs: dict[str, dict], h: str) -> pd.DataFrame:
    filas = []
    for nombre, c in configs.items():
        b, j = c["B"][h], c["B"]["juguete"]
        filas.append({
            "Configuración": nombre,
            "R² OOS (mediana)": c["r2"],
            "A: p<0.05 / esperadas": f"{c['A']['crudos']} / {c['A']['esperados']:.1f}",
            "A: tras BH": c["A"]["bh"],
            f"B: IC h={h}": b["pooled_ic"],
            "B: z vs nula": _z(b),
            "B: p": b["pooled_p"],
            "Sharpe bruto juguete": j["sharpe_bruto"],
            "p Sharpe": j["p"],
            "Breakeven (bps)": j["breakeven_bps"] if j["sharpe_bruto"] > 0 else None,
        })
    return pd.DataFrame(filas)










def _tabla_potencia(pot: dict, h: str) -> pd.DataFrame:
    filas = []
    for hl in (5, 10, 15, 20, 30, 60):
        fila = {"Half-life verdadera": f"{hl} d"}
        for w, etiqueta in ((1.0, "OU puro"), (0.5, "50 % OU"), (0.25, "25 % OU")):
            clave = f"{hl}_{w}"
            fila[f"A · {etiqueta}"] = pot["A"][clave]
            fila[f"B z · {etiqueta}"] = pot["B"][clave][h]
            fila[f"Sharpe · {etiqueta}"] = pot["B"][clave]["sharpe_bruto"]
        filas.append(fila)
    return pd.DataFrame(filas)


def _tabla_robustez(rob: dict) -> pd.DataFrame:
    filas = []
    for nombre, r in rob.items():
        for clave, etiqueta in (("tal_cual", "residuo tal cual"),
                                ("sin_mercado", "− promedio de mercado"),
                                ("sin_sector", "− promedio del sector")):
            filas.append({"Configuración": nombre, "Prueba": etiqueta,
                          "IC h=5": r[clave]["ic"], "z vs nula": r[clave]["z"],
                          "Sharpe bruto": r[clave]["sharpe_bruto"]})
        for m in r["mitades"]:
            filas.append({"Configuración": nombre, "Prueba": f"solo {m['desde']}–{m['hasta']}",
                          "IC h=5": None, "z vs nula": None,
                          "Sharpe bruto": m["sharpe_bruto"]})
    return pd.DataFrame(filas)


def main() -> None:
    st.set_page_config(page_title="botcito · walk-forward 011", page_icon="📈",
                       layout="wide")
    st.title("¿Revierten los residuos? — walk-forward")

    if not RESULTADO.exists():
        st.info(f"No existe `{RESULTADO}`.\n\n"
                "Correlo con `uv run python research/wf011/walk_forward.py` (~9 min).")
        return
    res = json.loads(RESULTADO.read_text())
    meta, principal = res["meta"], res["principal"]
    configs = _configs(res)
    jp = principal["B"]["juguete"]

    st.caption(
        f"SPEC-011 · {meta['n_tickers']} large caps de 11 sectores "
        f"(descartadas: {', '.join(meta['descartados']) or 'ninguna'}) · re-ajuste cada "
        f"1 de enero con datos anteriores · OOS {meta['oos'][0]} → {meta['oos'][1]} "
        f"({meta['oos'][2]:,} días) · s-score de {meta['ventana_s']} días · "
        f"{meta['n_perm']} permutaciones · generado {meta['fecha']}"
    )

    # --- Veredicto ------------------------------------------------------------
    st.error(
        "**Sin reversión operable.** Con la configuración de Avellaneda-Lee (K=5, "
        "re-ajuste sobre 252 días) el s-score no predice el residuo: IC igual a la nula "
        "y Sharpe bruto negativo, con una prueba que tenía potencia de sobra para verlo. "
        "La única variante con algo (ventana expansiva) es chica, se eligió entre 28 "
        "combinaciones y decae en el tiempo."
    )
    b5 = principal["B"]["5"]
    pot = res["potencia"]["B"]["15_0.25"]
    tiles = st.columns(4)
    tiles[0].metric("Días fuera de muestra", f"{meta['oos'][2]:,}",
                    help="vs 449 del diagnóstico del 2026-10-17")
    tiles[1].metric("Acciones con reversión tras BH", f"{principal['A']['bh']} / "
                    f"{meta['n_tickers']}")
    tiles[2].metric("IC a 5 días, z vs nula", f"{_z(b5):+.1f}",
                    help="Negativo = reversión. |z| > 2 sería señal.")
    tiles[3].metric("Sharpe bruto (juguete)", f"{jp['sharpe_bruto']:+.2f}",
                    help="Sin costos ni cobertura de factores. No es un backtest.")
    st.caption(
        f"Escala: un universo donde el residuo fuera apenas 25 % OU (half-life 15 d) + "
        f"75 % camino aleatorio daría z ≈ {pot['5']:.0f} y Sharpe bruto ≈ "
        f"{pot['sharpe_bruto']:.1f}. Benchmark de ADR-0005: 1.57 neto."
    )

    # --- Configuraciones -----------------------------------------------------
    st.subheader("Todas las configuraciones")
    h = st.radio("Horizonte del IC (días)", HORIZONTES, index=1, horizontal=True)
    st.dataframe(
        _tabla_configs(configs, h), hide_index=True, width="stretch",
        column_config={
            "R² OOS (mediana)": st.column_config.NumberColumn(format="%.2f"),
            f"B: IC h={h}": st.column_config.NumberColumn(format="%.4f"),
            "B: z vs nula": st.column_config.NumberColumn(format="%+.1f"),
            "B: p": st.column_config.NumberColumn(format="%.3f"),
            "Sharpe bruto juguete": st.column_config.NumberColumn(format="%+.2f"),
            "p Sharpe": st.column_config.NumberColumn(format="%.3f"),
            "Breakeven (bps)": st.column_config.NumberColumn(format="%.1f"),
        },
    )
    st.caption(
        "**A**: pendiente de reversión del residuo acumulado por acción, contra "
        "permutación, con BH. **B**: correlación entre el s-score de hoy y el residuo "
        "acumulado de los próximos h días, promediada sobre el universo; nula con la "
        "misma permutación de fechas para todas las acciones (conserva la correlación "
        "cruzada). **Juguete**: peso −s normalizado, cobra el residuo del día siguiente; "
        "breakeven = costo por unidad negociada que lo deja en cero. Las variantes usan "
        f"{meta['n_perm_variantes']} permutaciones (p mínimo ≈ "
        f"{1 / (meta['n_perm_variantes'] + 1):.3f})."
    )

    # --- Por año ---------------------------------------------------------------
    st.subheader("Año por año")
    nombres = list(configs)
    elegida = st.selectbox("Configuración", nombres, index=0)
    b = configs[elegida]["B"][h]
    izq, der = st.columns(2)
    izq.plotly_chart(_figura_ic_anual(b, f"IC a {h} días por año — {elegida}"),
                     width="stretch", theme="streamlit")
    der.markdown(
        f"**{b['anios_bajo_nula']} de {len(b['por_anio'])} años** por debajo de su nula · "
        f"IC anual medio {b['anual_ic']:.4f} vs nula {b['anual_null_media']:.4f} "
        f"(z {_z(b, 'anual'):+.1f}, p {b['anual_p']:.3f})\n\n"
        "Dentro de cada año hay una reversión débil pero real en **todas** las "
        "configuraciones. No se puede operar: medirla así resta la media del año, que "
        "solo se conoce al final. Sobre la muestra completa la anula un drift persistente "
        "del residuo, y por eso el IC operable (tabla de arriba) es nulo con train 252.\n\n"
        "Ojo con la banda gris: la nula de un año **no está en 0** (≈ "
        f"{b['por_anio'][0]['null_media']:.3f}). Comparar el IC anual contra cero "
        "inventa una señal que no existe."
    )

    # --- Curvas ----------------------------------------------------------------
    st.subheader("Señal de juguete: retorno bruto acumulado")
    rob = res["robustez"]
    c1, c2 = st.columns(2)
    c1.plotly_chart(_figura_curva(rob["principal"]["curva"],
                                  "K=5 · train 252 d (Avellaneda-Lee)"),
                    width="stretch", theme="streamlit")
    c2.plotly_chart(_figura_curva(rob["expansiva"]["curva"], "K=5 · train expansiva"),
                    width="stretch", theme="streamlit")
    st.caption("Exposición bruta 1, sin costos, sin cobertura real de los factores. "
               "Sirve para ver forma y estabilidad, no para estimar rentabilidad.")

    # --- Robustez de la variante expansiva -----------------------------------
    st.subheader("¿Qué es la señal de la ventana expansiva?")
    izq, der = st.columns([3, 2])
    izq.dataframe(
        _tabla_robustez({"K=5 · train 252 d": rob["principal"],
                         "K=5 · expansiva": rob["expansiva"]}),
        hide_index=True, width="stretch",
        column_config={
            "IC h=5": st.column_config.NumberColumn(format="%.4f"),
            "z vs nula": st.column_config.NumberColumn(format="%+.1f"),
            "Sharpe bruto": st.column_config.NumberColumn(format="%+.2f"),
        },
    )
    izq.caption("Quitar el promedio de mercado o de sector no la mueve: no es un factor "
                "común que se coló en el residuo. Pero cae a menos de la mitad en la "
                "segunda mitad del período.")
    der.plotly_chart(_figura_sectores(rob["expansiva"]["ic5_por_sector"],
                                      "Por sector (expansiva)"),
                     width="stretch", theme="streamlit")

    # --- Por acción ----------------------------------------------------------
    st.subheader("Por acción (test A)")
    a = principal["A"]
    izq, der = st.columns([3, 2])
    izq.plotly_chart(figura_pvalues(a, "Test A: p-value de cada acción (2,713 días OOS)"),
                     width="stretch", theme="streamlit")
    der.markdown(
        f"**{a['crudos']}** acciones con p < 0.05 contra **{a['esperados']:.1f}** "
        f"esperadas por azar; **{a['bh']}** debajo de la recta de BH.\n\n"
        "Este test no tiene potencia para el caso realista: detecta un residuo 50 % OU "
        "solo 10–20 % de las veces (tabla de potencia). **Para SPEC-012 el screening "
        "por acción no sirve; el test agregado sí.**"
    )

    # --- Potencia ------------------------------------------------------------
    with st.expander("Potencia: qué habría visto cada test si hubiera reversión"):
        st.dataframe(
            _tabla_potencia(res["potencia"], h), hide_index=True, width="stretch",
            column_config={
                **{c: st.column_config.NumberColumn(format="%.0f%%")
                   for c in ("A · OU puro", "A · 50 % OU", "A · 25 % OU")},
                **{c: st.column_config.NumberColumn(format="%+.1f")
                   for c in ("B z · OU puro", "B z · 50 % OU", "B z · 25 % OU")},
                **{c: st.column_config.NumberColumn(format="%.1f")
                   for c in ("Sharpe · OU puro", "Sharpe · 50 % OU", "Sharpe · 25 % OU")},
            },
        )
        st.caption(
            f"Datos sintéticos del mismo largo ({meta['oos'][2]:,} días). **A**: fracción "
            f"de {meta['n_sim']} simulaciones con p < 0.05. **B**: z del IC agregado de un "
            f"universo de {meta['n_tickers']} acciones con esa mezcla, contra la nula real "
            f"(observado: {_z(b5):+.1f} a 5 días). La mezcla es ε = Δ(OU + camino "
            "aleatorio), con el % indicando la parte de la varianza de las innovaciones "
            "que va al OU."
        )

    # --- Siguientes pasos ----------------------------------------------------
    st.subheader("Siguientes pasos")
    st.markdown(
        "1. **Decidir si se cierra la línea de residuos en este universo** (dueño del "
        "modelado). Es lo que dice la evidencia de esta página.\n"
        "2. Si se le da una última oportunidad, **pre-registrar** antes de mirar: una "
        "sola configuración (ETFs sectoriales como factores, o universo de cientos de "
        "acciones), test B con nula conjunta, umbral de decisión fijado de antemano.\n"
        "3. Pase lo que pase, **SPEC-012** usa el test agregado con nula conjunta, no "
        "half-life en rango ni p-values por acción.\n"
        "4. Trabajo que sirve con cualquier técnica: **SPEC-005 → SPEC-004** (PnL y "
        "Sharpe bien calculados), SPEC-001, y `/spec-verify 002` y `009`."
    )


if __name__ == "__main__":
    main()
