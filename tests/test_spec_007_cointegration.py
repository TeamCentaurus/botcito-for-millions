"""
SPEC-007 — Engle-Granger bidireccional / Johansen.

Ver `docs/specs/007-cointegracion-bidireccional.md`.

AC4 y AC5 pasan HOY (el test detecta pares cointegrados y rechaza independientes):
son guardas de regresión. El resto es el trabajo pendiente.
"""

from __future__ import annotations

import pytest

import synthetic as syn

PENDIENTE = "SPEC-007 no implementada"


@pytest.mark.spec
@pytest.mark.xfail(reason=PENDIENTE, strict=True)
def test_ac1_simetria_del_veredicto():
    """I1: el veredicto no puede depender del orden de los argumentos."""
    from botcito_core.statistical_validation import test_cointegration

    # El par independiente es el que discrimina: hoy reporta 0.9794 en A~B y 0.7966
    # en B~A, así que el p_value publicado depende del orden de los argumentos.
    for price_a, price_b in (
        syn.independent_pair(n=500, seed=3),
        syn.cointegrated_pair(beta=2.0, alpha=10.0, theta=0.1, n=500, seed=2),
    ):
        directo = test_cointegration(price_a, price_b)
        inverso = test_cointegration(price_b, price_a)

        assert bool(directo["cointegrado"]) == bool(inverso["cointegrado"])
        assert directo["p_value"] == pytest.approx(inverso["p_value"], abs=1e-12)


@pytest.mark.spec
@pytest.mark.xfail(reason=PENDIENTE, strict=True)
def test_ac2_reporta_ambas_direcciones():
    from botcito_core.statistical_validation import test_cointegration

    # Par independiente: la asimetría de Engle-Granger es grande y observable
    # (medido sobre el código actual: 0.9794 en A~B vs 0.7966 en B~A).
    price_a, price_b = syn.independent_pair(n=500, seed=3)
    resultado = test_cointegration(price_a, price_b)

    for clave in ("p_value_ab", "p_value_ba", "direccion", "metodo"):
        assert clave in resultado, f"falta la clave {clave}"

    assert resultado["p_value_ab"] != resultado["p_value_ba"], (
        "este par tiene asimetría medible: si son iguales, no se está probando B~A"
    )
    assert resultado["direccion"] in ("a~b", "b~a")
    assert resultado["metodo"] == "engle-granger"


@pytest.mark.spec
@pytest.mark.xfail(reason=PENDIENTE, strict=True)
def test_ac3_correccion_bonferroni():
    """I2 e I3: p_value = min(1, 2*min(ab, ba)) y nunca más permisivo que el mínimo."""
    from botcito_core.statistical_validation import test_cointegration

    price_a, price_b = syn.independent_pair(n=500, seed=3)
    resultado = test_cointegration(price_a, price_b)

    minimo = min(resultado["p_value_ab"], resultado["p_value_ba"])
    assert resultado["p_value"] == pytest.approx(min(1.0, 2 * minimo), abs=1e-12)
    assert resultado["p_value"] >= minimo


@pytest.mark.spec
def test_ac4_detecta_par_cointegrado():
    from botcito_core.statistical_validation import test_cointegration

    price_a, price_b = syn.cointegrated_pair(beta=2.0, alpha=10.0, theta=0.1, n=500, seed=2)
    resultado = test_cointegration(price_a, price_b, significance=0.05)

    assert resultado["cointegrado"], "debe detectar el par cointegrado"
    assert resultado["p_value"] < 0.05


@pytest.mark.spec
def test_ac5_rechaza_par_independiente():
    from botcito_core.statistical_validation import test_cointegration

    price_a, price_b = syn.independent_pair(n=500, seed=3)
    resultado = test_cointegration(price_a, price_b, significance=0.05)

    assert not resultado["cointegrado"], "no debe declarar cointegrado un par independiente"
    assert resultado["p_value"] >= 0.05


@pytest.mark.spec
@pytest.mark.xfail(reason=PENDIENTE, strict=True)
def test_ac6_metodo_johansen():
    from botcito_core.statistical_validation import test_cointegration

    price_a, price_b = syn.cointegrated_pair(beta=2.0, alpha=10.0, theta=0.1, n=500, seed=2)
    johansen = test_cointegration(price_a, price_b, method="johansen")
    engle = test_cointegration(price_a, price_b)

    # I4: mismas claves para ambos métodos, para no romper consumidores.
    assert set(johansen) == set(engle)
    assert johansen["metodo"] == "johansen"
    assert johansen["direccion"] is None
    assert johansen["cointegrado"], "Johansen debe detectar el par cointegrado"


@pytest.mark.spec
@pytest.mark.xfail(reason=PENDIENTE, strict=True)
def test_ac7_errores_de_entrada():
    from botcito_core.statistical_validation import test_cointegration

    price_a, price_b = syn.cointegrated_pair(n=500, seed=2)

    with pytest.raises(ValueError):
        test_cointegration(price_a, price_b, method="chamuyo")

    with pytest.raises(ValueError):
        test_cointegration(price_a, price_b.iloc[:100])

    with pytest.raises(ValueError):
        test_cointegration(price_a.iloc[:20], price_b.iloc[:20])
