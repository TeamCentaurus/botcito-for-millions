"""
Walk-forward sobre el S&P 500 con dos familias de factores: PCA y ETF sectorial.

Ejecuta lo que fija `PREREGISTRO.md` (escrito antes de correr esto): H1 = PCA K=15,
H2 = ETF del sector, ambos con re-ajuste anual sobre 252 días; IC agregado a 5 días
contra nula de permutación conjunta, p < 0.025, Sharpe bruto de juguete ≥ 1.0 y
breakeven ≥ 5 bps. Todo lo demás es descriptivo.

Reusa los tests de `research/wf011/walk_forward.py` para que los números sean
comparables con el universo de 96.

    uv run python research/wf_universo/universo.py              # ~30 min
    uv run python research/wf_universo/universo.py --rapido

Precios en data/ (gitignored). Resultado en research/wf_universo/resultado.json.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

from botcito_core.data_loader import load_yfinance

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI.parent / "wf011"))
import walk_forward as W  # noqa: E402

RAIZ = AQUI.parents[1]
CACHE_ACCIONES = RAIZ / "data" / "wfu_precios_sp500.parquet"
CACHE_ETF = RAIZ / "data" / "wfu_precios_etf.parquet"
CONSTITUYENTES = AQUI / "sp500_constituyentes.csv"
SALIDA = AQUI / "resultado.json"

ETF_GICS = {
    "Information Technology": "XLK", "Financials": "XLF", "Energy": "XLE",
    "Health Care": "XLV", "Industrials": "XLI", "Consumer Staples": "XLP",
    "Consumer Discretionary": "XLY", "Utilities": "XLU", "Materials": "XLB",
    "Real Estate": "IYR", "Communication Services": "VOX",
}
ETF_SECTOR_96 = {
    "Tecnología": "XLK", "Financiero": "XLF", "Energía": "XLE", "Salud": "XLV",
    "Industrial": "XLI", "Consumo básico": "XLP", "Consumo discrecional": "XLY",
    "Utilities": "XLU", "Materiales": "XLB", "Inmobiliario": "IYR", "Comunicaciones": "VOX",
}
ETFS = sorted(set(ETF_GICS.values())) + ["SPY"]

# Umbrales del pre-registro
P_MAX, SHARPE_MIN, BREAKEVEN_MIN = 0.025, 1.0, 5.0


# --------------------------------------------------------------------------- datos

def _precios(cache: Path, tickers: list[str]) -> pd.DataFrame:
    if cache.exists():
        return pd.read_parquet(cache)
    precios = load_yfinance(tickers, start=W.INICIO, end=W.FIN, min_coverage=0.95)
    cache.parent.mkdir(exist_ok=True)
    precios.to_parquet(cache)
    return precios


def cargar() -> tuple[pd.DataFrame, pd.DataFrame, dict[str, str]]:
    constituyentes = pd.read_csv(CONSTITUYENTES)
    sector_de = dict(zip(constituyentes.ticker, constituyentes.sector, strict=True))
    acciones = _precios(CACHE_ACCIONES, sorted(sector_de))
    etf = _precios(CACHE_ETF, ETFS)
    fechas = acciones.index.intersection(etf.index)
    r = acciones.loc[fechas].pct_change().iloc[1:]
    f = etf.loc[fechas].pct_change().iloc[1:]
    return r, f, {t: sector_de[t] for t in r.columns}


# ------------------------------------------------------------ walk-forward con ETF

def walk_forward_etf(returns: pd.DataFrame, etf: pd.DataFrame, etf_de: dict[str, str],
                     train: int | None, con_spy: bool = False) -> dict:
    """
    Igual que `W.walk_forward` pero el factor de cada acción es el ETF de su sector
    (+ SPY si `con_spy`): εᵢ = Rᵢ − αᵢ − βᵢ·ETF (− γᵢ·SPY). OLS sobre el pasado,
    proyección sobre el año; los parámetros no se re-estiman fuera de muestra.
    """
    anios = sorted(set(returns.index.year))
    eps, por_anio = [], []
    for anio in anios:
        pasado = returns.index.year < anio
        if pasado.sum() < 252:
            continue
        idx_train = np.nonzero(pasado)[0]
        if train is not None:
            idx_train = idx_train[-train:]
        futuro = returns.index.year == anio
        e = pd.DataFrame(index=returns.index[futuro], columns=returns.columns, dtype=float)
        for codigo in sorted(set(etf_de.values())):
            cols = [t for t in returns.columns if etf_de[t] == codigo]
            if not cols:
                continue
            fac = [codigo, "SPY"] if con_spy else [codigo]
            X = np.column_stack([np.ones(len(idx_train)), etf[fac].to_numpy()[idx_train]])
            Y = returns[cols].to_numpy()[idx_train]
            coefs, *_ = np.linalg.lstsq(X, Y, rcond=None)
            Xf = np.column_stack([np.ones(futuro.sum()), etf[fac].to_numpy()[futuro]])
            e[cols] = returns[cols].to_numpy()[futuro] - Xf @ coefs
        r2 = 1 - e.var() / returns[futuro].var()
        eps.append(e)
        por_anio.append({"anio": int(anio), "n": int(futuro.sum()),
                         "r2_mediana": float(r2.median())})
    return {"eps": pd.concat(eps), "por_anio": por_anio}


def walk_forward_pca(returns: pd.DataFrame, k: int, train: int | None) -> dict:
    return W.walk_forward(returns, k=k, train=train)


# ------------------------------------------------------------------- evaluación

def evaluar(wf: dict, n_perm: int, rng, completo: bool) -> dict:
    eps = wf["eps"]
    a = W.test_pendiente(eps, n_perm, rng)
    b = W.test_predictivo(eps, n_perm, rng)
    r2 = float(np.median([x["r2_mediana"] for x in wf["por_anio"]]))
    if not completo:
        a = {x: a[x] for x in ("crudos", "esperados", "bh", "rechazados")}
        b = {h: ({x: v for x, v in b[h].items() if x not in ("ic_tickers", "p_tickers")}
                 if h != "juguete" else b[h]) for h in b}
    return {"n_tickers": eps.shape[1], "r2_mediana": r2, "por_anio": wf["por_anio"],
            "A": a, "B": b}


def decidir(ev: dict) -> dict:
    b, j = ev["B"]["5"], ev["B"]["juguete"]
    criterios = {
        "p_ic5": {"valor": b["pooled_p"], "umbral": f"< {P_MAX}",
                  "cumple": b["pooled_p"] < P_MAX},
        "sharpe_bruto": {"valor": j["sharpe_bruto"], "umbral": f">= {SHARPE_MIN}",
                         "cumple": j["sharpe_bruto"] >= SHARPE_MIN},
        "breakeven_bps": {"valor": j["breakeven_bps"], "umbral": f">= {BREAKEVEN_MIN}",
                          "cumple": (j["breakeven_bps"] or -1) >= BREAKEVEN_MIN},
    }
    return {"criterios": criterios, "pasa": all(c["cumple"] for c in criterios.values())}


def potencia_b(T: int, n: int, anio: np.ndarray, null_b: dict, rng) -> dict:
    """z del IC agregado y Sharpe bruto si todas las acciones tuvieran esa mezcla."""
    out = {}
    for hl in (10, 15, 30):
        for w in (0.25, 0.1):
            U = W.simular(n, T, hl, w, rng)
            r = W._ics(U, anio, W.VENTANA_S)
            out[f"{hl}_{w}"] = {
                "z5": (r[5]["pooled"] - null_b["5"]["pooled_null_media"])
                / null_b["5"]["pooled_null_sd"],
                "sharpe_bruto": r["juguete"]["sharpe_bruto"],
            }
    return out


# -------------------------------------------------------------------------- main

def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--rapido", action="store_true")
    args = ap.parse_args()
    n_perm, n_perm_sec = (100, 50) if args.rapido else (1000, 300)
    rng = np.random.default_rng(20261018)
    t0 = time.time()

    r, etf, sector_de = cargar()
    etf_de = {t: ETF_GICS[s] for t, s in sector_de.items()}
    pedidos = len(pd.read_csv(CONSTITUYENTES))
    print(f"retornos {r.shape} {r.index[0].date()} → {r.index[-1].date()}")
    assert r.index[0] < pd.Timestamp("2015-01-01"), "el panel arranca tarde: no hay train 2016"

    sectores = pd.Series(sector_de).value_counts().to_dict()
    res = {"meta": {
        "fecha": "2026-10-18", "preregistro": "research/wf_universo/PREREGISTRO.md",
        "pedidos": pedidos, "n_tickers": r.shape[1], "descartados": pedidos - r.shape[1],
        "sectores": sectores, "etf_de_sector": ETF_GICS,
        "datos": [str(r.index[0].date()), str(r.index[-1].date())],
        "n_perm": n_perm, "n_perm_secundarias": n_perm_sec,
        "umbrales": {"p": P_MAX, "sharpe": SHARPE_MIN, "breakeven_bps": BREAKEVEN_MIN},
    }}

    # --- primarias -------------------------------------------------------------
    primarias = {
        "H1": ("PCA K=15 · train 252 d", lambda: walk_forward_pca(r, 15, 252)),
        "H2": ("ETF sectorial · train 252 d", lambda: walk_forward_etf(r, etf, etf_de, 252)),
    }
    res["primarias"] = {}
    for clave, (nombre, fn) in primarias.items():
        wf = fn()
        ev = evaluar(wf, n_perm, rng, completo=True)
        ev["nombre"] = nombre
        ev["decision"] = decidir(ev)
        ev["robustez"] = W.robustez(wf["eps"], n_perm_sec, rng, sector_de)
        res["primarias"][clave] = ev
        res["meta"]["oos"] = [str(wf["eps"].index[0].date()), str(wf["eps"].index[-1].date()),
                              len(wf["eps"])]
        print(f"{clave} {nombre}: pasa={ev['decision']['pasa']} ({time.time() - t0:.0f}s)")

    res["decision"] = {
        "alguna_pasa": any(p["decision"]["pasa"] for p in res["primarias"].values()),
        "regla": "si H1 o H2 cumple las tres condiciones se sigue a SPEC-012/013; "
                 "si no, se cierra la línea de residuos (daily, acciones EE.UU.)",
    }

    # --- secundarias -----------------------------------------------------------
    r96 = W.cargar_retornos()
    fechas96 = r96.index.intersection(etf.index)
    etf_de_96 = {t: ETF_SECTOR_96[W.SECTOR_DE[t]] for t in r96.columns}
    secundarias = [
        ("PCA K=5 · train 252 d", lambda: walk_forward_pca(r, 5, 252)),
        ("ETF sectorial + SPY · train 252 d",
         lambda: walk_forward_etf(r, etf, etf_de, 252, con_spy=True)),
        ("PCA K=15 · train expansiva", lambda: walk_forward_pca(r, 15, None)),
        ("ETF sectorial · train expansiva",
         lambda: walk_forward_etf(r, etf, etf_de, None)),
        ("Universo 96 · ETF sectorial · train 252 d",
         lambda: walk_forward_etf(r96.loc[fechas96], etf.loc[fechas96], etf_de_96, 252)),
    ]
    res["secundarias"] = []
    for nombre, fn in secundarias:
        ev = evaluar(fn(), n_perm_sec, rng, completo=False)
        ev["nombre"] = nombre
        res["secundarias"].append(ev)
        print(f"{nombre} ({time.time() - t0:.0f}s)")

    oos = res["primarias"]["H1"]
    anio = np.array([int(f[:4]) for f in oos["robustez"]["curva"]["fechas"]])
    anio = np.concatenate([[anio[0]], anio])
    res["potencia"] = potencia_b(len(anio), r.shape[1], anio, oos["B"], rng)
    print(f"potencia ({time.time() - t0:.0f}s)")

    SALIDA.write_text(json.dumps(res, ensure_ascii=False, indent=1))
    print(f"→ {SALIDA}")


if __name__ == "__main__":
    main()
