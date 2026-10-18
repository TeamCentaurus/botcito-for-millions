"""
SPEC-004 — Sharpe anualizado.

Ver `docs/specs/004-sharpe-anualizado.md`. Todos los ACs están pendientes:
`annualized_sharpe` y `max_drawdown` (público) no existen todavía y `run_backtest`
no acepta `annualization_factor`.
"""

from __future__ import annotations

import numpy as np
import pytest

PENDIENTE = "SPEC-004 no implementada"

RETORNOS = np.array([0.01, -0.005, 0.02, 0.0])


@pytest.mark.spec
@pytest.mark.xfail(reason=PENDIENTE, strict=True)
def test_ac1_formula_caso_cerrado():
    from botcito_core.backtest import annualized_sharpe

    esperado = (RETORNOS.mean() / RETORNOS.std(ddof=1)) * np.sqrt(252)
    assert annualized_sharpe(RETORNOS, annualization_factor=252) == pytest.approx(
        esperado, abs=1e-12
    )


@pytest.mark.spec
@pytest.mark.xfail(reason=PENDIENTE, strict=True)
def test_ac2_escalado_por_raiz_del_factor():
    from botcito_core.backtest import annualized_sharpe

    anual = annualized_sharpe(RETORNOS, annualization_factor=252)
    crudo = annualized_sharpe(RETORNOS, annualization_factor=1)

    assert anual == pytest.approx(crudo * np.sqrt(252), abs=1e-12)


@pytest.mark.spec
@pytest.mark.xfail(reason=PENDIENTE, strict=True)
def test_ac3_series_degeneradas_dan_cero():
    """Ningún trade o un solo valor son casos normales: 0.0, no inf ni NaN."""
    from botcito_core.backtest import annualized_sharpe

    assert annualized_sharpe(np.array([])) == 0.0
    assert annualized_sharpe(np.array([0.01, 0.01, 0.01])) == 0.0
    assert annualized_sharpe(np.zeros(10)) == 0.0


@pytest.mark.spec
@pytest.mark.xfail(reason=PENDIENTE, strict=True)
def test_ac4_invariante_a_escala():
    from botcito_core.backtest import annualized_sharpe

    assert annualized_sharpe(RETORNOS * 10) == pytest.approx(
        annualized_sharpe(RETORNOS), abs=1e-12
    )


@pytest.mark.spec
@pytest.mark.xfail(reason=PENDIENTE, strict=True)
def test_ac5_run_backtest_expone_el_factor(coint_prices, pair_model):
    import inspect

    from botcito_core.backtest import run_backtest

    firma = inspect.signature(run_backtest)
    assert "annualization_factor" in firma.parameters
    assert firma.parameters["annualization_factor"].default == 252

    inicio = str(coint_prices.index[0].date())
    fin = str(coint_prices.index[-1].date())
    resultado = run_backtest(coint_prices, pair_model, inicio, fin)
    assert resultado["annualization_factor"] == 252


@pytest.mark.spec
@pytest.mark.xfail(reason=PENDIENTE, strict=True)
def test_ac6_factor_uno_vs_default(coint_prices, pair_model):
    from botcito_core.backtest import run_backtest

    inicio = str(coint_prices.index[0].date())
    fin = str(coint_prices.index[-1].date())

    anual = run_backtest(coint_prices, pair_model, inicio, fin)["sharpe_ratio"]
    crudo = run_backtest(
        coint_prices, pair_model, inicio, fin, annualization_factor=1
    )["sharpe_ratio"]

    assert anual == pytest.approx(crudo * np.sqrt(252), rel=1e-6)


@pytest.mark.spec
@pytest.mark.xfail(reason=PENDIENTE, strict=True)
def test_ac7_factor_invalido_falla():
    from botcito_core.backtest import annualized_sharpe

    with pytest.raises(ValueError):
        annualized_sharpe(RETORNOS, annualization_factor=0)

    with pytest.raises(ValueError):
        annualized_sharpe(RETORNOS, annualization_factor=-1)


@pytest.mark.spec
@pytest.mark.xfail(reason=PENDIENTE, strict=True)
def test_ac8_max_drawdown_caso_cerrado():
    """
    Retornos [+0.10, -0.20, +0.05] → equity [1.10, 0.88, 0.924].
    Pico 1.10, valle 0.88 → drawdown = 0.22 / 1.10 = 0.20.
    """
    from botcito_core.backtest import max_drawdown

    assert max_drawdown(np.array([0.10, -0.20, 0.05])) == pytest.approx(0.20, abs=1e-12)
    assert max_drawdown(np.array([0.01, 0.02, 0.03])) == pytest.approx(0.0, abs=1e-12)
    assert max_drawdown(np.array([])) == 0.0
