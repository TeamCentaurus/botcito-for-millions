# SPEC-010 — Loader de precios

- **Estado:** Implementada ✅
- **Aceptada por:** Leonel, 2026-10-12
- **Implementada:** 2026-10-12
- **Origen:** pedido de sesión (2026-10-12) — el notebook debe quedar como orquestador
- **ADRs relacionados:** ADR-0002 (daily)
- **Timeframe objetivo:** daily
- **Archivos afectados:** `src/botcito_core/data_loader.py` (nuevo)

## 1. Problema

La carga de precios vive en la **celda 1** de `notebooks/01_selector_pairs.ipynb`:

```python
def load_prices(df: pd.DataFrame) -> pd.DataFrame:
    df = df.dropna(thresh=int(len(df) * 0.95), axis=1)   # descarta columnas con >5% faltante
    ...  # forward-fill
```

Consecuencias concretas:

1. **Nada lo puede reusar.** Ni un test, ni un DAG, ni un script. Cada consumidor
   reimplementa la higiene de datos, y dos higienes distintas producen universos
   distintos a partir de la misma descarga.
2. **`monitoring.py:4` importa `from src.data_loader import load_prices`** — un módulo
   que no existe. El import está roto desde que el layout pasó a `src/botcito_core/`.
3. **La higiene no está verificada.** El umbral de 95% de cobertura decide qué tickers
   entran al universo; si descarta de más o de menos, cambia el screening entero y nadie
   se enteraría.

## 2. Decisión metodológica

Separar **descarga** de **higiene**, porque tienen testabilidad opuesta:

- `clean_prices` es una función pura sobre un `DataFrame`: se verifica por completo con
  datos construidos a mano, sin red.
- `load_yfinance` es un wrapper delgado sobre `yf.download`: se verifica que traduzca
  bien (columnas, parámetros) con la descarga monkeypatcheada, no con la red.

Esa separación es el punto del spec. Un loader monolítico que descarga y limpia en la
misma función solo se puede testear con red, y un test con red no es un test.

La higiene replica la del notebook (umbral 95% + forward-fill) para no cambiar en
silencio qué tickers sobreviven, pero con el umbral como parámetro explícito.

## 3. Contrato

```python
def clean_prices(raw: pd.DataFrame, min_coverage: float = 0.95) -> pd.DataFrame:
    """
    Higiene de un panel de precios:
      1. Descarta columnas con cobertura < min_coverage (fracción de valores no nulos).
      2. Forward-fill de huecos internos.
      3. Descarta las filas iniciales que sigan incompletas tras el ffill.
    Función pura: no muta `raw`.
    """

def load_yfinance(tickers: list[str], start: str, end: str | None = None,
                  interval: str = "1d", min_coverage: float = 0.95) -> pd.DataFrame:
    """
    Descarga precios de cierre ajustado con yfinance y aplica `clean_prices`.
    Devuelve un DataFrame con una columna por ticker e índice de fechas.
    """
```

**Invariantes:**

- **I1** — `clean_prices` no muta `raw`.
- **I2** — Una columna con cobertura `< min_coverage` no está en el resultado; una con
  cobertura `>= min_coverage`, sí.
- **I3** — El resultado no tiene `NaN`.
- **I4** — El índice del resultado es un `DatetimeIndex` ordenado y sin duplicados.
- **I5** — `load_yfinance` aplana las columnas `MultiIndex` de yfinance quedándose con
  el nivel `Close`, y el resultado tiene una columna por ticker pedido que sobreviva la
  higiene.
- **I6** — `load_yfinance` pasa `auto_adjust` explícitamente, no por default. El default
  de yfinance cambió a `True` y el ajuste reescribe la historia hacia atrás, lo cual
  afecta la cointegración sobre niveles: tiene que ser una decisión visible en el código.

**Errores:**

- `ValueError` si `raw` está vacío, o si tras la higiene quedan menos de 2 columnas
  (no hay par posible).
- `ValueError` si `min_coverage` no está en `(0, 1]`.
- `ValueError` si `tickers` está vacío.
- `ValueError` si la descarga vuelve vacía.

## 4. Criterios de aceptación

- **AC1 (I2)** — Panel con una columna al 100%, una al 96% y una al 50%: con
  `min_coverage=0.95` sobreviven las dos primeras y se descarta la tercera.
- **AC2 (I3)** — El resultado no tiene `NaN`, con huecos internos y huecos iniciales.
- **AC3 (I1)** — `raw` queda idéntico tras la llamada.
- **AC4 (I4)** — Con un índice desordenado y con un duplicado, el resultado sale
  ordenado y sin duplicados.
- **AC5** — `min_coverage` en `0`, `1.5` y `-0.1` lanza `ValueError`; `raw` vacío lanza
  `ValueError`; un panel que deja 1 sola columna lanza `ValueError`.
- **AC6 (I5)** — Con `yf.download` monkeypatcheado devolviendo columnas `MultiIndex`
  `(campo, ticker)`, `load_yfinance` devuelve una columna por ticker tomada de `Close`.
- **AC7 (I6)** — `load_yfinance` llama a `yf.download` con `auto_adjust` presente en los
  kwargs, y propaga `tickers`, `start`, `end` e `interval`.
- **AC8** — `tickers=[]` lanza `ValueError`; una descarga vacía lanza `ValueError`.

## 5. Verificación

- **Archivo:** `tests/test_spec_010_data_loader.py`
- **Comando:** `uv run pytest tests/test_spec_010_data_loader.py -v`

| AC | Test |
|---|---|
| AC1 | `test_ac1_descarta_por_cobertura` |
| AC2 | `test_ac2_sin_nan_en_el_resultado` |
| AC3 | `test_ac3_no_muta_input` |
| AC4 | `test_ac4_indice_ordenado_sin_duplicados` |
| AC5 | `test_ac5_errores_de_clean_prices` |
| AC6 | `test_ac6_aplana_multiindex_de_yfinance` |
| AC7 | `test_ac7_pasa_auto_adjust_explicito` |
| AC8 | `test_ac8_errores_de_load_yfinance` |

Ningún test toca la red. `load_yfinance` se verifica con `yf.download` monkeypatcheado.

## 6. Fuera de alcance

- **Backend de GCS** (leer los parquet que escribe la Cloud Function) → `BACKLOG.md`.
  El loader de producción es otro spec; este es el de laboratorio.
- **Arreglar los imports de `monitoring.py`** → `BACKLOG.md`. Este spec crea el módulo
  que ese import busca, pero refactorizar `monitoring.py` (que además ejecuta un
  `while True` al importarse) es trabajo aparte.
- **Resampleo** de 1-min a daily → `BACKLOG.md`, para cuando se use el dato de GCS.
- **Survivorship bias**: yfinance solo devuelve tickers vivos. No se puede resolver
  desde el loader; queda declarado como advertencia en el artefacto de la corrida.

## 7. Referencias

Ninguna metodológica. El antecedente es la celda 1 del notebook actual.
