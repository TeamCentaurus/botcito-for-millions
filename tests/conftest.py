"""
Fixtures compartidas del arnés de specs.

Todas las series son deterministas (seeds fijas): un AC que falla debe fallar siempre,
no una vez cada diez corridas. Los generadores viven en `tests/synthetic.py`.
"""

from __future__ import annotations

import pytest

from synthetic import (
    cointegrated_pair,
    independent_pair,
    independent_universe,
    price_frame,
)

# ---------------------------------------------------------------- precios

@pytest.fixture
def coint_prices():
    """Par cointegrado: hedge ratio verdadero 2.0, intercepto 10.0, half-life ~6.9 d."""
    price_a, price_b = cointegrated_pair(beta=2.0, alpha=10.0, theta=0.1, n=500, seed=2)
    return price_frame(A=price_a, B=price_b)


@pytest.fixture
def indep_prices():
    """Dos random walks independientes: no deben sobrevivir al screening."""
    price_a, price_b = independent_pair(n=500, seed=3)
    return price_frame(A=price_a, B=price_b)


@pytest.fixture
def indep_universe():
    """20 tickers independientes → 190 pares, todos falsos positivos potenciales."""
    return independent_universe(n_tickers=20, n=500, seed=0)


@pytest.fixture
def mixed_universe():
    """
    18 tickers independientes + 2 pares cointegrados construidos (C1A/C1B, C2A/C2B).
    22 tickers → 231 pares. Es el universo de SPEC-002 AC6.
    """
    universe = independent_universe(n_tickers=18, n=500, seed=0)
    c1_a, c1_b = cointegrated_pair(beta=2.0, alpha=10.0, theta=0.1, n=500, seed=11)
    c2_a, c2_b = cointegrated_pair(beta=1.5, alpha=8.0, theta=0.15, n=500, seed=33)
    frame = universe.copy()
    for name, series in [("C1A", c1_a), ("C1B", c1_b), ("C2A", c2_a), ("C2B", c2_b)]:
        frame[name] = series.to_numpy()
    return frame


@pytest.fixture
def true_pairs():
    """Los pares realmente cointegrados dentro de `mixed_universe`."""
    return {("C1A", "C1B"), ("C2A", "C2B")}


# ---------------------------------------------------------------- modelo

@pytest.fixture
def pair_model(coint_prices):
    """
    `PairModel` armado directamente, sin pasar por `model.train`.

    Así los tests de backtest no dependen de que `train` sea correcto: aíslan el
    módulo bajo prueba. El hedge ratio es el verdadero del generador (2.0).
    """
    from botcito_core.types import PairModel

    spread = coint_prices["A"] - 2.0 * coint_prices["B"]
    return PairModel(
        ticker_a="A",
        ticker_b="B",
        hedge_ratio=2.0,
        spread_mean=float(spread.mean()),
        spread_std=float(spread.std()),
        half_life=6.93,
        zscore_window=30,
        entry_threshold=2.0,
        exit_threshold=0.5,
        stop_loss_threshold=3.5,
    )
