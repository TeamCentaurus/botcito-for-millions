"""
Modelo de factores PCA, residuos idiosincráticos y s-score (SPEC-011, ADR-0005).

Pipeline de Avellaneda & Lee (2010):

    PCA sobre la correlación de retornos → eigenportafolios → regresión de cada
    acción contra los K primeros → residuo ε → residuo ACUMULADO X → s-score.

Lo que se modela como media-reverting es el residuo acumulado `X(t) = Σ ε(s)`, no
el residuo `ε(t)` (que es aproximadamente ruido blanco). Ver SPEC-011 §2.
"""

import numpy as np
import pandas as pd

from botcito_core.spread_calculator import compute_zscore
from botcito_core.types import FactorModel

# Mínimo de observaciones por factor para que la regresión sea informativa
MIN_OBS_POR_FACTOR = 10


def _validar_sin_nan(returns: pd.DataFrame) -> None:
    """ValueError si el panel tiene NaN (SPEC-010 ya debería garantizar que no)."""
    if returns.isna().to_numpy().any():
        columnas = [str(c) for c in returns.columns[returns.isna().any()]]
        raise ValueError(f"returns tiene NaN en las columnas: {columnas}")


def _validar_alineacion(model: FactorModel, returns: pd.DataFrame) -> None:
    """I8: las columnas de `returns` deben ser `model.tickers`, en el mismo orden."""
    columnas = tuple(str(c) for c in returns.columns)
    if columnas == model.tickers:
        return

    faltan = [t for t in model.tickers if t not in columnas]
    sobran = [c for c in columnas if c not in model.tickers]
    if faltan or sobran:
        raise ValueError(
            "las columnas de returns no coinciden con model.tickers: "
            f"faltan {faltan}, sobran {sobran}"
        )
    raise ValueError(
        "las columnas de returns están en otro orden que model.tickers: "
        f"esperado {list(model.tickers)}, recibido {list(columnas)}"
    )


def fit_factor_model(returns: pd.DataFrame, n_factors: int = 5,
                     train_end: str | None = None) -> FactorModel:
    """
    Ajusta el modelo de factores sobre el período recibido.

    1. Estandariza los retornos con media y desviación del período recibido.
    2. PCA sobre la matriz de correlación → `n_factors` autovectores.
    3. Construye los eigenportafolios con pesos  Qᵏᵢ = vᵏᵢ / stdᵢ.
    4. Regresa cada acción contra los K retornos de eigenportafolio (OLS con
       intercepto) y guarda `loadings` e `intercepts`.

    El caller es responsable de pasar SOLO retornos del período de entrenamiento.
    """
    n_obs, n_tickers = returns.shape

    if n_factors < 1 or n_factors >= n_tickers:
        raise ValueError(
            f"n_factors debe cumplir 1 <= n_factors < n_tickers ({n_tickers}): {n_factors}"
        )
    if n_obs < MIN_OBS_POR_FACTOR * n_factors:
        raise ValueError(
            f"se necesitan al menos {MIN_OBS_POR_FACTOR * n_factors} observaciones "
            f"para {n_factors} factores; hay {n_obs}"
        )
    _validar_sin_nan(returns)

    R = returns.to_numpy(dtype=float)

    # 1. estandarización con parámetros del training
    means = R.mean(axis=0)
    stds = R.std(axis=0, ddof=1)
    if np.any(stds == 0):
        constantes = [str(c) for c, s in zip(returns.columns, stds) if s == 0]
        raise ValueError(f"retornos con desviación cero: {constantes}")
    Y = (R - means) / stds

    # 2. PCA sobre la matriz de correlación (eigh: simétrica, autovalores ascendentes)
    corr = (Y.T @ Y) / (n_obs - 1)
    eigvals, eigvecs = np.linalg.eigh(corr)
    orden = np.argsort(eigvals)[::-1]
    eigvals = eigvals[orden]
    eigvecs = eigvecs[:, orden]

    vecs = eigvecs[:, :n_factors].copy()
    # signo determinista: cada autovector con suma de componentes no negativa
    signos = np.where(vecs.sum(axis=0) < 0, -1.0, 1.0)
    vecs = vecs * signos

    evr = np.clip(eigvals[:n_factors], 0.0, None) / eigvals.sum()

    # 3. eigenportafolios: Qᵏᵢ = vᵏᵢ / stdᵢ  →  Fₖ(t) = Σᵢ Qᵏᵢ · Rᵢ(t)
    pesos = vecs / stds[:, None]
    F = R @ pesos

    # 4. OLS con intercepto de cada acción contra los K factores
    X = np.column_stack([np.ones(n_obs), F])
    coefs, *_ = np.linalg.lstsq(X, R, rcond=None)   # (1 + K, N)
    intercepts = coefs[0]
    loadings = coefs[1:].T                           # (N, K)

    if train_end is None:
        ultimo = returns.index[-1]
        train_end = str(ultimo.date()) if hasattr(ultimo, "date") else str(ultimo)

    return FactorModel(
        tickers=tuple(str(c) for c in returns.columns),
        n_factors=int(n_factors),
        eigenvectors=vecs,
        loadings=loadings,
        intercepts=intercepts,
        return_means=means,
        return_stds=stds,
        explained_variance_ratio=evr,
        train_end=train_end,
    )


def compute_factor_returns(model: FactorModel, returns: pd.DataFrame) -> pd.DataFrame:
    """Retornos de los K eigenportafolios: Fₖ(t) = Σᵢ Qᵏᵢ · Rᵢ(t).  (T, n_factors)"""
    _validar_alineacion(model, returns)
    _validar_sin_nan(returns)

    pesos = model.eigenvectors / model.return_stds[:, None]
    F = returns.to_numpy(dtype=float) @ pesos
    columnas = [f"F{k + 1}" for k in range(model.n_factors)]
    return pd.DataFrame(F, index=returns.index, columns=columnas)


def compute_residuals(model: FactorModel, returns: pd.DataFrame) -> pd.DataFrame:
    """
    Residuo idiosincrático por acción, PROYECTANDO con los parámetros del modelo:
        εᵢ(t) = Rᵢ(t) − αᵢ − Σₖ βᵏᵢ · Fₖ(t)
    Nunca re-estima. (T, n_tickers)
    """
    F = compute_factor_returns(model, returns).to_numpy()
    R = returns.to_numpy(dtype=float)
    residuos = R - model.intercepts - F @ model.loadings.T
    return pd.DataFrame(residuos, index=returns.index, columns=returns.columns)


def cumulative_residual(residuals: pd.DataFrame) -> pd.DataFrame:
    """Suma acumulada de los residuos: el proceso que se modela como OU."""
    return residuals.cumsum()


def compute_sscore(cumulative: pd.DataFrame, window: int) -> pd.DataFrame:
    """
    s-score: z-score rolling causal del residuo acumulado, columna por columna,
    delegando en `botcito_core.spread_calculator.compute_zscore` para que el cálculo
    sea literalmente el mismo que usa el live (ADR-0001).
    """
    return pd.DataFrame(
        {c: compute_zscore(cumulative[c], window=window) for c in cumulative.columns},
        index=cumulative.index,
    )
