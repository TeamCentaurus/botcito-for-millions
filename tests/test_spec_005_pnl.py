"""
SPEC-005 — PnL sobre capital invertido.

Ver `docs/specs/005-pnl-sobre-capital.md`. Todos los ACs están pendientes:
`run_backtest` no acepta `capital` y sigue normalizando el PnL por `spread_std`.

Los ACs no predicen en qué barra entra cada trade: recalculan el PnL desde los
precios y shares que el propio backtest registra en cada trade. Así el AC verifica
coherencia interna y unidad económica sin acoplarse al timing de la señal.
"""

from __future__ import annotations

import dataclasses

import pytest

PENDIENTE = "SPEC-005 no implementada"


def _rango(prices):
    return str(prices.index[0].date()), str(prices.index[-1].date())


def _trades_cerrados(resultado):
    return [t for t in resultado["trades"] if str(t["type"]).startswith(("CLOSE", "FORCED"))]


@pytest.mark.spec
@pytest.mark.xfail(reason=PENDIENTE, strict=True)
def test_ac1_sin_normalizar_por_spread_std(coint_prices, pair_model):
    """I6, por comportamiento: el PnL no puede depender de `spread_std`."""
    from botcito_core.backtest import run_backtest

    inicio, fin = _rango(coint_prices)
    normal = run_backtest(coint_prices, pair_model, inicio, fin, capital=10_000.0)
    absurdo = run_backtest(
        coint_prices,
        dataclasses.replace(pair_model, spread_std=1e9),
        inicio,
        fin,
        capital=10_000.0,
    )

    assert normal["total_pnl"] == pytest.approx(absurdo["total_pnl"], abs=1e-9)
    assert normal["total_return"] == pytest.approx(absurdo["total_return"], abs=1e-9)


@pytest.mark.spec
@pytest.mark.xfail(reason=PENDIENTE, strict=True)
def test_ac2_invarianza_de_escala(coint_prices, pair_model):
    """I1: el capital no puede cambiar las métricas relativas."""
    from botcito_core.backtest import run_backtest

    inicio, fin = _rango(coint_prices)
    chico = run_backtest(coint_prices, pair_model, inicio, fin, capital=10_000.0)
    grande = run_backtest(coint_prices, pair_model, inicio, fin, capital=1_000_000.0)

    for clave in ("sharpe_ratio", "total_return", "max_drawdown", "win_rate"):
        assert chico[clave] == pytest.approx(grande[clave], abs=1e-9), clave


@pytest.mark.spec
@pytest.mark.xfail(reason=PENDIENTE, strict=True)
def test_ac3_pnl_escala_linealmente(coint_prices, pair_model):
    """I2: el PnL en dólares escala con el capital."""
    from botcito_core.backtest import run_backtest

    inicio, fin = _rango(coint_prices)
    base = run_backtest(coint_prices, pair_model, inicio, fin, capital=10_000.0)
    doble = run_backtest(coint_prices, pair_model, inicio, fin, capital=20_000.0)

    assert doble["total_pnl"] == pytest.approx(2 * base["total_pnl"], rel=1e-9)


@pytest.mark.spec
@pytest.mark.xfail(reason=PENDIENTE, strict=True)
def test_ac4_costos_por_leg(coint_prices, pair_model):
    """Los 4 legs se cobran sobre el notional de cada leg, recomputable."""
    from botcito_core.backtest import run_backtest

    inicio, fin = _rango(coint_prices)
    costo = 0.001
    sin_costo = run_backtest(coint_prices, pair_model, inicio, fin, capital=10_000.0,
                             transaction_cost=0.0)
    con_costo = run_backtest(coint_prices, pair_model, inicio, fin, capital=10_000.0,
                             transaction_cost=costo)

    cerrados = _trades_cerrados(con_costo)
    assert cerrados, "el escenario debe cerrar al menos un trade"

    esperado = sum(
        costo * (
            t["shares_a"] * t["price_a_entry"] + t["shares_b"] * t["price_b_entry"]
            + t["shares_a"] * t["price_a_exit"] + t["shares_b"] * t["price_b_exit"]
        )
        for t in cerrados
    )
    assert sin_costo["total_pnl"] - con_costo["total_pnl"] == pytest.approx(esperado, rel=1e-9)

    # El costo de apertura en unidades de retorno es exactamente transaction_cost.
    primero = cerrados[0]
    notional_entrada = (
        primero["shares_a"] * primero["price_a_entry"]
        + primero["shares_b"] * primero["price_b_entry"]
    )
    assert costo * notional_entrada / 10_000.0 == pytest.approx(costo, rel=1e-9)


@pytest.mark.spec
@pytest.mark.xfail(reason=PENDIENTE, strict=True)
def test_ac5_retornos_por_periodo(coint_prices, pair_model):
    """I3: una observación por barra, 0.0 cuando está flat."""
    import numpy as np

    from botcito_core.backtest import run_backtest

    inicio, fin = _rango(coint_prices)
    resultado = run_backtest(coint_prices, pair_model, inicio, fin, capital=10_000.0)

    retornos = np.asarray(resultado["returns"])
    assert len(retornos) == len(coint_prices), (
        "la serie debe ser por período, no por trade"
    )
    assert (retornos == 0.0).any(), "las barras flat deben aportar exactamente 0.0"
    assert len(retornos) > resultado["total_trades"]


@pytest.mark.spec
@pytest.mark.xfail(reason=PENDIENTE, strict=True)
def test_ac6_max_drawdown_sobre_equity(coint_prices, pair_model):
    """I4: el drawdown se mide sobre la curva de equity, no sobre PnL por trade."""
    import numpy as np

    from botcito_core.backtest import run_backtest

    inicio, fin = _rango(coint_prices)
    resultado = run_backtest(coint_prices, pair_model, inicio, fin, capital=10_000.0)

    equity = np.asarray(resultado["equity_curve"])
    retornos = np.asarray(resultado["returns"])
    np.testing.assert_allclose(equity, np.cumprod(1 + retornos), rtol=1e-12)

    picos = np.maximum.accumulate(equity)
    esperado = float(((picos - equity) / picos).max())
    assert resultado["max_drawdown"] == pytest.approx(esperado, abs=1e-12)
    assert 0.0 <= resultado["max_drawdown"] <= 1.0


@pytest.mark.spec
@pytest.mark.xfail(reason=PENDIENTE, strict=True)
def test_ac7_pnl_en_dolares_caso_cerrado(coint_prices, pair_model):
    """I5 e I7: PnL recomputable desde los precios, notional de entrada == capital."""
    from botcito_core.backtest import run_backtest

    inicio, fin = _rango(coint_prices)
    capital = 10_000.0
    resultado = run_backtest(coint_prices, pair_model, inicio, fin, capital=capital,
                             transaction_cost=0.0)

    cerrados = _trades_cerrados(resultado)
    assert cerrados

    for trade in cerrados:
        notional = (
            trade["shares_a"] * trade["price_a_entry"]
            + trade["shares_b"] * trade["price_b_entry"]
        )
        assert notional == pytest.approx(capital, rel=1e-9), "I7: notional != capital"

        bruto = trade["posicion"] * (
            trade["shares_a"] * (trade["price_a_exit"] - trade["price_a_entry"])
            - trade["shares_b"] * (trade["price_b_exit"] - trade["price_b_entry"])
        )
        assert trade["pnl"] == pytest.approx(bruto, rel=1e-9)

    assert resultado["total_pnl"] == pytest.approx(
        sum(t["pnl"] for t in cerrados), rel=1e-9
    )


@pytest.mark.spec
@pytest.mark.xfail(reason=PENDIENTE, strict=True)
def test_ac8_errores_de_entrada(coint_prices, pair_model):
    from botcito_core.backtest import run_backtest

    inicio, fin = _rango(coint_prices)

    with pytest.raises(ValueError):
        run_backtest(coint_prices, pair_model, inicio, fin, capital=0.0)

    with pytest.raises(ValueError):
        run_backtest(coint_prices, pair_model, inicio, fin, capital=-1.0)

    with pytest.raises(ValueError):
        run_backtest(coint_prices, pair_model, inicio, fin, transaction_cost=-0.1)
