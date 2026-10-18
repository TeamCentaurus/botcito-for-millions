"""
Verificación de los generadores sintéticos.

Estos tests NO dependen de `botcito_core`: validan que el ground truth es el que
decimos que es. Si fallan, todos los ACs de todos los specs quedan sin fundamento.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from statsmodels.regression.linear_model import OLS
from statsmodels.tools import add_constant

import synthetic as syn


def test_ou_revierte_a_la_media():
    serie = syn.ou_series(theta=0.1, sigma=1.0, n=5000, mu=0.0, seed=1)
    assert abs(serie.mean()) < 0.5, "el OU debe orbitar su media"
    assert np.isfinite(serie).all()


def test_ou_half_life_recuperable_por_ols():
    """
    El half-life teórico ln(2)/theta debe recuperarse del estimador AR(1):
    regresar Δx sobre x_lag da beta ≈ -theta.
    """
    theta = 0.1
    serie = syn.ou_series(theta=theta, n=2000, seed=1)
    lag = serie.shift(1).dropna()
    dif = serie.diff().dropna()
    beta = OLS(dif, add_constant(lag)).fit().params.iloc[1]

    estimada = -np.log(2) / beta
    teorica = syn.half_life_teorica(theta)
    assert teorica == pytest.approx(6.93, abs=0.01)
    assert estimada == pytest.approx(teorica, rel=0.10)


def test_ou_theta_invalido_falla():
    with pytest.raises(ValueError, match="theta"):
        syn.ou_series(theta=0.0)
    with pytest.raises(ValueError, match="theta"):
        syn.ou_series(theta=1.5)


def test_random_walk_es_positivo():
    serie = syn.random_walk(n=2000, p0=100.0, seed=7)
    assert (serie > 0).all(), "los precios deben ser positivos para calcular shares"


def test_cointegrated_pair_recupera_el_beta():
    price_a, price_b = syn.cointegrated_pair(beta=2.0, alpha=10.0, theta=0.1, n=500, seed=2)
    beta = OLS(price_a, add_constant(price_b)).fit().params.iloc[1]
    assert beta == pytest.approx(2.0, abs=0.05)


def test_cointegrated_pair_spread_estacionario():
    price_a, price_b = syn.cointegrated_pair(beta=2.0, alpha=10.0, theta=0.1, n=500, seed=2)
    spread = price_a - 2.0 * price_b
    # El spread verdadero es alpha + OU: media cerca de alpha y varianza acotada.
    assert spread.mean() == pytest.approx(10.0, abs=1.5)
    assert spread.std() < 5.0


def test_independent_pair_no_tiene_relacion():
    price_a, price_b = syn.independent_pair(n=500, seed=3)
    corr = np.corrcoef(np.log(price_a).diff().dropna(), np.log(price_b).diff().dropna())[0, 1]
    assert abs(corr) < 0.15, "dos random walks independientes no deben correlacionar"


def test_price_frame_tiene_la_forma_esperada():
    price_a, price_b = syn.cointegrated_pair(n=100, seed=0)
    frame = syn.price_frame(AAPL=price_a, MSFT=price_b)
    assert list(frame.columns) == ["AAPL", "MSFT"]
    assert isinstance(frame.index, pd.DatetimeIndex)
    assert len(frame) == 100
    assert frame.index.freqstr == "B"


def test_price_frame_vacio_falla():
    with pytest.raises(ValueError):
        syn.price_frame()


def test_independent_universe_dimensiones():
    universe = syn.independent_universe(n_tickers=20, n=500, seed=0)
    assert universe.shape == (500, 20)
    assert universe.columns[0] == "T00"


def test_corrupt_after_solo_toca_el_futuro():
    universe = syn.independent_universe(n_tickers=3, n=300, seed=0)
    cutoff = universe.index[150]
    corrupted = syn.corrupt_after(universe, str(cutoff.date()))

    pd.testing.assert_frame_equal(universe.loc[:cutoff], corrupted.loc[:cutoff])
    assert (corrupted.loc[corrupted.index > cutoff] == 1e6).all().all()


def test_corrupt_between_solo_toca_el_rango():
    universe = syn.independent_universe(n_tickers=3, n=300, seed=0)
    inicio, fin = universe.index[100], universe.index[200]
    corrupted = syn.corrupt_between(universe, str(inicio.date()), str(fin.date()))

    assert (corrupted.loc[inicio:fin] == 1e6).all().all()

    antes, despues = universe.index[99], universe.index[201]
    pd.testing.assert_frame_equal(universe.loc[:antes], corrupted.loc[:antes])
    pd.testing.assert_frame_equal(universe.loc[despues:], corrupted.loc[despues:])


def test_generadores_son_deterministas():
    primera = syn.cointegrated_pair(seed=42)[0]
    segunda = syn.cointegrated_pair(seed=42)[0]
    pd.testing.assert_series_equal(primera, segunda)


def test_factor_panel_varianza_por_ticker():
    """Cada ticker tiene exactamente la fracción de varianza factorial pedida."""
    retornos, truth = syn.factor_panel(n_tickers=20, n_factors=2, varianza_factores=0.7, seed=0)
    comp_factor = truth["factores"].to_numpy() @ truth["betas"].to_numpy().T
    fraccion = comp_factor.var(axis=0) / retornos.to_numpy().var(axis=0)
    assert np.allclose(fraccion, 0.7, atol=1e-9)
    assert np.allclose(retornos.to_numpy().std(axis=0), 0.01, rtol=1e-9)


def test_factor_panel_descomposicion_exacta():
    retornos, truth = syn.factor_panel(seed=0)
    reconstruido = (truth["factores"].to_numpy() @ truth["betas"].to_numpy().T
                    + truth["residuos"].to_numpy())
    assert np.allclose(reconstruido, retornos.to_numpy(), atol=1e-14)
    assert np.allclose(truth["residuos"].cumsum().to_numpy(),
                       truth["residuo_acumulado"].to_numpy(), atol=1e-12)


def test_factor_panel_el_acumulado_es_ou():
    """La half-life del acumulado VERDADERO se recupera en mediana (base de SPEC-011 AC5)."""
    _, truth = syn.factor_panel(theta=0.1, n=1000, seed=0)
    estimadas = []
    for col in truth["residuo_acumulado"]:
        serie = truth["residuo_acumulado"][col]
        ajuste = OLS(serie.diff().dropna(), add_constant(serie.shift(1).dropna())).fit()
        beta = ajuste.params.iloc[1]
        estimadas.append(-np.log(2) / beta)
    assert np.median(estimadas) == pytest.approx(truth["half_life"], rel=0.10)


def test_independent_returns_sin_estructura():
    retornos = syn.independent_returns(n_tickers=20, n=1000, seed=0)
    corr = retornos.corr().to_numpy()
    fuera_diag = np.abs(corr[~np.eye(20, dtype=bool)])
    assert fuera_diag.max() < 0.15
