# SPEC-001 — Correlación: snapshot, no rolling

- **Estado:** Borrador
- **Origen:** `docs/METHODOLOGY.md` §P0.1
- **ADRs relacionados:** ADR-0002 (ventana de 252 para daily)
- **Timeframe objetivo:** daily
- **Archivos afectados:** `src/botcito_core/statistical_validation.py`

## 1. Problema

```python
# statistical_validation.py:11-17
def compute_correlation_matrix(prices: pd.DataFrame, window: int = 252) -> pd.DataFrame:
    """
    Calcula correlación de Pearson sobre ventana rodante.
    window=252 es un año bursátil para datos diarios.
    """
    returns = np.log(prices / prices.shift(1)).dropna()
    return returns.tail(window).corr()
```

El nombre y el docstring dicen **"ventana rodante"**. El cuerpo calcula **una sola
matriz** sobre los últimos `window` retornos: `tail(window).corr()`. No hay nada
rodante.

Dos riesgos concretos:

1. **Look-ahead silencioso.** Si el caller pasa un `prices` que incluye el período de
   validación o test, la correlación se calcula con datos del futuro y el pre-filtro
   de pares queda contaminado. Nada en la firma ni en el docstring advierte que el
   caller es responsable de recortar.
2. **Ventana no satisfecha sin aviso.** Con menos de `window` retornos disponibles,
   `tail(window)` devuelve lo que haya y `corr()` calcula sobre eso. El caller cree
   que midió un año y midió tres semanas. No hay error ni warning.

No hay ningún consumidor de esta función dentro del repo (`grep` solo encuentra su
definición); el único uso es `notebooks/01_selector_pairs.ipynb`, que es local y está
en `.gitignore`. Por eso el rename puede ser limpio, sin alias de compatibilidad.

## 2. Decisión metodológica

Renombrar a lo que la función **hace**: un snapshot de correlación sobre las últimas
`window` observaciones. El contrato pasa a ser explícito sobre la responsabilidad del
caller, y la ventana insatisfecha pasa de silenciosa a error.

No se implementa correlación rodante de verdad: nadie la necesita hoy, y
`returns.rolling(window).corr()` produce un panel 3D caro que no tiene consumidor.
Queda en `BACKLOG.md`.

## 3. Contrato

```python
def compute_correlation_snapshot(prices: pd.DataFrame, window: int = 252) -> pd.DataFrame:
    """
    Correlación de Pearson de log-returns sobre las últimas `window` observaciones.

    NO es una correlación rodante: devuelve UNA matriz, calculada sobre la cola de la
    serie. El caller es responsable de pasar únicamente precios del período de
    entrenamiento — pasar precios que incluyan validación o test introduce look-ahead.
    """
```

**Invariantes:**

- **I1** — El resultado es una matriz cuadrada `(n_tickers, n_tickers)` con el mismo
  orden de columnas que `prices`.
- **I2** — Simétrica, con diagonal exactamente `1.0`.
- **I3** — El resultado depende **solo** de los últimos `window` log-returns.
  Añadir observaciones más antiguas (anteriores a esa cola) no cambia el resultado.
- **I4** — Función pura: no muta `prices`.

**Errores:**

- `ValueError` si el número de log-returns disponibles (`len(prices) - 1`) es menor
  que `window`. El mensaje debe indicar cuántos se pidieron y cuántos hay.
- `ValueError` si `prices` tiene menos de 2 columnas (no hay par que correlacionar).

`compute_correlation_matrix` **deja de existir**. Sin alias: no hay consumidores en el
repo y un alias deprecado solo prolonga el nombre equivocado.

## 4. Criterios de aceptación

- **AC1** — `compute_correlation_snapshot` existe en `botcito_core.statistical_validation`
  y `compute_correlation_matrix` ya no está expuesto.
- **AC2** — Para un `DataFrame` de dos series con relación lineal conocida, el valor
  fuera de diagonal coincide con el `corr()` de pandas sobre los mismos log-returns
  (caso numérico cerrado, tolerancia `1e-12`).
- **AC3** — Con `len(prices) - 1 < window` lanza `ValueError`, y el mensaje menciona
  ambos números.
- **AC4** — I2: diagonal `== 1.0` y matriz simétrica.
- **AC5** — I3: dado `prices` de 400 filas y `window=252`, el resultado es idéntico al
  de pasar solo las últimas 253 filas.
- **AC6** — I4: `prices` no queda modificado tras la llamada (comparación con una copia).

## 5. Verificación

- **Archivo:** `tests/test_spec_001_correlation.py`
- **Comando:** `uv run pytest tests/test_spec_001_correlation.py -v`

| AC | Test |
|---|---|
| AC1 | `test_ac1_funcion_renombrada` |
| AC2 | `test_ac2_valor_numerico_correcto` |
| AC3 | `test_ac3_ventana_insuficiente_falla` |
| AC4 | `test_ac4_simetrica_diagonal_uno` |
| AC5 | `test_ac5_solo_depende_de_la_cola` |
| AC6 | `test_ac6_no_muta_input` |

## 6. Fuera de alcance

- Correlación rodante real (panel 3D) → `BACKLOG.md`.
- Cambiar `filter_by_correlation` (`statistical_validation.py:19-33`), que consume la
  matriz: su contrato no cambia. Nota: hoy filtra por `corr >= min_corr` sin valor
  absoluto, así que ignora pares fuertemente **anti**-correlacionados; eso es decisión
  de modelado y va al `BACKLOG.md`, no aquí.
- Validar que el caller realmente recortó a training. Imposible desde dentro de la
  función; se mitiga con el docstring y se verifica en SPEC-006 (split explícito).

## 7. Referencias

- Krauss (2017), *Statistical Arbitrage Pairs Trading Strategies: Review and Outlook*,
  §2 — el pre-filtro por correlación debe calcularse en una ventana anterior al
  período de evaluación.
