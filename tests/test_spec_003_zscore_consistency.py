"""
SPEC-003 — z-score consistente: backtest ≡ live.

Ver `docs/specs/003-zscore-consistente-backtest-live.md`.
ADR-0001 fue aceptado el 2026-10-12 con la Opción A (rolling en backtest y en live),
así que estos tests reflejan la decisión vigente, no una hipótesis.

AC2 y AC3 pasan HOY: `compute_zscore` ya es causal. Son guardas de regresión que
impiden que la implementación de este spec rompa la causalidad.

NOTA: `botcito_core.monitoring` NO se puede importar (tiene imports rotos y un
`while True` en el cuerpo del módulo), así que AC6 inspecciona el fuente.
"""

from __future__ import annotations

import re
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

import synthetic as syn

PENDIENTE = "SPEC-003 no implementada"
CORE = Path(__file__).resolve().parents[1] / "src" / "botcito_core"


def _zscore_live(spread: pd.Series, window: int) -> pd.Series:
    """
    Simula el live: en cada barra t calcula el z-score con datos solo hasta t.
    Es la referencia contra la que el backtest tiene que coincidir.
    """
    from botcito_core.spread_calculator import compute_zscore

    valores = []
    for t in range(len(spread)):
        prefijo = spread.iloc[: t + 1]
        if len(prefijo) < window:
            valores.append(np.nan)
        else:
            valores.append(compute_zscore(prefijo, window=window).iloc[-1])
    return pd.Series(valores, index=spread.index, name="zscore")


@pytest.mark.spec
@pytest.mark.xfail(reason=PENDIENTE, strict=True)
def test_ac1_live_equivale_a_backtest(coint_prices, pair_model):
    """I1: el z-score del backtest es el que el live habría calculado barra a barra."""
    from botcito_core.backtest import run_backtest

    inicio = str(coint_prices.index[0].date())
    fin = str(coint_prices.index[-1].date())
    resultado = run_backtest(coint_prices, pair_model, inicio, fin)

    assert "zscore" in resultado, "el backtest debe exponer el z-score que usó"

    spread = coint_prices["A"] - pair_model.hedge_ratio * coint_prices["B"]
    esperado = _zscore_live(spread, pair_model.zscore_window)

    pd.testing.assert_series_equal(
        pd.Series(resultado["zscore"]).astype(float),
        esperado.astype(float),
        check_names=False,
        atol=1e-12,
    )


@pytest.mark.spec
def test_ac2_causalidad_por_truncamiento(coint_prices, pair_model):
    """I2: z_t es igual calculado sobre la serie completa o truncada en t."""
    from botcito_core.spread_calculator import compute_zscore

    spread = coint_prices["A"] - pair_model.hedge_ratio * coint_prices["B"]
    window = pair_model.zscore_window
    completo = compute_zscore(spread, window=window)

    for t in (100, 250, 400, len(spread) - 1):
        truncado = compute_zscore(spread.iloc[: t + 1], window=window)
        assert truncado.iloc[-1] == pytest.approx(completo.iloc[t], abs=1e-12)


@pytest.mark.spec
def test_ac3_futuro_no_afecta_pasado(coint_prices, pair_model):
    """I2, versión destructiva: corromper el futuro no cambia el pasado."""
    from botcito_core.spread_calculator import compute_zscore

    window = pair_model.zscore_window
    corte = coint_prices.index[300]
    corrompido = syn.corrupt_after(coint_prices, str(corte.date()))

    def z(frame):
        spread = frame["A"] - pair_model.hedge_ratio * frame["B"]
        return compute_zscore(spread, window=window)

    original, alterado = z(coint_prices), z(corrompido)

    pd.testing.assert_series_equal(original.loc[:corte], alterado.loc[:corte], atol=1e-12)


@pytest.mark.spec
@pytest.mark.xfail(reason=PENDIENTE, strict=True)
def test_ac4_sin_trades_en_warmup(coint_prices, pair_model):
    """I3: durante las primeras (window - 1) barras el z es NaN y no hay señal."""
    from botcito_core.backtest import run_backtest

    inicio = str(coint_prices.index[0].date())
    fin = str(coint_prices.index[-1].date())
    resultado = run_backtest(coint_prices, pair_model, inicio, fin)

    primera_barra_valida = coint_prices.index[pair_model.zscore_window - 1]
    aperturas = [t for t in resultado["trades"] if str(t["type"]).startswith("OPEN")]
    assert aperturas, "el escenario debe generar al menos un trade para ser informativo"

    for trade in aperturas:
        assert pd.Timestamp(trade["date"]) >= primera_barra_valida, (
            f"trade abierto en warmup: {trade}"
        )


@pytest.mark.spec
@pytest.mark.xfail(reason=PENDIENTE, strict=True)
def test_ac5_backtest_ignora_stats_estaticos(coint_prices, pair_model):
    """
    I4: con z rolling, `spread_mean`/`spread_std` son diagnóstico, no insumo.
    Ponerlos en valores absurdos no debe cambiar ningún resultado.
    """
    import dataclasses

    from botcito_core.backtest import run_backtest

    inicio = str(coint_prices.index[0].date())
    fin = str(coint_prices.index[-1].date())

    normal = run_backtest(coint_prices, pair_model, inicio, fin)
    absurdo = run_backtest(
        coint_prices,
        dataclasses.replace(pair_model, spread_mean=1e9, spread_std=1e9),
        inicio,
        fin,
    )

    for clave in ("total_trades", "sharpe_ratio", "win_rate", "max_drawdown"):
        assert normal[clave] == pytest.approx(absurdo[clave], abs=1e-12), (
            f"{clave} depende de los estadísticos estáticos del training"
        )


@pytest.mark.spec
@pytest.mark.xfail(reason=PENDIENTE, strict=True)
def test_ac6_misma_funcion_en_live_y_backtest():
    """I5: live y backtest resuelven compute_zscore al mismo módulo."""
    patron = re.compile(
        r"from\s+botcito_core\.spread_calculator\s+import\s+[^\n]*compute_zscore"
    )

    for modulo in ("backtest.py", "monitoring.py"):
        fuente = (CORE / modulo).read_text()
        assert patron.search(fuente), (
            f"{modulo} debe importar compute_zscore de botcito_core.spread_calculator"
        )


@pytest.mark.spec
@pytest.mark.xfail(reason=PENDIENTE, strict=True)
def test_ac7_errores_de_ventana(coint_prices, pair_model):
    from botcito_core.spread_calculator import compute_zscore

    spread = coint_prices["A"] - pair_model.hedge_ratio * coint_prices["B"]

    with pytest.raises(ValueError):
        compute_zscore(spread, window=1)

    with pytest.raises(ValueError):
        compute_zscore(spread.iloc[:10], window=30)


@pytest.mark.spec
@pytest.mark.xfail(reason=PENDIENTE, strict=True)
def test_ac8_pairmodel_documenta_diagnostico():
    """Sin la nota en el docstring, spread_mean/std se vuelven a usar por error."""
    from botcito_core.types import PairModel

    doc = (PairModel.__doc__ or "").lower()
    assert "diagn" in doc, "el docstring debe marcar spread_mean/spread_std como diagnóstico"
    assert "señal" in doc or "senal" in doc
