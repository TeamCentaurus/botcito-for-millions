from statsmodels.regression.linear_model import OLS
from statsmodels.tools import add_constant
from pykalman import KalmanFilter
import pandas as pd

def compute_hedge_ratio(price_a: pd.Series,
                         price_b: pd.Series,
                         method: str = "ols") -> float:
    """
    Métodos disponibles:
    - 'ols': Regresión lineal simple (estático, más simple)
    - 'kalman': Filtro de Kalman (dinámico, se adapta en el tiempo)
    """
    if method == "ols":
        X = add_constant(price_b)
        model = OLS(price_a, X).fit()
        return model.params.iloc[1]

    elif method == "kalman":
        return _kalman_hedge_ratio(price_a, price_b)

def _kalman_hedge_ratio(price_a: pd.Series,
                         price_b: pd.Series) -> pd.Series:
    """
    Hedge ratio dinámico usando Filtro de Kalman.
    Retorna una Serie con el hedge ratio en cada punto del tiempo.
    RECOMENDADO para datos intraday.
    """
    kf = KalmanFilter(
        transition_matrices=[1],
        observation_matrices=price_b.values.reshape(-1, 1, 1),
        initial_state_mean=0,
        initial_state_covariance=1,
        observation_covariance=1,
        transition_covariance=0.01
    )
    state_means, _ = kf.filter(price_a.values)
    return pd.Series(state_means.flatten(), index=price_a.index)

def compute_spread(price_a: pd.Series,
                   price_b: pd.Series,
                   hedge_ratio) -> pd.Series:
    """Calcula el spread: spread = A - β * B"""
    if isinstance(hedge_ratio, pd.Series):
        return price_a - hedge_ratio * price_b
    return price_a - hedge_ratio * price_b

def compute_zscore(spread: pd.Series,
                   window: int = 30) -> pd.Series:
    """
    Z-Score rodante del spread.
    z = (spread - media) / desviación_estándar

    Ventana recomendada:
    - Datos diarios: 20-60 días
    - Datos por minuto: 60-240 minutos
    """
    mean = spread.rolling(window=window).mean()
    std  = spread.rolling(window=window).std()
    return (spread - mean) / std