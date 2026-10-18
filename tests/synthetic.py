"""
Generadores de datos sintéticos con ground truth conocido.

Son el pilar del arnés: un criterio de aceptación como "no hay look-ahead" o "el
half-life se recupera" solo es falsificable si la respuesta correcta se conoce de
antemano. Nada aquí importa `botcito_core` — estos generadores se validan contra sí
mismos (ver `test_synthetic.py`), no contra el código que verifican.

Convención de ADR-0002: índice de días hábiles (`freq="B"`), timeframe daily.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

DEFAULT_START = "2020-01-01"


def business_index(n: int, start: str = DEFAULT_START) -> pd.DatetimeIndex:
    """Índice de `n` días hábiles consecutivos."""
    return pd.date_range(start=start, periods=n, freq="B")


def ou_series(
    theta: float = 0.1,
    sigma: float = 1.0,
    n: int = 500,
    mu: float = 0.0,
    x0: float | None = None,
    seed: int = 0,
    start: str = DEFAULT_START,
) -> pd.Series:
    """
    Proceso Ornstein-Uhlenbeck discretizado con dt=1:

        x_t = x_{t-1} + theta * (mu - x_{t-1}) + sigma * eps_t

    Half-life analítica: ln(2) / theta. Es el valor que `compute_half_life` debe
    recuperar, porque su estimador regresa Δx sobre x_lag y obtiene beta ≈ -theta.
    """
    if not 0 < theta < 1:
        raise ValueError(f"theta debe estar en (0, 1) para que el proceso revierta: {theta}")

    rng = np.random.default_rng(seed)
    x = np.empty(n, dtype=float)
    x[0] = mu if x0 is None else x0
    noise = rng.normal(0.0, sigma, size=n)
    for t in range(1, n):
        x[t] = x[t - 1] + theta * (mu - x[t - 1]) + noise[t]

    return pd.Series(x, index=business_index(n, start), name="ou")


def half_life_teorica(theta: float) -> float:
    """Half-life analítica de un OU con velocidad de reversión `theta`."""
    return float(np.log(2) / theta)


def random_walk(
    n: int = 500,
    p0: float = 100.0,
    sigma_ret: float = 0.01,
    drift: float = 0.0,
    seed: int = 0,
    start: str = DEFAULT_START,
    name: str = "rw",
) -> pd.Series:
    """
    Random walk geométrico: precios I(1) y siempre positivos (necesario para los
    cálculos de shares y notional de SPEC-005).
    """
    rng = np.random.default_rng(seed)
    log_ret = rng.normal(drift, sigma_ret, size=n)
    log_ret[0] = 0.0
    prices = p0 * np.exp(np.cumsum(log_ret))
    return pd.Series(prices, index=business_index(n, start), name=name)


def cointegrated_pair(
    beta: float = 2.0,
    alpha: float = 10.0,
    theta: float = 0.1,
    sigma_spread: float = 1.0,
    n: int = 500,
    p0: float = 100.0,
    seed: int = 0,
    start: str = DEFAULT_START,
) -> tuple[pd.Series, pd.Series]:
    """
    Par cointegrado por construcción:

        B_t = random walk geométrico
        A_t = alpha + beta * B_t + OU_t

    Ground truth: hedge ratio = `beta`, intercepto = `alpha`, half-life del spread
    = ln(2) / theta. El spread A - beta*B es estacionario alrededor de `alpha`.
    """
    price_b = random_walk(n=n, p0=p0, seed=seed, start=start, name="B")
    noise = ou_series(theta=theta, sigma=sigma_spread, n=n, seed=seed + 1_000, start=start)
    price_a = pd.Series(
        alpha + beta * price_b.to_numpy() + noise.to_numpy(),
        index=price_b.index,
        name="A",
    )
    return price_a, price_b


def independent_pair(
    n: int = 500,
    p0: float = 100.0,
    seed: int = 0,
    start: str = DEFAULT_START,
) -> tuple[pd.Series, pd.Series]:
    """
    Dos random walks independientes: NO cointegrados.

    Es el test de falsos positivos. Un screening sin corrección por multiple testing
    deja pasar ~5% de estos pares a alpha=0.05 (SPEC-002, AC5).
    """
    price_a = random_walk(n=n, p0=p0, seed=seed, start=start, name="A")
    price_b = random_walk(n=n, p0=p0, seed=seed + 500_000, start=start, name="B")
    return price_a, price_b


def price_frame(**series: pd.Series) -> pd.DataFrame:
    """
    Ensambla un DataFrame con la forma que esperan `screen_pair`, `model.train` y
    `run_backtest`: columnas por ticker, DatetimeIndex de días hábiles.

        price_frame(AAPL=serie_a, MSFT=serie_b)
    """
    if not series:
        raise ValueError("price_frame necesita al menos una serie")
    frame = pd.DataFrame({ticker: s.to_numpy() for ticker, s in series.items()})
    frame.index = next(iter(series.values())).index
    return frame


def independent_universe(
    n_tickers: int = 20,
    n: int = 500,
    seed: int = 0,
    start: str = DEFAULT_START,
) -> pd.DataFrame:
    """
    Universo de `n_tickers` random walks independientes, nombrados T00, T01, ...
    Ninguno cointegra con ninguno: cualquier par "válido" es un falso positivo.
    """
    series = {
        f"T{i:02d}": random_walk(n=n, seed=seed + i * 7_919, start=start, name=f"T{i:02d}")
        for i in range(n_tickers)
    }
    return price_frame(**series)


def corrupt_after(prices: pd.DataFrame, cutoff: str, value: float = 1e6) -> pd.DataFrame:
    """
    Copia de `prices` con todo lo POSTERIOR a `cutoff` reemplazado por `value`.

    Herramienta central de los tests de leakage: si una función que solo debería
    mirar hasta `cutoff` devuelve un resultado distinto sobre esta copia, está
    leyendo el futuro (SPEC-003 AC3, SPEC-006 AC2).
    """
    corrupted = prices.copy()
    corrupted.loc[corrupted.index > pd.Timestamp(cutoff)] = value
    return corrupted


def corrupt_between(
    prices: pd.DataFrame, start: str, end: str, value: float = 1e6
) -> pd.DataFrame:
    """Copia de `prices` con el rango [start, end] reemplazado por `value`."""
    corrupted = prices.copy()
    mask = (corrupted.index >= pd.Timestamp(start)) & (corrupted.index <= pd.Timestamp(end))
    corrupted.loc[mask] = value
    return corrupted


def factor_panel(
    n_tickers: int = 20,
    n_factors: int = 2,
    n: int = 1000,
    varianza_factores: float = 0.7,
    theta: float = 0.1,
    sigma_ret: float = 0.01,
    seed: int = 0,
    start: str = DEFAULT_START,
) -> tuple[pd.DataFrame, dict]:
    """
    Panel de RETORNOS de `n_tickers` acciones generado por `n_factors` factores más un
    componente idiosincrático cuyo ACUMULADO es un OU (Avellaneda-Lee, SPEC-011):

        R_i(t) = Σ_k beta_ik · F_k(t) + eps_i(t),     eps_i(t) = X_i(t) − X_i(t−1)
        X_i    = OU con velocidad `theta`  →  half-life ln(2)/theta

    Cada ticker tiene exactamente (en muestra) `varianza_factores` de su varianza
    explicada por el componente factorial (se escala ticker por ticker). Los factores son
    iid normales e independientes entre sí, con varianzas decrecientes para que los
    autovalores queden ordenados sin ambigüedad. Sin intercepto (alpha = 0).

    Ground truth devuelto: `factores` (T, K), `betas` (N, K), `residuos` (T, N) = eps,
    `residuo_acumulado` (T, N) = X − X(0), `half_life` = ln(2)/theta.
    """
    if not 0 < varianza_factores < 1:
        raise ValueError(f"varianza_factores debe estar en (0, 1): {varianza_factores}")
    if n_factors < 1:
        raise ValueError(f"n_factors debe ser >= 1: {n_factors}")

    rng = np.random.default_rng(seed)
    index = business_index(n, start)
    tickers = [f"T{i:02d}" for i in range(n_tickers)]

    escalas = 1.0 / (1.0 + np.arange(n_factors))      # 1, 1/2, 1/3, ...
    factores = rng.normal(0.0, 1.0, size=(n, n_factors)) * escalas
    betas = rng.normal(0.0, 1.0, size=(n_tickers, n_factors))
    betas[:, 0] += 1.0                                 # factor 1 tipo "mercado"

    acumulado = np.column_stack(
        [ou_series(theta=theta, n=n, seed=seed + 10_007 * (i + 1)).to_numpy()
         for i in range(n_tickers)]
    )
    acumulado = acumulado - acumulado[0]               # X(0) = 0 → eps(0) = 0
    residuos = np.vstack([np.zeros((1, n_tickers)), np.diff(acumulado, axis=0)])

    comp_factor = factores @ betas.T                   # (T, N)
    # escala k_i tal que, EN MUESTRA, var(k·C) / var(k·C + e) = varianza_factores.
    # Incluye la covarianza muestral C–e (no es exactamente 0 aunque sean independientes):
    #   k²·a·(1−v) − 2·v·c·k − v·b = 0
    v = varianza_factores
    a = comp_factor.var(axis=0)
    b = residuos.var(axis=0)
    c = ((comp_factor - comp_factor.mean(axis=0)) * (residuos - residuos.mean(axis=0))).mean(axis=0)
    k = (2 * v * c + np.sqrt(4 * v**2 * c**2 + 4 * a * (1 - v) * v * b)) / (2 * a * (1 - v))
    betas = betas * k[:, None]
    comp_factor = factores @ betas.T

    total = comp_factor + residuos
    escala = sigma_ret / total.std(axis=0)             # retornos diarios ~1 %
    retornos = total * escala

    truth = {
        "factores": pd.DataFrame(factores, index=index,
                                 columns=[f"F{k + 1}" for k in range(n_factors)]),
        "betas": pd.DataFrame(betas * escala[:, None], index=tickers,
                              columns=[f"F{k + 1}" for k in range(n_factors)]),
        "residuos": pd.DataFrame(residuos * escala, index=index, columns=tickers),
        "residuo_acumulado": pd.DataFrame(acumulado * escala, index=index, columns=tickers),
        "half_life": half_life_teorica(theta),
    }
    return pd.DataFrame(retornos, index=index, columns=tickers), truth


def independent_returns(
    n_tickers: int = 20,
    n: int = 1000,
    sigma_ret: float = 0.01,
    seed: int = 0,
    start: str = DEFAULT_START,
) -> pd.DataFrame:
    """Retornos iid normales e independientes entre tickers: sin estructura de factores."""
    rng = np.random.default_rng(seed)
    return pd.DataFrame(
        rng.normal(0.0, sigma_ret, size=(n, n_tickers)),
        index=business_index(n, start),
        columns=[f"T{i:02d}" for i in range(n_tickers)],
    )
