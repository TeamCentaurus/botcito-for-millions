# SPEC-007 — Engle-Granger bidireccional / Johansen

- **Estado:** Descartada — obsoleta por ADR-0005 (aceptado 2026-10-15, Opción A): el código sobre el que actúa se borra con el pivote
- **Origen:** `docs/METHODOLOGY.md` §P0.6
- **ADRs relacionados:** ninguno
- **Timeframe objetivo:** daily
- **Archivos afectados:** `src/botcito_core/statistical_validation.py`

## 1. Problema

```python
# statistical_validation.py:36-53
def test_cointegration(price_a, price_b, significance=0.05) -> dict:
    score, pvalue, critical_values = coint(price_a, price_b)
    return {"cointegrado": pvalue < significance, ...}
```

`statsmodels.tsa.stattools.coint(a, b)` regresa **A sobre B** y aplica ADF al residuo.
Regresar **B sobre A** da un p-value distinto — el test no es simétrico. Consecuencia:
el veredicto "este par es cointegrado" puede depender de en qué orden se escribieron
los tickers, y `screen_pair` (`statistical_validation.py:145`) llama siempre
`test_cointegration(p_a, p_b)` con el orden en que vinieron los argumentos.

Un par puede entrar o quedar fuera del universo tradeable por una decisión de
nomenclatura. Eso no es un criterio estadístico.

## 2. Decisión metodológica

Probar **ambas direcciones** y reportar las dos. El veredicto usa el p-value menor,
**corregido por los dos tests** con Bonferroni (`p_eff = min(1, 2 · p_min)`): tomar el
mínimo de dos p-values sin corregir infla el error tipo I — es exactamente el sesgo
que SPEC-002 corrige a nivel de universo, y sería incoherente cometerlo dentro de cada
par.

Adicionalmente se ofrece `method="johansen"`, que no requiere elegir variable
dependiente y es la respuesta robusta al problema. Se deja como opción y no como
default porque cambia el criterio de selección de pares (decisión de modelado, no de
correctitud) y requiere revalidar el universo.

## 3. Contrato

```python
def test_cointegration(price_a: pd.Series, price_b: pd.Series,
                       significance: float = 0.05,
                       method: str = "engle-granger") -> dict:
    """
    method="engle-granger": prueba A~B y B~A, reporta ambos p-values y usa el menor
        corregido por Bonferroni (2 tests) para el veredicto.
    method="johansen": test de Johansen (trace statistic, det_order=0, k_ar_diff=1),
        sin dirección.
    """
```

Claves del dict devuelto:

| Clave | Tipo | Significado |
|---|---|---|
| `cointegrado` | `bool` | `p_value < significance` |
| `p_value` | `float` | p-value **efectivo** (corregido) usado en el veredicto |
| `p_value_ab` | `float \| None` | A~B sin corregir (`None` con Johansen) |
| `p_value_ba` | `float \| None` | B~A sin corregir (`None` con Johansen) |
| `direccion` | `str \| None` | `"a~b"` o `"b~a"`: la que dio el p-value menor |
| `estadistico` | `float` | Estadístico del test elegido |
| `valores_criticos` | `np.ndarray` | Valores críticos del test elegido |
| `metodo` | `str` | Método efectivamente usado |
| `interpretacion` | `str` | `"PAR VÁLIDO"` / `"DESCARTAR"` |

**Invariantes:**

- **I1 (simetría)** — `test_cointegration(a, b)` y `test_cointegration(b, a)` devuelven
  el mismo `cointegrado` y el mismo `p_value`. Los campos `p_value_ab`/`p_value_ba` se
  intercambian y `direccion` se invierte, pero el **veredicto no depende del orden**.
- **I2** — `p_value == min(1.0, 2 * min(p_value_ab, p_value_ba))` con Engle-Granger.
- **I3** — `p_value >= min(p_value_ab, p_value_ba)`: la corrección nunca hace el
  veredicto más permisivo.
- **I4** — Las claves del dict son las mismas para ambos métodos (los campos no
  aplicables van en `None`), para que los consumidores no se rompan al cambiar método.

**Errores:**

- `ValueError` si `method` no es `"engle-granger"` ni `"johansen"`.
- `ValueError` si las series tienen longitudes distintas o menos de 30 observaciones
  (los tests no son informativos y `coint` puede fallar de forma opaca).

## 4. Criterios de aceptación

- **AC1 (I1)** — Para un par sintético cointegrado, invertir el orden de los
  argumentos no cambia `cointegrado` ni `p_value`.
- **AC2** — El dict contiene `p_value_ab`, `p_value_ba`, `direccion` y `metodo`, y
  `p_value_ab != p_value_ba` para un par real (demuestra que la asimetría existe y que
  se está midiendo).
- **AC3 (I2)** — `p_value` es exactamente `min(1.0, 2 * min(ab, ba))`.
- **AC4** — `cointegrated_pair(beta=2.0, theta=0.1)` se declara cointegrado a
  `significance=0.05`.
- **AC5** — `independent_pair()` (dos random walks independientes, seed fija) **no** se
  declara cointegrado.
- **AC6** — `method="johansen"` devuelve el mismo conjunto de claves, con
  `direccion is None` y `metodo == "johansen"`, y declara cointegrado el par sintético
  cointegrado.
- **AC7** — `method="chamuyo"` lanza `ValueError`; series de longitudes distintas
  lanzan `ValueError`.

## 5. Verificación

- **Archivo:** `tests/test_spec_007_cointegration.py`
- **Comando:** `uv run pytest tests/test_spec_007_cointegration.py -v`

| AC | Test |
|---|---|
| AC1 | `test_ac1_simetria_del_veredicto` |
| AC2 | `test_ac2_reporta_ambas_direcciones` |
| AC3 | `test_ac3_correccion_bonferroni` |
| AC4 | `test_ac4_detecta_par_cointegrado` |
| AC5 | `test_ac5_rechaza_par_independiente` |
| AC6 | `test_ac6_metodo_johansen` |
| AC7 | `test_ac7_errores_de_entrada` |

## 6. Fuera de alcance

- Hacer de Johansen el método por defecto → decisión de modelado, `BACKLOG.md`.
- Cointegración de más de 2 series (cestas) → `BACKLOG.md`.
- La corrección FDR **entre pares** → SPEC-002. Este spec corrige solo los 2 tests
  internos de un par.

## 7. Referencias

- Engle & Granger (1987), *Co-integration and Error Correction*, Econometrica 55(2) —
  el test original y su dependencia de la variable dependiente elegida.
- Johansen (1991), *Estimation and Hypothesis Testing of Cointegration Vectors*,
  Econometrica 59(6) — test sin variable dependiente.
- Krauss (2017), §3 — discusión práctica de la asimetría de Engle-Granger en screening
  de pares.
