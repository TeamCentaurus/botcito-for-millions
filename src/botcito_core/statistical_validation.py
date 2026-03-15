import pandas as pd
import numpy as np
from itertools import combinations
from statsmodels.tsa.stattools import coint, adfuller
from statsmodels.regression.linear_model import OLS
from statsmodels.tools import add_constant
from statsmodels.regression.linear_model import OLS
from statsmodels.tools import add_constant
from pykalman import KalmanFilter

def compute_correlation_matrix(prices: pd.DataFrame, window: int = 252) -> pd.DataFrame:
    """
    Calcula correlación de Pearson sobre ventana rodante.
    window=252 es un año bursátil para datos diarios.
    """
    returns = np.log(prices / prices.shift(1)).dropna()
    return returns.tail(window).corr()

def filter_by_correlation(corr_matrix: pd.DataFrame,
                           min_corr: float = 0.80) -> list[tuple]:
    """
    Devuelve pares con correlación >= min_corr.
    Un umbral de 0.80 es conservador y recomendado para comenzar.
    """
    pairs = []
    tickers = corr_matrix.columns.tolist()

    for t1, t2 in combinations(tickers, 2):
        corr = corr_matrix.loc[t1, t2]
        if corr >= min_corr:
            pairs.append((t1, t2, round(corr, 4)))

    return sorted(pairs, key=lambda x: x[2], reverse=True)


def test_cointegration(price_a: pd.Series,
                        price_b: pd.Series,
                        significance: float = 0.05) -> dict:
    """
    Prueba de cointegración de Engle-Granger.

    H0: No existe cointegración (el spread NO es estacionario)
    Se rechaza H0 si p-value < significance → el par ES cointegrado
    """
    score, pvalue, critical_values = coint(price_a, price_b)

    return {
        "cointegrado": pvalue < significance,
        "p_value": round(pvalue, 4),
        "estadistico": round(score, 4),
        "valores_criticos": critical_values,
        "interpretacion": "PAR VÁLIDO" if pvalue < significance else "DESCARTAR"
    }


def test_stationarity_adf(spread: pd.Series,
                           significance: float = 0.05) -> dict:
    """
    Prueba Augmented Dickey-Fuller.

    H0: La serie tiene raíz unitaria (NO es estacionaria)
    Se rechaza H0 si p-value < significance → el spread ES estacionario
    """
    result = adfuller(spread, autolag="AIC")

    return {
        "estacionario": result[1] < significance,
        "p_value": round(result[1], 4),
        "estadistico_adf": round(result[0], 4),
        "valores_criticos": result[4],
        "interpretacion": "SPREAD VÁLIDO" if result[1] < significance else "NO USAR"
    }


def compute_half_life(spread: pd.Series) -> float:
    """
    Estima el half-life de reversión a la media.
    Si el half-life > 30 días (datos diarios), el par puede ser demasiado lento.
    Si < 1 día (datos diarios), puede ser ruido estadístico.
    Rango ideal para datos diarios: 5-30 días.
    """
    spread_lag = spread.shift(1).dropna()
    spread_diff = spread.diff().dropna()

    # Regresión: Δspread = α + β * spread_lag
    X = add_constant(spread_lag)
    model = OLS(spread_diff, X).fit()
    beta = model.params.iloc[1]

    if beta >= 0:
        return float("inf")  # No hay reversión

    half_life = -np.log(2) / beta
    return round(half_life, 2)

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

def screen_pair(prices: pd.DataFrame,
                ticker_a: str,
                ticker_b: str,
                hedge_method: str = "ols") -> dict:
    """
    Ejecuta todos los tests estadísticos para un par.
    Devuelve un resumen de validez.
    """
    p_a = prices[ticker_a].dropna()
    p_b = prices[ticker_b].dropna()

    # Alinear fechas
    p_a, p_b = p_a.align(p_b, join="inner")

    # 1. Cointegración
    coint_result = test_cointegration(p_a, p_b)

    # 2. Hedge ratio via OLS
    hedge_ratio = compute_hedge_ratio(p_a, p_b)

    # 3. Spread
    spread = p_a - hedge_ratio * p_b

    # 4. Estacionariedad del spread
    adf_result = test_stationarity_adf(spread)

    # 5. Half-life
    hl = compute_half_life(spread)

    # Veredicto final
    es_valido = (
        coint_result["cointegrado"] and
        adf_result["estacionario"] and
        1 < hl < 60  # Ajustar según tu frecuencia de datos
    )

    return {
        "par": f"{ticker_a}/{ticker_b}",
        "valido": es_valido,
        "cointegracion": coint_result,
        "estacionariedad": adf_result,
        "half_life_dias": hl,
        "hedge_ratio": round(hedge_ratio, 4),
    }