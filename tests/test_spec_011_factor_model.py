"""
SPEC-011 — Modelo de factores PCA, residuos y s-score.

Ver `docs/specs/011-modelo-de-factores-y-residuos.md` y ADR-0005. Implementada el
2026-10-17: los 11 ACs corren sin marker xfail.

Toda la verdad viene de `synthetic.factor_panel`: retornos = factores + incrementos de
un OU, con betas, residuos y half-life conocidos.
"""

from __future__ import annotations

import dataclasses
import json

import numpy as np
import pandas as pd
import pytest

from synthetic import corrupt_after, factor_panel, independent_returns

N_TICKERS = 20
N_FACTORS = 2
N_OBS = 1000
THETA = 0.1
WINDOW = 30
RANGO_TRADEABLE = (5.0, 30.0)  # ADR-0002, días


@pytest.fixture
def panel():
    """Panel de AC1: 20 tickers, 2 factores con 70 % de la varianza, theta=0.1."""
    return factor_panel(n_tickers=N_TICKERS, n_factors=N_FACTORS, n=N_OBS,
                        varianza_factores=0.7, theta=THETA, seed=0)


@pytest.fixture
def returns(panel):
    return panel[0]


@pytest.fixture
def truth(panel):
    return panel[1]


@pytest.fixture
def fitted(returns):
    from botcito_core.factor_model import fit_factor_model

    return fit_factor_model(returns, n_factors=N_FACTORS)


@pytest.mark.spec
def test_ac1_varianza_explicada(fitted):
    evr = np.asarray(fitted.explained_variance_ratio)

    assert evr.shape == (N_FACTORS,)
    assert np.all(np.diff(evr) <= 0), f"no decreciente: {evr}"
    assert np.all((evr >= 0) & (evr <= 1))
    assert evr.sum() <= 1 + 1e-12
    assert evr.sum() >= 0.60, f"los 2 factores capturan solo {evr.sum():.3f}"


@pytest.mark.spec
def test_ac2_recupera_residuo_verdadero(fitted, returns, truth):
    from botcito_core.factor_model import compute_residuals

    estimado = compute_residuals(fitted, returns)
    verdadero = truth["residuos"]

    corrs = pd.Series({
        ticker: np.corrcoef(estimado[ticker], verdadero[ticker])[0, 1]
        for ticker in returns.columns
    })
    # mediana y no por ticker: con N=20 PCA filtra parte del residuo de las acciones
    # con peso grande en un autovector (ver historial del spec)
    assert corrs.median() >= 0.90, f"mediana {corrs.median():.3f}\n{corrs.round(3)}"
    assert corrs.min() >= 0.80, f"mínimo {corrs.min():.3f} en {corrs.idxmin()}"


@pytest.mark.spec
def test_ac3_ortogonalidad_en_muestra(fitted, returns):
    from botcito_core.factor_model import compute_factor_returns, compute_residuals

    residuos = compute_residuals(fitted, returns).to_numpy()
    factores = compute_factor_returns(fitted, returns).to_numpy()

    peor = max(
        abs(np.corrcoef(residuos[:, i], factores[:, k])[0, 1])
        for i in range(residuos.shape[1])
        for k in range(factores.shape[1])
    )
    assert peor < 1e-8, f"max |corr(residuo, factor)| = {peor:.2e}"


@pytest.mark.spec
def test_ac4_sin_look_ahead(returns):
    from botcito_core.factor_model import (
        compute_residuals,
        cumulative_residual,
        fit_factor_model,
    )

    t = returns.index[599]   # fin del training
    s = returns.index[800]   # punto evaluado, fuera de muestra
    modelo = fit_factor_model(returns.loc[:t], n_factors=N_FACTORS, train_end=str(t.date()))

    corrupto = corrupt_after(returns, str(s.date()))
    assert not corrupto.equals(returns), "la corrupción no tocó nada"

    res_ok = compute_residuals(modelo, returns)
    res_bad = compute_residuals(modelo, corrupto)
    acum_ok = cumulative_residual(res_ok)
    acum_bad = cumulative_residual(res_bad)

    np.testing.assert_allclose(res_bad.loc[:s], res_ok.loc[:s], rtol=0, atol=1e-12)
    np.testing.assert_allclose(acum_bad.loc[:s], acum_ok.loc[:s], rtol=0, atol=1e-12)
    # control: después de s la corrupción sí se ve
    assert not np.allclose(res_bad.loc[s:].iloc[1:], res_ok.loc[s:].iloc[1:])


@pytest.mark.spec
def test_ac5_el_ou_es_el_acumulado(fitted, returns, truth):
    """La trampa de §2: el OU es el residuo ACUMULADO, no el residuo."""
    from botcito_core.factor_model import compute_residuals, cumulative_residual
    from botcito_core.statistical_validation import compute_half_life

    residuos = compute_residuals(fitted, returns)
    acumulado = cumulative_residual(residuos)

    # (a) mediana entre tickers dentro de ±20 % de ln(2)/theta
    hl_acum = [compute_half_life(acumulado[c]) for c in acumulado.columns]
    mediana = float(np.median(hl_acum))
    assert mediana == pytest.approx(truth["half_life"], rel=0.20), (
        f"mediana {mediana:.2f} vs teórica {truth['half_life']:.2f}; por ticker: {hl_acum}"
    )

    # (b) el residuo crudo queda fuera del rango tradeable en TODOS los tickers
    lo, hi = RANGO_TRADEABLE
    for c in residuos.columns:
        hl_crudo = compute_half_life(residuos[c])
        assert not (lo < hl_crudo < hi), (
            f"{c}: half-life del residuo crudo = {hl_crudo} cae en el rango tradeable"
        )


@pytest.mark.spec
def test_ac6_sscore_usa_compute_zscore(fitted, returns):
    from botcito_core import factor_model, spread_calculator
    from botcito_core.factor_model import (
        compute_residuals,
        compute_sscore,
        cumulative_residual,
    )

    assert factor_model.compute_zscore is spread_calculator.compute_zscore

    acumulado = cumulative_residual(compute_residuals(fitted, returns))
    sscore = compute_sscore(acumulado, window=WINDOW)

    for c in acumulado.columns[:3]:
        esperado = spread_calculator.compute_zscore(acumulado[c], window=WINDOW)
        pd.testing.assert_series_equal(sscore[c], esperado, check_names=False)


@pytest.mark.spec
def test_ac7_no_muta_input(returns):
    from botcito_core.factor_model import (
        compute_factor_returns,
        compute_residuals,
        cumulative_residual,
        fit_factor_model,
    )

    original = returns.copy(deep=True)
    modelo = fit_factor_model(returns, n_factors=N_FACTORS)
    compute_factor_returns(modelo, returns)
    residuos = compute_residuals(modelo, returns)
    residuos_original = residuos.copy(deep=True)
    cumulative_residual(residuos)

    pd.testing.assert_frame_equal(returns, original)
    pd.testing.assert_frame_equal(residuos, residuos_original)


@pytest.mark.spec
def test_ac8_errores_de_dimension(returns):
    from botcito_core.factor_model import fit_factor_model

    with pytest.raises(ValueError):
        fit_factor_model(returns, n_factors=0)
    with pytest.raises(ValueError):
        fit_factor_model(returns, n_factors=returns.shape[1])
    with pytest.raises(ValueError):
        fit_factor_model(returns.iloc[:15], n_factors=5)


@pytest.mark.spec
def test_ac9_tickers_desalineados(fitted, returns):
    from botcito_core.factor_model import compute_residuals

    invertido = returns[returns.columns[::-1]]
    with pytest.raises(ValueError):
        compute_residuals(fitted, invertido)

    renombrado = returns.rename(columns={"T05": "ZZZ"})
    with pytest.raises(ValueError, match="ZZZ|T05"):
        compute_residuals(fitted, renombrado)


@pytest.mark.spec
def test_ac10_no_inventa_factores():
    from botcito_core.factor_model import fit_factor_model

    ruido = independent_returns(n_tickers=N_TICKERS, n=N_OBS, seed=0)
    modelo = fit_factor_model(ruido, n_factors=N_FACTORS)

    n, t = ruido.shape[1], ruido.shape[0]
    techo = 1.2 * (1 + np.sqrt(n / t)) ** 2 / n   # Marchenko-Pastur + 20 %
    assert modelo.explained_variance_ratio[0] < techo, (
        f"EVR[0] = {modelo.explained_variance_ratio[0]:.4f} >= techo {techo:.4f}"
    )


@pytest.mark.spec
def test_ac11_serializable(fitted):
    from botcito_core.reporting import _to_native
    from botcito_core.types import FactorModel

    assert isinstance(fitted, FactorModel)
    assert dataclasses.is_dataclass(fitted)
    with pytest.raises(dataclasses.FrozenInstanceError):
        fitted.n_factors = 99  # type: ignore[misc]

    json.dumps(_to_native(dataclasses.asdict(fitted)))
