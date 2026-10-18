"""
Guardas de regresión sobre comportamiento que YA es correcto.

Sin spec asociado: estos tests no describen trabajo pendiente, protegen lo que
funciona de los cambios que vienen (SPEC-003 toca la generación de señales y
SPEC-005 reescribe el bucle del backtest).
"""

from __future__ import annotations

import numpy as np
import pytest

from botcito_core.alerts import Signal, generate_signal


@pytest.mark.parametrize(
    ("zscore", "esperado"),
    [
        (0.0, Signal.CLOSE_POSITION),     # |z| < exit
        (0.4, Signal.CLOSE_POSITION),
        (-0.4, Signal.CLOSE_POSITION),
        (1.0, Signal.NEUTRAL),            # entre exit y entry: zona muerta
        (-1.0, Signal.NEUTRAL),
        (2.5, Signal.SHORT_A_LONG_B),     # z > +entry
        (-2.5, Signal.LONG_A_SHORT_B),    # z < -entry
        (4.0, Signal.STOP_LOSS),          # |z| > stop
        (-4.0, Signal.STOP_LOSS),
    ],
)
def test_precedencia_de_senales(pair_model, zscore, esperado):
    """El stop manda sobre la entrada, y la entrada sobre el cierre."""
    assert generate_signal(zscore, pair_model) is esperado


def test_stop_tiene_prioridad_sobre_entrada(pair_model):
    """
    Con |z| > stop, la señal debe ser STOP_LOSS aunque también supere entry.
    Si este test se rompe, el backtest abriría posiciones en divergencias extremas.
    """
    assert generate_signal(10.0, pair_model) is Signal.STOP_LOSS
    assert generate_signal(-10.0, pair_model) is Signal.STOP_LOSS


def test_nan_no_genera_senal(pair_model):
    """
    Durante el warmup del z-score rolling (SPEC-003) z es NaN. Hoy devuelve NEUTRAL
    porque todas las comparaciones con NaN son falsas: funciona por accidente, no por
    diseño. Este test fija el comportamiento para que SPEC-003 no lo rompa en silencio.
    """
    assert generate_signal(float("nan"), pair_model) is Signal.NEUTRAL
    assert generate_signal(np.nan, pair_model) is Signal.NEUTRAL
