"""
Universo ampliado (S&P 500) con factores PCA y por ETF sectorial — lector puro de
`research/wf_universo/resultado.json` (ADR-0004: esta página no calcula nada).

El experimento está pre-registrado en `research/wf_universo/PREREGISTRO.md`: H1 (PCA
K=15) y H2 (ETF sectorial) son las únicas configuraciones que deciden.

Uso:  uv run streamlit run app/dashboard.py   → página "universo ampliado"
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import wf_comun as C  # noqa: E402

RAIZ = Path(__file__).resolve().parents[2]
RESULTADO = RAIZ / "research" / "wf_universo" / "resultado.json"
RESULTADO_96 = RAIZ / "research" / "wf011" / "resultado.json"

NOMBRE_CRITERIO = {"p_ic5": "p del IC a 5 días", "sharpe_bruto": "Sharpe bruto (juguete)",
                   "breakeven_bps": "Breakeven (bps)"}


def _fila(nombre: str, ev: dict, h: str, universo: str) -> dict:
    b, j = ev["B"][h], ev["B"]["juguete"]
    return {
        "Universo": universo,
        "Configuración": nombre,
        "N": ev.get("n_tickers"),
        "R² OOS": ev.get("r2_mediana"),
        "A: p<0.05 / esp.": f"{ev['A']['crudos']} / {ev['A']['esperados']:.1f}",
        "A: tras BH": ev["A"]["bh"],
        f"IC h={h}": b["pooled_ic"],
        "z vs nula": C.z(b),
        "p": b["pooled_p"],
        "Sharpe bruto": j["sharpe_bruto"],
        "Breakeven (bps)": j["breakeven_bps"] if j["sharpe_bruto"] > 0 else None,
    }


FORMATO = {
    "R² OOS": st.column_config.NumberColumn(format="%.2f"),
    "z vs nula": st.column_config.NumberColumn(format="%+.1f"),
    "p": st.column_config.NumberColumn(format="%.3f"),
    "Sharpe bruto": st.column_config.NumberColumn(format="%+.2f"),
    "Breakeven (bps)": st.column_config.NumberColumn(format="%.1f"),
}


def _criterios(decision: dict) -> pd.DataFrame:
    return pd.DataFrame([
        {"Criterio": NOMBRE_CRITERIO[k], "Valor": c["valor"], "Umbral": c["umbral"],
         "Cumple": "✅ sí" if c["cumple"] else "❌ no"}
        for k, c in decision["criterios"].items()
    ])


def _robustez(rob: dict) -> pd.DataFrame:
    filas = [{"Prueba": etiqueta, "IC h=5": rob[clave]["ic"], "z vs nula": rob[clave]["z"],
              "Sharpe bruto": rob[clave]["sharpe_bruto"]}
             for clave, etiqueta in (("tal_cual", "residuo tal cual"),
                                     ("sin_mercado", "− promedio de mercado"),
                                     ("sin_sector", "− promedio del sector"))]
    filas += [{"Prueba": f"solo {m['desde']}–{m['hasta']}", "IC h=5": None,
               "z vs nula": None, "Sharpe bruto": m["sharpe_bruto"]} for m in rob["mitades"]]
    return pd.DataFrame(filas)


def _segmento(clave: str, prim: dict, secundarias: list[dict], h: str, n: int) -> None:
    """Una familia de factores: tabla, año por año, curva, robustez y por acción."""
    filas = [_fila(prim["nombre"] + f" ({clave}, primaria)", prim, h, f"S&P 500 ({n})")]
    filas += [_fila(s["nombre"], s, h, "96 large caps" if s["nombre"].startswith("Universo 96")
                    else f"S&P 500 ({n})") for s in secundarias]
    st.dataframe(pd.DataFrame(filas), hide_index=True, width="stretch",
                 column_config={**FORMATO, f"IC h={h}": st.column_config.NumberColumn(
                     format="%.4f")})

    b = prim["B"][h]
    izq, der = st.columns(2)
    izq.plotly_chart(C.figura_ic_anual(b, f"IC a {h} días por año — {prim['nombre']}"),
                     width="stretch", theme="streamlit")
    der.plotly_chart(C.figura_curva(prim["robustez"]["curva"],
                                    f"Señal de juguete, acumulado bruto — {clave}"),
                     width="stretch", theme="streamlit")
    st.caption(f"{b['anios_bajo_nula']} de {len(b['por_anio'])} años por debajo de su nula "
               f"(z del IC anual medio {C.z(b, 'anual'):+.1f}). La curva es bruta, con "
               "exposición 1, sin costos ni cobertura real: forma y estabilidad, no "
               "rentabilidad.")

    izq, der = st.columns([3, 2])
    izq.markdown("**Robustez**")
    izq.dataframe(_robustez(prim["robustez"]), hide_index=True, width="stretch",
                  column_config={"IC h=5": st.column_config.NumberColumn(format="%.4f"),
                                 **FORMATO})
    izq.plotly_chart(C.figura_pvalues(prim["A"], "Test A: p-value por acción"),
                     width="stretch", theme="streamlit")
    der.plotly_chart(C.figura_sectores(prim["robustez"]["ic5_por_sector"], "Por sector"),
                     width="stretch", theme="streamlit")


def main() -> None:
    st.set_page_config(page_title="botcito · universo ampliado", page_icon="📈",
                       layout="wide")
    st.title("Universo ampliado: S&P 500, factores PCA y por ETF sectorial")

    if not RESULTADO.exists():
        st.info(f"No existe `{RESULTADO}`.\n\nCorrelo con "
                "`uv run python research/wf_universo/universo.py` (~40 min).")
        return
    res = json.loads(RESULTADO.read_text())
    meta, prim = res["meta"], res["primarias"]
    n = meta["n_tickers"]

    st.caption(
        f"{n} acciones del S&P 500 actual con historia desde 2014 (de {meta['pedidos']}; "
        f"{meta['descartados']} sin cobertura suficiente) · OOS {meta['oos'][0]} → "
        f"{meta['oos'][1]} ({meta['oos'][2]:,} días) · re-ajuste anual sobre 252 días · "
        f"{meta['n_perm']} permutaciones · pre-registro en `{meta['preregistro']}`"
    )

    # --- Decisión pre-registrada ---------------------------------------------
    u = meta["umbrales"]
    regla = (f"p < {u['p']} en el IC a 5 días, Sharpe bruto ≥ {u['sharpe']} y breakeven ≥ "
             f"{u['breakeven_bps']} bps")
    if res["decision"]["alguna_pasa"]:
        pasan = [k for k, p in prim.items() if p["decision"]["pasa"]]
        st.success(f"**Pasa el pre-registro: {', '.join(pasan)}.** Cumple {regla}. "
                   "Siguiente paso: SPEC-012/013 con esa configuración.")
    else:
        st.error(f"**Ninguna hipótesis pasa el pre-registro** ({regla}). Por la regla "
                 "fijada antes de correr: se cierra la línea de residuos para acciones de "
                 "EE.UU. en daily.")

    cols = st.columns(2)
    for col, (clave, p) in zip(cols, prim.items(), strict=True):
        col.markdown(f"**{clave} · {p['nombre']}**")
        col.dataframe(_criterios(p["decision"]), hide_index=True, width="stretch",
                      column_config={"Valor": st.column_config.NumberColumn(format="%.3f")})

    # --- Segmentos -----------------------------------------------------------
    h = st.radio("Horizonte del IC (días)", C.HORIZONTES, index=1, horizontal=True)
    sec = res["secundarias"]
    tab_pca, tab_etf, tab_cmp = st.tabs(["Factores PCA", "Factores ETF sectorial",
                                         "Comparación con el universo de 96"])
    with tab_pca:
        _segmento("H1", prim["H1"], [s for s in sec if s["nombre"].startswith("PCA")], h, n)
    with tab_etf:
        st.caption("Cada acción contra el ETF de su sector: "
                   + ", ".join(f"{s} → {e}" for s, e in meta["etf_de_sector"].items())
                   + ". IYR y VOX en lugar de XLRE y XLC porque estos nacen en 2015 y 2018.")
        _segmento("H2", prim["H2"], [s for s in sec if "ETF" in s["nombre"]], h, n)
    with tab_cmp:
        filas = [_fila(p["nombre"], p, h, f"S&P 500 ({n})") for p in prim.values()]
        filas += [_fila(s["nombre"], s, h, "96 large caps" if s["nombre"].startswith(
            "Universo 96") else f"S&P 500 ({n})") for s in sec]
        if RESULTADO_96.exists():
            r96 = json.loads(RESULTADO_96.read_text())
            p96 = r96["principal"]
            filas.insert(0, _fila("PCA K=5 · train 252 d (wf011)",
                                  {**p96, "n_tickers": r96["meta"]["n_tickers"],
                                   "r2_mediana": None}, h, "96 large caps"))
        st.dataframe(pd.DataFrame(filas), hide_index=True, width="stretch",
                     column_config={**FORMATO, f"IC h={h}": st.column_config.NumberColumn(
                         format="%.4f")})
        st.caption("Si la falta de señal en wf011 fuera por N chico, debería aparecer al "
                   "pasar de 96 a ~455 acciones con la misma prueba.")

    # --- Potencia --------------------------------------------------------------
    with st.expander("Potencia del test agregado con este N"):
        filas = [{"Half-life": f"{k.split('_')[0]} d",
                  "% de la varianza que es OU": f"{float(k.split('_')[1]):.0%}",
                  "z esperado (h=5)": v["z5"], "Sharpe bruto esperado": v["sharpe_bruto"]}
                 for k, v in res["potencia"].items()]
        st.dataframe(pd.DataFrame(filas), hide_index=True, width="stretch",
                     column_config={
                         "z esperado (h=5)": st.column_config.NumberColumn(format="%+.1f"),
                         "Sharpe bruto esperado": st.column_config.NumberColumn(
                             format="%.2f")})
        st.caption(f"Universo sintético de {n} acciones con residuo = OU + camino "
                   "aleatorio, comparado contra la nula real de H1. Observado en H1: "
                   f"z {C.z(prim['H1']['B']['5']):+.1f}, Sharpe "
                   f"{prim['H1']['B']['juguete']['sharpe_bruto']:+.2f}.")

    # --- Metodología -------------------------------------------------------------
    with st.expander("Metodología"):
        st.markdown(
            "- **Walk-forward anual:** cada 1 de enero se ajusta el modelo con los 252 "
            "días hábiles anteriores y se proyecta el año siguiente sin re-estimar. Los "
            "residuos de todos los años se concatenan: ~11 años fuera de muestra.\n"
            "- **Residuo:** retorno de la acción menos lo que explican los factores "
            "(PCA sobre la correlación: eigenportafolios; o el ETF del sector). Se acumula "
            "y se calcula el **s-score** = z-score rolling causal de 60 días "
            "(`compute_sscore`, la misma función que usaría el live).\n"
            "- **Test B (decide):** correlación entre el s-score de hoy y el residuo de "
            "los próximos h días, promediada sobre acciones. Reversión ⇒ negativa. Nula: "
            "barajar las fechas **con la misma permutación para todas las acciones**, que "
            "destruye la dependencia temporal pero conserva la correlación entre acciones.\n"
            "- **Test A (descriptivo):** por acción, pendiente de reversión del residuo "
            "acumulado contra permutación, con Benjamini-Hochberg.\n"
            "- **Señal de juguete:** peso −s normalizado a exposición 1, cobra el residuo "
            "del día siguiente. Sin costos ni cobertura: traduce el IC a Sharpe bruto y a "
            "un breakeven de costos. **No es un backtest** (eso es SPEC-013).\n"
            "- **Sesgos declarados:** supervivencia (S&P 500 de hoy), costos ausentes, "
            "beta del ETF anual y no en ventanas de 60 días como en el paper."
        )


if __name__ == "__main__":
    main()
