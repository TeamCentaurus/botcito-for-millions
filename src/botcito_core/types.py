from dataclasses import dataclass

import numpy as np

@dataclass
class PairModel:
    """Contiene todos los parámetros de un par entrenado."""
    ticker_a: str
    ticker_b: str
    hedge_ratio: float
    spread_mean: float
    spread_std: float
    half_life: float
    zscore_window: int
    entry_threshold: float    # Z-score para abrir posición
    exit_threshold: float     # Z-score para cerrar posición
    stop_loss_threshold: float  # Z-score para stop-loss

@dataclass(frozen=True)
class FactorModel:
    """
    Modelo de factores estimado sobre UN período de entrenamiento (SPEC-011).

    `loadings`, `intercepts`, `eigenvectors`, `return_means` y `return_stds` son
    parámetros del training y NO se re-estiman para evaluar: proyectar con ellos es
    lo que hace que el residuo fuera de muestra no tenga look-ahead.
    """
    tickers: tuple[str, ...]
    n_factors: int
    eigenvectors: np.ndarray             # (n_tickers, n_factors)
    loadings: np.ndarray                 # (n_tickers, n_factors) — betas de la regresión
    intercepts: np.ndarray               # (n_tickers,)
    return_means: np.ndarray             # (n_tickers,) del training
    return_stds: np.ndarray              # (n_tickers,) del training
    explained_variance_ratio: np.ndarray # (n_factors,)
    train_end: str
