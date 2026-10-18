"""
SPEC-008 — Deduplicar `compute_hedge_ratio`.

Ver `docs/specs/008-deduplicar-hedge-ratio.md`.

AC3, AC4 y AC5 pasan HOY: son guardas de regresión que verifican que la
deduplicación no cambia el comportamiento. AC1, AC2 y AC6 son el trabajo pendiente.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

import pytest

import synthetic as syn

PENDIENTE = "SPEC-008 no implementada"
CORE = Path(__file__).resolve().parents[1] / "src" / "botcito_core"


@pytest.mark.spec
@pytest.mark.xfail(reason=PENDIENTE, strict=True)
def test_ac1_misma_funcion():
    from botcito_core import spread_calculator, statistical_validation

    assert (
        statistical_validation.compute_hedge_ratio is spread_calculator.compute_hedge_ratio
    ), "statistical_validation debe importar la función, no redefinirla"


@pytest.mark.spec
@pytest.mark.xfail(reason=PENDIENTE, strict=True)
def test_ac2_una_sola_definicion():
    fuentes = "\n".join(p.read_text() for p in sorted(CORE.glob("*.py")))

    assert len(re.findall(r"^def compute_hedge_ratio", fuentes, re.M)) == 1
    assert len(re.findall(r"^def _kalman_hedge_ratio", fuentes, re.M)) == 1


@pytest.mark.spec
def test_ac3_sin_cambio_funcional():
    """El hedge ratio OLS debe seguir recuperando el beta verdadero del generador."""
    from botcito_core.spread_calculator import compute_hedge_ratio

    price_a, price_b = syn.cointegrated_pair(beta=2.0, alpha=10.0, n=500, seed=2)

    primera = compute_hedge_ratio(price_a, price_b, method="ols")
    segunda = compute_hedge_ratio(price_a, price_b, method="ols")

    assert primera == pytest.approx(2.0, abs=0.05)
    assert primera == segunda, "el cálculo debe ser determinista"


@pytest.mark.spec
@pytest.mark.parametrize(
    "orden",
    [
        ("botcito_core.spread_calculator", "botcito_core.statistical_validation"),
        ("botcito_core.statistical_validation", "botcito_core.spread_calculator"),
    ],
)
def test_ac4_sin_import_circular(orden):
    """Importables en cualquier orden, en procesos limpios."""
    codigo = f"import {orden[0]}; import {orden[1]}"
    resultado = subprocess.run(
        [sys.executable, "-c", codigo],
        capture_output=True,
        text=True,
        cwd=Path(__file__).resolve().parents[1],
    )
    assert resultado.returncode == 0, resultado.stderr


@pytest.mark.spec
def test_ac5_humo_screen_pair_y_train():
    """`screen_pair` y `model.train` siguen corriendo end-to-end."""
    from botcito_core.model import train
    from botcito_core.statistical_validation import screen_pair

    price_a, price_b = syn.cointegrated_pair(beta=2.0, alpha=10.0, n=500, seed=2)
    prices = syn.price_frame(A=price_a, B=price_b)

    resultado = screen_pair(prices, "A", "B")
    assert resultado["hedge_ratio"] == pytest.approx(2.0, abs=0.05)

    train_end = str(prices.index[300].date())
    modelo = train(prices, "A", "B", train_end=train_end)
    # Tolerancia más holgada: sobre 300 barras el estimador OLS se desvía más que
    # sobre las 500 completas. El punto del humo es que corre end-to-end.
    assert modelo.hedge_ratio == pytest.approx(2.0, abs=0.25)
    assert modelo.ticker_a == "A" and modelo.ticker_b == "B"


@pytest.mark.spec
@pytest.mark.xfail(reason=PENDIENTE, strict=True)
def test_ac6_sin_imports_duplicados():
    lineas = (CORE / "statistical_validation.py").read_text().splitlines()
    imports = [ln.strip() for ln in lineas if ln.startswith(("import ", "from "))]

    assert len(imports) == len(set(imports)), f"imports duplicados: {imports}"
