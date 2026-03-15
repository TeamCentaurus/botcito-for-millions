import pandas as pd
import numpy as np
import joblib
from botcito_core.statistical_validation import compute_hedge_ratio, compute_half_life
from botcito_core.spread_calculator import compute_spread
from botcito_core.backtest import run_backtest
from botcito_core.types import PairModel

def train(prices: pd.DataFrame,
          ticker_a: str,
          ticker_b: str,
          train_end: str,
          zscore_window: int = 30,
          entry_z: float = 2.0,
          exit_z: float = 0.5,
          stop_z: float = 3.5) -> PairModel:
    """
    Entrena el modelo para un par de acciones.

    Parámetros de Z-Score recomendados:
    - entry_z=2.0  → entrar cuando el spread está 2 desv. estándar de la media
    - exit_z=0.5   → salir cuando el spread vuelve cerca de la media
    - stop_z=3.5   → stop-loss si el spread se aleja demasiado (divergencia extrema)
    """
    # Datos de entrenamiento
    p_a = prices.loc[:train_end, ticker_a]
    p_b = prices.loc[:train_end, ticker_b]
    p_a, p_b = p_a.align(p_b, join="inner")

    # Hedge ratio sobre datos de entrenamiento
    hedge_ratio = compute_hedge_ratio(p_a, p_b, method="ols")

    # Spread y parámetros estadísticos
    spread = compute_spread(p_a, p_b, hedge_ratio)

    model = PairModel(
        ticker_a=ticker_a,
        ticker_b=ticker_b,
        hedge_ratio=hedge_ratio,
        spread_mean=spread.mean(),
        spread_std=spread.std(),
        half_life=compute_half_life(spread),
        zscore_window=zscore_window,
        entry_threshold=entry_z,
        exit_threshold=exit_z,
        stop_loss_threshold=stop_z,
    )

    return model


def save_model(model: PairModel, path: str):
    joblib.dump(model, path)
    print(f"Modelo guardado en {path}")

def load_model(path: str) -> PairModel:
    return joblib.load(path)


def optimize_thresholds(prices: pd.DataFrame,
                         model: PairModel,
                         val_start: str,
                         val_end: str) -> dict:
    """
    Busca los mejores umbrales de z-score en el período de validación.
    Métrica objetivo: Sharpe Ratio.
    """
    from itertools import product

    entry_range = [1.5, 2.0, 2.5]
    exit_range  = [0.0, 0.5, 1.0]

    best_sharpe = -np.inf
    best_params = {}

    for entry, exit_ in product(entry_range, exit_range):
        if exit_ >= entry:
            continue

        model.entry_threshold = entry
        model.exit_threshold = exit_

        # Ejecutar backtest en validación
        results = run_backtest(prices, model, val_start, val_end)
        sharpe = results["sharpe_ratio"]

        if sharpe > best_sharpe:
            best_sharpe = sharpe
            best_params = {"entry": entry, "exit": exit_, "sharpe": sharpe}

    print(f"Mejores parámetros: {best_params}")
    return best_params