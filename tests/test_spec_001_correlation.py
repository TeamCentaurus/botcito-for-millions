"""
SPEC-001 — Correlación: snapshot, no rolling.

Ver `docs/specs/001-correlation-snapshot.md`. Los imports van dentro de cada test
para que la ausencia de la función produzca `xfail` y no un error de colección.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

import synthetic as syn

PENDIENTE = "SPEC-001 no implementada"


@pytest.mark.spec
@pytest.mark.xfail(reason=PENDIENTE, strict=True)
def test_ac1_funcion_renombrada():
    from botcito_core import statistical_validation as sv

    assert hasattr(sv, "compute_correlation_snapshot")
    assert not hasattr(sv, "compute_correlation_matrix"), (
        "el nombre viejo no debe seguir expuesto: no hay consumidores en el repo"
    )


@pytest.mark.spec
@pytest.mark.xfail(reason=PENDIENTE, strict=True)
def test_ac2_valor_numerico_correcto():
    from botcito_core.statistical_validation import compute_correlation_snapshot

    price_a, price_b = syn.cointegrated_pair(n=400, seed=5)
    prices = syn.price_frame(A=price_a, B=price_b)

    window = 252
    esperado = np.log(prices / prices.shift(1)).dropna().tail(window).corr()
    obtenido = compute_correlation_snapshot(prices, window=window)

    pd.testing.assert_frame_equal(obtenido, esperado, atol=1e-12, rtol=0)


@pytest.mark.spec
@pytest.mark.xfail(reason=PENDIENTE, strict=True)
def test_ac3_ventana_insuficiente_falla():
    from botcito_core.statistical_validation import compute_correlation_snapshot

    price_a, price_b = syn.cointegrated_pair(n=100, seed=5)
    prices = syn.price_frame(A=price_a, B=price_b)

    with pytest.raises(ValueError) as exc:
        compute_correlation_snapshot(prices, window=252)

    mensaje = str(exc.value)
    assert "252" in mensaje and "99" in mensaje, (
        f"el error debe decir cuántos retornos se pidieron y cuántos hay: {mensaje!r}"
    )


@pytest.mark.spec
@pytest.mark.xfail(reason=PENDIENTE, strict=True)
def test_ac4_simetrica_diagonal_uno():
    from botcito_core.statistical_validation import compute_correlation_snapshot

    universe = syn.independent_universe(n_tickers=5, n=400, seed=1)
    matriz = compute_correlation_snapshot(universe, window=252)

    assert matriz.shape == (5, 5)
    assert list(matriz.columns) == list(universe.columns)
    np.testing.assert_allclose(np.diag(matriz.to_numpy()), 1.0, atol=1e-12)
    np.testing.assert_allclose(matriz.to_numpy(), matriz.to_numpy().T, atol=1e-12)


@pytest.mark.spec
@pytest.mark.xfail(reason=PENDIENTE, strict=True)
def test_ac5_solo_depende_de_la_cola():
    """I3: añadir historia más antigua que la ventana no cambia el resultado."""
    from botcito_core.statistical_validation import compute_correlation_snapshot

    universe = syn.independent_universe(n_tickers=4, n=400, seed=2)
    window = 252

    completo = compute_correlation_snapshot(universe, window=window)
    # 253 filas de precios → 252 log-returns, exactamente la ventana.
    solo_cola = compute_correlation_snapshot(universe.tail(window + 1), window=window)

    pd.testing.assert_frame_equal(completo, solo_cola, atol=1e-12, rtol=0)


@pytest.mark.spec
@pytest.mark.xfail(reason=PENDIENTE, strict=True)
def test_ac6_no_muta_input():
    from botcito_core.statistical_validation import compute_correlation_snapshot

    universe = syn.independent_universe(n_tickers=3, n=400, seed=3)
    copia = universe.copy(deep=True)

    compute_correlation_snapshot(universe, window=252)

    pd.testing.assert_frame_equal(universe, copia)
