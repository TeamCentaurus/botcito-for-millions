"""
Walk-forward de SPEC-011 sobre datos reales: ¿revierten los residuos fuera de muestra?

Continuación del diagnóstico del 2026-10-17 (un solo corte train/test, 449 días OOS,
0 acciones tras BH, potencia ~10 % para reversión mezclada). Acá el modelo se re-ajusta
cada 1 de enero con datos estrictamente anteriores y se proyecta sobre el año
siguiente, así que se acumulan ~11 años de residuos fuera de muestra sin look-ahead.

Dos tests contra una nula de permutación (residuos barajados en el tiempo; para los
estadísticos agregados, con la MISMA permutación de fechas en todas las acciones):

  A. Por acción, pendiente de reversión del residuo acumulado sobre todo el OOS
     (ΔX = a + b·X₋₁), igual al diagnóstico anterior → p-value, BH sobre el universo.
  B. Predictivo: correlación (IC) entre el s-score causal en t (z-score rolling de 60
     días del residuo acumulado, vía `compute_sscore`) y el residuo acumulado de
     t+1..t+h. Si hay reversión operable en 5–30 días, el IC es NEGATIVO. Es la
     pregunta que importa para la señal, y agregada sobre el universo tiene mucha más
     potencia que A.

Uso (desde la raíz del repo):

    uv run python research/wf011/walk_forward.py              # corrida completa
    uv run python research/wf011/walk_forward.py --rapido     # menos permutaciones

Precios cacheados en data/ (gitignored). Resultado en research/wf011/resultado.json.
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import numpy as np
import pandas as pd

from botcito_core.data_loader import load_yfinance
from botcito_core.factor_model import (
    compute_residuals,
    compute_sscore,
    cumulative_residual,
    fit_factor_model,
)

RAIZ = Path(__file__).resolve().parents[2]
CACHE = RAIZ / "data" / "wf011_precios.parquet"
SALIDA = Path(__file__).resolve().parent / "resultado.json"

# Mismo universo que el diagnóstico del 2026-10-17 (97 pedidos, MMC se descartó)
SECTORES = {
    "Tecnología": ["AAPL", "ADBE", "CSCO", "GOOGL", "IBM", "INTC", "MSFT", "ORCL", "QCOM", "TXN"],
    "Salud": ["ABT", "AMGN", "BMY", "CVS", "DHR", "GILD", "JNJ", "LLY", "MDT", "MRK", "PFE",
              "TMO", "UNH"],
    "Financiero": ["AXP", "BAC", "BLK", "C", "CB", "GS", "JPM", "MMC", "MS", "PNC", "SCHW",
                   "USB", "WFC"],
    "Energía": ["COP", "CVX", "EOG", "OXY", "PSX", "SLB", "VLO", "XOM"],
    "Industrial": ["BA", "CAT", "DE", "EMR", "GE", "HON", "ITW", "LMT", "MMM", "RTX", "UNP",
                   "UPS"],
    "Consumo básico": ["CL", "COST", "GIS", "KMB", "KO", "MDLZ", "MO", "PEP", "PG", "PM", "WMT"],
    "Consumo discrecional": ["AMZN", "BKNG", "HD", "LOW", "MCD", "NKE", "SBUX", "TJX"],
    "Utilities": ["AEP", "D", "DUK", "EXC", "NEE", "SO"],
    "Materiales": ["APD", "DD", "ECL", "FCX", "LIN", "NEM", "SHW"],
    "Inmobiliario": ["AMT", "O", "PLD", "PSA", "SPG"],
    "Comunicaciones": ["CMCSA", "DIS", "T", "VZ"],
}
TICKERS = sorted(t for ts in SECTORES.values() for t in ts)
SECTOR_DE = {t: s for s, ts in SECTORES.items() for t in ts}

INICIO, FIN = "2014-01-01", "2026-10-17"
VENTANA_S = 60            # ventana del s-score (Avellaneda-Lee)
HORIZONTES = (1, 5, 10, 20)
ALPHA = 0.05


# --------------------------------------------------------------------------- datos

def cargar_retornos() -> pd.DataFrame:
    if CACHE.exists():
        precios = pd.read_parquet(CACHE)
    else:
        precios = load_yfinance(TICKERS, start=INICIO, end=FIN, min_coverage=0.95)
        CACHE.parent.mkdir(exist_ok=True)
        precios.to_parquet(CACHE)
    return precios.pct_change().iloc[1:]


# ------------------------------------------------------------------- walk-forward

def walk_forward(returns: pd.DataFrame, k: int, train: int | None) -> dict:
    """
    Re-ajusta el 1 de enero de cada año con datos ANTERIORES y proyecta el año.
    `train=None` → ventana expansiva; si no, las últimas `train` observaciones.
    """
    anios = sorted(set(returns.index.year))
    eps, por_anio = [], []
    for anio in anios:
        pasado = returns[returns.index.year < anio]
        if train is not None:
            if len(pasado) < train:
                continue
            pasado = pasado.iloc[-train:]
        elif len(pasado) < 252:
            continue
        futuro = returns[returns.index.year == anio]
        modelo = fit_factor_model(pasado, n_factors=k)
        e = compute_residuals(modelo, futuro)
        r2 = 1 - e.var() / futuro.var()
        eps.append(e)
        por_anio.append({
            "anio": int(anio), "n": len(futuro), "train_end": modelo.train_end,
            "evr": [float(x) for x in modelo.explained_variance_ratio],
            "r2_mediana": float(r2.median()),
        })
    return {"eps": pd.concat(eps), "por_anio": por_anio}


# ------------------------------------------------------------------------ tests

def bh(p: np.ndarray, q: float = ALPHA) -> np.ndarray:
    """Máscara de rechazos de Benjamini-Hochberg."""
    n = len(p)
    orden = np.argsort(p)
    umbral = q * np.arange(1, n + 1) / n
    pasa = p[orden] <= umbral
    rechazo = np.zeros(n, dtype=bool)
    if pasa.any():
        rechazo[orden[: np.max(np.nonzero(pasa)) + 1]] = True
    return rechazo


def pendiente(eps: np.ndarray) -> np.ndarray:
    """b de ΔX = a + b·X₋₁ con X = cumsum(ε). `eps` (..., T) → (...)."""
    x = np.cumsum(eps, axis=-1)[..., :-1]
    d = eps[..., 1:]
    xc = x - x.mean(axis=-1, keepdims=True)
    dc = d - d.mean(axis=-1, keepdims=True)
    return (xc * dc).sum(-1) / (xc * xc).sum(-1)


def barajar(a: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    """Permuta cada columna de (T, N) de forma independiente."""
    idx = np.argsort(rng.random(a.shape), axis=0)
    return np.take_along_axis(a, idx, axis=0)


def barajar_conjunto(a: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    """
    Misma permutación de fechas para todas las columnas: destruye la dependencia
    serial pero conserva la correlación contemporánea entre acciones. Es la nula
    correcta para estadísticos AGREGADOS sobre el universo; barajar cada columna por
    separado la subestima, porque los residuos siguen correlacionados entre sí.
    """
    return a[rng.permutation(len(a))]


def test_pendiente(eps: pd.DataFrame, n_perm: int, rng) -> dict:
    E = eps.to_numpy().T                                    # (N, T)
    b = pendiente(E)
    menores = np.zeros(len(b))
    for _ in range(n_perm):
        menores += pendiente(barajar(E.T, rng).T) <= b
    p = (1 + menores) / (1 + n_perm)
    rech = bh(p)
    hl = np.where(b < 0, -np.log(2) / np.where(b < 0, b, -1), np.inf)
    return {
        "tickers": list(eps.columns), "b": b.tolist(), "p": p.tolist(),
        "hl": [None if not np.isfinite(h) else float(h) for h in hl],
        "crudos": int((p < ALPHA).sum()), "esperados": ALPHA * len(p),
        "bh": int(rech.sum()),
        "rechazados": [t for t, r in zip(eps.columns, rech, strict=True) if r],
    }


def _sscore_rapido(X: np.ndarray, w: int) -> np.ndarray:
    """Misma cuenta que `compute_sscore` (rolling mean/std ddof=1) sin el loop por columna."""
    df = pd.DataFrame(X)
    r = df.rolling(w)
    return ((df - r.mean()) / r.std()).to_numpy()


def _forward(E: np.ndarray, h: int) -> np.ndarray:
    """Σ ε(t+1..t+h), NaN al final."""
    c = np.vstack([np.zeros((1, E.shape[1])), np.cumsum(E, axis=0)])
    f = np.full(E.shape, np.nan)
    f[: len(E) - h] = c[h + 1:] - c[1: len(E) - h + 1]
    return f


def _ic_por_columna(s: np.ndarray, f: np.ndarray) -> np.ndarray:
    m = ~(np.isnan(s) | np.isnan(f))
    n = m.sum(0)
    s0, f0 = np.where(m, s, 0.0), np.where(m, f, 0.0)
    ms, mf = s0.sum(0) / n, f0.sum(0) / n
    cs, cf = np.where(m, s - ms, 0.0), np.where(m, f - mf, 0.0)
    return (cs * cf).sum(0) / np.sqrt((cs * cs).sum(0) * (cf * cf).sum(0))


def _ics(E: np.ndarray, anio: np.ndarray, w: int) -> dict:
    s = _sscore_rapido(np.cumsum(E, axis=0), w)
    out = {}
    for h in HORIZONTES:
        f = _forward(E, h)
        ic = _ic_por_columna(s, f)
        por_anio = {int(a): float(np.nanmean(_ic_por_columna(s[anio == a], f[anio == a])))
                    for a in np.unique(anio)}
        out[h] = {"ic": ic, "pooled": float(np.nanmean(ic)), "por_anio": por_anio}
    out["juguete"] = _juguete(s, E)
    return out


def _pnl_juguete(s: np.ndarray, E: np.ndarray):
    """Pesos (T, N), PnL de t+1 por cada t (T−1,) y máscara de días con posición."""
    w = -np.nan_to_num(s)
    bruto = np.abs(w).sum(1, keepdims=True)
    w = np.divide(w, bruto, out=np.zeros_like(w), where=bruto > 0)
    return w, (w[:-1] * E[1:]).sum(1), bruto[:-1, 0] > 0


def _juguete(s: np.ndarray, E: np.ndarray) -> dict:
    """
    Señal contraria de juguete en espacio de residuos: peso −s(t) normalizado a
    exposición bruta 1, cobra ε(t+1). SIN costos, SIN cobertura real de factores:
    NO es un backtest (eso es SPEC-013). Sirve para traducir el IC a un Sharpe bruto
    y a un breakeven de costos por unidad negociada.
    """
    w, pnl, activo = _pnl_juguete(s, E)
    pnl = pnl[activo]
    giro = np.abs(np.diff(w, axis=0)).sum(1)[VENTANA_S:].mean()
    sharpe = pnl.mean() / pnl.std(ddof=1) * np.sqrt(252)
    return {"sharpe_bruto": float(sharpe), "ret_diario_bps": float(pnl.mean() * 1e4),
            "giro_diario": float(giro),
            "breakeven_bps": float(pnl.mean() / giro * 1e4) if giro > 0 else None}


def test_predictivo(eps: pd.DataFrame, n_perm: int, rng, w: int = VENTANA_S) -> dict:
    # el s-score real sale de la función de producción; la versión rápida se usa
    # para las permutaciones y se verifica igual a ella acá mismo
    real_s = compute_sscore(cumulative_residual(eps), window=w).to_numpy()
    E = eps.to_numpy()
    assert np.allclose(real_s, _sscore_rapido(np.cumsum(E, axis=0), w), equal_nan=True)

    anio = eps.index.year.to_numpy()
    real = _ics(E, anio, w)
    nula = {h: {"ic": [], "pooled": [], "por_anio": []} for h in HORIZONTES}
    sharpe_null = []
    for _ in range(n_perm):
        r = _ics(barajar_conjunto(E, rng), anio, w)
        sharpe_null.append(r["juguete"]["sharpe_bruto"])
        for h in HORIZONTES:
            nula[h]["ic"].append(r[h]["ic"])
            nula[h]["pooled"].append(r[h]["pooled"])
            nula[h]["por_anio"].append([r[h]["por_anio"][a] for a in sorted(r[h]["por_anio"])])

    sharpe_null = np.array(sharpe_null)
    out = {"juguete": {**real["juguete"],
                       "sharpe_null_media": float(sharpe_null.mean()),
                       "sharpe_null_sd": float(sharpe_null.std(ddof=1)),
                       "p": float((1 + (sharpe_null >= real["juguete"]["sharpe_bruto"]).sum())
                                  / (1 + n_perm))}}
    for h in HORIZONTES:
        ic_null = np.array(nula[h]["ic"])                   # (P, N)
        p_tk = (1 + (ic_null <= real[h]["ic"]).sum(0)) / (1 + n_perm)
        pooled_null = np.array(nula[h]["pooled"])
        anio_null = np.array(nula[h]["por_anio"])           # (P, años)
        anios = sorted(real[h]["por_anio"])
        rech = bh(p_tk)
        # IC medio de los años (cada año demeanea por separado → su nula NO está en 0)
        anual_real = np.mean([real[h]["por_anio"][a] for a in anios])
        anual_null = anio_null.mean(1)
        out[str(h)] = {
            "anual_ic": float(anual_real),
            "anual_null_media": float(anual_null.mean()),
            "anual_null_sd": float(anual_null.std(ddof=1)),
            "anual_p": float((1 + (anual_null <= anual_real).sum()) / (1 + n_perm)),
            "anios_bajo_nula": int(sum(real[h]["por_anio"][a] < anio_null[:, i].mean()
                                       for i, a in enumerate(anios))),
            "pooled_ic": real[h]["pooled"],
            "pooled_null_media": float(pooled_null.mean()),
            "pooled_null_sd": float(pooled_null.std(ddof=1)),
            "pooled_p": float((1 + (pooled_null <= real[h]["pooled"]).sum()) / (1 + n_perm)),
            "ic_tickers": real[h]["ic"].tolist(),
            "p_tickers": p_tk.tolist(),
            "crudos": int((p_tk < ALPHA).sum()), "bh": int(rech.sum()),
            "rechazados": [t for t, r in zip(eps.columns, rech, strict=True) if r],
            "por_anio": [{"anio": a, "ic": real[h]["por_anio"][a],
                          "null_media": float(anio_null[:, i].mean()),
                          "null_sd": float(anio_null[:, i].std(ddof=1)),
                          "p": float((1 + (anio_null[:, i] <= real[h]["por_anio"][a]).sum())
                                     / (1 + n_perm))}
                         for i, a in enumerate(anios)],
        }
    return out


# --------------------------------------------------------------------- robustez

def robustez(eps: pd.DataFrame, n_perm: int, rng,
             sector_de: dict[str, str] | None = None) -> dict:
    """
    ¿La señal es idiosincrática o un factor común que se coló en el residuo? ¿Es
    estable en el tiempo? Más la curva acumulada de la señal de juguete para graficar.
    """
    anio = eps.index.year.to_numpy()
    sector_de = sector_de or SECTOR_DE
    sector = np.array([sector_de[t] for t in eps.columns])
    E = eps.to_numpy()
    E_sec = E.copy()
    for sec in np.unique(sector):
        m = sector == sec
        E_sec[:, m] -= E[:, m].mean(1, keepdims=True)

    def z_ic(M: np.ndarray, h: int = 5) -> dict:
        real = _ics(M, anio, VENTANA_S)
        null = np.array([_ics(barajar_conjunto(M, rng), anio, VENTANA_S)[h]["pooled"]
                         for _ in range(n_perm)])
        return {"ic": real[h]["pooled"], "z": float((real[h]["pooled"] - null.mean())
                                                     / null.std(ddof=1)),
                "sharpe_bruto": real["juguete"]["sharpe_bruto"]}

    s = _sscore_rapido(np.cumsum(E, axis=0), VENTANA_S)
    _, pnl, _ = _pnl_juguete(s, E)
    ic_tk = _ic_por_columna(s, _forward(E, 5))

    mitades = []
    for a, b in ((2016, 2020), (2021, 2026)):
        m = (anio >= a) & (anio <= b)
        sm = _sscore_rapido(np.cumsum(E[m], axis=0), VENTANA_S)
        mitades.append({"desde": a, "hasta": b, **_juguete(sm, E[m])})

    return {
        "tal_cual": z_ic(E),
        "sin_mercado": z_ic(E - E.mean(1, keepdims=True)),
        "sin_sector": z_ic(E_sec),
        "mitades": mitades,
        "ic5_por_sector": {sec: float(np.nanmean(ic_tk[sector == sec]))
                           for sec in np.unique(sector)},
        "curva": {"fechas": [str(d.date()) for d in eps.index[1:]],
                  "pnl_acumulado": np.cumsum(pnl).round(6).tolist()},
    }


# ---------------------------------------------------------------------- potencia

def simular(n_series: int, T: int, hl: float, peso_ou: float, rng) -> np.ndarray:
    """
    ε = Δ(OU + camino aleatorio). `peso_ou` es la fracción de la varianza de las
    innovaciones que va al OU (1.0 = OU puro, 0.5 = el "50/50" del diagnóstico previo).
    Devuelve (T, n_series).
    """
    phi = 0.5 ** (1 / hl)
    u = rng.standard_normal((T + 1, n_series)) * np.sqrt(peso_ou)
    ou = np.zeros((T + 1, n_series))
    for t in range(1, T + 1):
        ou[t] = phi * ou[t - 1] + u[t]
    rw = np.cumsum(rng.standard_normal((T + 1, n_series)) * np.sqrt(1 - peso_ou), axis=0)
    return np.diff(ou + rw, axis=0)


def potencia(T: int, n_tickers: int, anio: np.ndarray, n_sim: int, n_perm: int,
             null_pooled: dict, rng) -> dict:
    """
    A: potencia por acción del test de pendiente (p < 0.05 crudo) con T días.
    B: IC pooled esperado de un universo donde TODAS las acciones tienen esa mezcla,
       en desvíos de la nula real (z); |z| > 1.64 sería detectable.
    """
    out = {"A": {}, "B": {}}
    for hl in (5, 10, 15, 20, 30, 60):
        for w in (1.0, 0.5, 0.25):
            E = simular(n_sim, T, hl, w, rng).T            # (n_sim, T)
            b = pendiente(E)
            menores = np.zeros(n_sim)
            for _ in range(n_perm):
                menores += pendiente(barajar(E.T, rng).T) <= b
            p = (1 + menores) / (1 + n_perm)
            out["A"][f"{hl}_{w}"] = float((p < ALPHA).mean())

            U = simular(n_tickers, T, hl, w, rng)
            r = _ics(U, anio, VENTANA_S)
            out["B"][f"{hl}_{w}"] = {
                str(h): (r[h]["pooled"] - null_pooled[str(h)]["pooled_null_media"])
                / null_pooled[str(h)]["pooled_null_sd"] for h in HORIZONTES}
            out["B"][f"{hl}_{w}"]["sharpe_bruto"] = r["juguete"]["sharpe_bruto"]
    return out


# -------------------------------------------------------------------------- main

def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--rapido", action="store_true")
    args = ap.parse_args()
    n_perm, n_perm_var, n_sim = (100, 50, 60) if args.rapido else (1000, 300, 200)
    rng = np.random.default_rng(20261018)
    t0 = time.time()

    returns = cargar_retornos()
    print(f"retornos {returns.shape}, {returns.index[0].date()} → {returns.index[-1].date()}")

    res = {"meta": {
        "fecha": "2026-10-18", "pedidos": len(TICKERS), "n_tickers": returns.shape[1],
        "descartados": sorted(set(TICKERS) - set(returns.columns)),
        "datos": [str(returns.index[0].date()), str(returns.index[-1].date())],
        "ventana_s": VENTANA_S, "horizontes": list(HORIZONTES),
        "n_perm": n_perm, "n_perm_variantes": n_perm_var, "n_sim": n_sim,
        "sectores": {t: SECTOR_DE[t] for t in returns.columns},
    }}

    # configuración principal: K = 5, re-ajuste anual sobre los últimos 252 días
    wf = walk_forward(returns, k=5, train=252)
    eps = wf["eps"]
    res["meta"]["oos"] = [str(eps.index[0].date()), str(eps.index[-1].date()), len(eps)]
    res["principal"] = {
        "k": 5, "train": 252, "por_anio": wf["por_anio"],
        "A": test_pendiente(eps, n_perm, rng),
        "B": test_predictivo(eps, n_perm, rng),
    }
    print(f"principal listo ({time.time() - t0:.0f}s)")

    variantes = [(5, None), (5, 504), (1, 252), (3, 252), (10, 252), (15, 504)]
    res["variantes"] = []
    for k, train in variantes:
        wfv = walk_forward(returns, k=k, train=train)
        ev = wfv["eps"]
        a = test_pendiente(ev, n_perm_var, rng)
        b = test_predictivo(ev, n_perm_var, rng)
        res["variantes"].append({
            "k": k, "train": train or "expansiva", "oos": [str(ev.index[0].date()), len(ev)],
            "r2_mediana": float(np.median([x["r2_mediana"] for x in wfv["por_anio"]])),
            "A": {x: a[x] for x in ("crudos", "esperados", "bh", "rechazados")},
            "B": {h: ({x: v for x, v in b[h].items() if x not in ("ic_tickers", "p_tickers")}
                      if h != "juguete" else b[h]) for h in b},
        })
        print(f"variante K={k} train={train} ({time.time() - t0:.0f}s)")

    res["robustez"] = {
        "principal": robustez(eps, n_perm_var, rng),
        "expansiva": robustez(walk_forward(returns, k=5, train=None)["eps"], n_perm_var, rng),
    }
    print(f"robustez lista ({time.time() - t0:.0f}s)")

    res["potencia"] = potencia(len(eps), eps.shape[1], eps.index.year.to_numpy(),
                               n_sim, n_perm // 2, res["principal"]["B"], rng)
    print(f"potencia lista ({time.time() - t0:.0f}s)")

    SALIDA.write_text(json.dumps(res, ensure_ascii=False, indent=1))
    print(f"→ {SALIDA}")


if __name__ == "__main__":
    main()
