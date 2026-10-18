# SPEC-006 — Hold-out test tras el tuning de umbrales

- **Estado:** Borrador
- **Origen:** `docs/METHODOLOGY.md` §P0.7
- **ADRs relacionados:** ADR-0002
- **Timeframe objetivo:** daily
- **Archivos afectados:** `src/botcito_core/model.py`
- **Depende de:** SPEC-004 y SPEC-005 (las métricas del hold-out solo valen si el Sharpe y el PnL ya son correctos)

## 1. Problema

```python
# model.py:76-89
for entry, exit_ in product(entry_range, exit_range):
    if exit_ >= entry:
        continue
    model.entry_threshold = entry      # ← MUTA el modelo recibido
    model.exit_threshold = exit_
    results = run_backtest(prices, model, val_start, val_end)
    sharpe = results["sharpe_ratio"]
    if sharpe > best_sharpe:
        best_sharpe = sharpe
        best_params = {"entry": entry, "exit": exit_, "sharpe": sharpe}
return best_params
```

Dos problemas, uno metodológico y uno de implementación:

**a) No hay hold-out.** Se hace grid search 3×3 maximizando Sharpe en validación y el
Sharpe reportado es **el de ese mismo período de validación**. Es el número que se
optimizó: está sesgado al alza por construcción. Con N pares × 9 combinaciones, el
máximo de N×9 evaluaciones ruidosas puede ser alto sin que haya ningún edge.

**b) `optimize_thresholds` muta el modelo y lo deja mal.** Asigna
`model.entry_threshold`/`exit_threshold` en cada iteración y **nunca restaura los
mejores**: al terminar, el `PairModel` del caller queda con la **última** combinación
probada del grid, no con la ganadora. Quien llame a `optimize_thresholds` y luego use
`model` está operando con umbrales arbitrarios. `PairModel` es un dataclass mutable sin
`frozen=True`, así que nada lo impide.

## 2. Decisión metodológica

Split explícito **train → val → test** con el test intacto durante todo el tuning, y
una función aparte que reporta las métricas finales **solo** sobre test.

Y `optimize_thresholds` pasa a ser **pura**: no muta el modelo recibido, devuelve los
mejores parámetros, y el caller los aplica con `dataclasses.replace`. Una función de
búsqueda que deja efectos secundarios en su entrada no es auditable.

El solapamiento entre rangos deja de ser responsabilidad del caller: se valida y falla.
Walk-forward con purging (P1.4) es la evolución correcta de esto, pero requiere
rediseñar el flujo completo y queda en `BACKLOG.md`; un hold-out único es el mínimo
que hace el número reportado honesto.

## 3. Contrato

```python
@dataclass(frozen=True)
class Split:
    """Fronteras temporales del flujo train → val → test. Fechas 'YYYY-MM-DD'."""
    train_end: str
    val_start: str
    val_end: str
    test_start: str
    test_end: str

def validate_split(split: Split) -> None:
    """Lanza ValueError si el orden temporal no es estrictamente train < val < test."""

def optimize_thresholds(prices: pd.DataFrame, model: PairModel,
                        val_start: str, val_end: str,
                        entry_range: tuple[float, ...] = (1.5, 2.0, 2.5),
                        exit_range: tuple[float, ...] = (0.0, 0.5, 1.0),
                        **backtest_kwargs) -> dict:
    """
    Grid search en VALIDACIÓN. Función pura: NO muta `model`.
    Devuelve {"entry", "exit", "sharpe_validacion", "n_combinaciones"}.
    El sharpe devuelto es IN-SAMPLE respecto al tuning: no reportarlo como resultado.
    """

def evaluate_holdout(prices: pd.DataFrame, model: PairModel,
                     test_start: str, test_end: str,
                     **backtest_kwargs) -> dict:
    """
    Métricas finales sobre el hold-out. Es el único número reportable como
    performance esperada.
    """
```

**Invariantes:**

- **I1 (pureza)** — Tras `optimize_thresholds`, el `PairModel` recibido es igual al de
  antes, campo por campo.
- **I2 (no leakage)** — El resultado de `optimize_thresholds` depende **solo** de datos
  en `[val_start, val_end]`. Alterar los datos posteriores a `val_end` no cambia el
  resultado.
- **I3** — `optimize_thresholds` nunca devuelve una combinación con `exit >= entry`.
- **I4** — `validate_split` rechaza cualquier solapamiento o desorden.
- **I5** — `evaluate_holdout` solo lee el rango de test.
- **I6** — El dict de `optimize_thresholds` nombra su Sharpe `sharpe_validacion`, no
  `sharpe`: el nombre tiene que impedir que se reporte como resultado out-of-sample.

**Errores:**

- `ValueError` si `test_start <= val_end`, si `val_start <= train_end`, o si cualquier
  rango está invertido.
- `ValueError` si ninguna combinación del grid es válida (`exit < entry` para ninguna).
- `ValueError` si el rango de validación o de test no contiene barras.

## 4. Criterios de aceptación

- **AC1 (I1)** — `dataclasses.asdict(model)` es idéntico antes y después de llamar
  `optimize_thresholds`.
- **AC2 (I2, leakage)** — Con un `prices` cuyo tramo posterior a `val_end` se reemplaza
  por valores absurdos (`1e6`), `optimize_thresholds` devuelve **exactamente** el mismo
  resultado que con los datos originales. Es el test central del spec.
- **AC3 (I3)** — Ninguna combinación devuelta tiene `exit >= entry`.
- **AC4** — `evaluate_holdout` existe y devuelve las mismas claves que `run_backtest`.
- **AC5 (I5)** — `evaluate_holdout` sobre un `prices` con el tramo de validación
  corrompido da el mismo resultado que con los datos originales.
- **AC6 (I4)** — `validate_split` lanza `ValueError` con `test_start <= val_end`, con
  `val_start <= train_end` y con rangos invertidos; y **no** lanza con un split válido.
- **AC7 (I6)** — El dict de `optimize_thresholds` tiene `sharpe_validacion` y **no**
  tiene una clave llamada `sharpe`.
- **AC8** — `entry_range=(1.0,)`, `exit_range=(2.0,)` (ninguna combinación válida)
  lanza `ValueError`.
- **AC9** — El grid se recorre completo: `n_combinaciones` devuelto coincide con el
  número de pares `(entry, exit)` con `exit < entry`.

## 5. Verificación

- **Archivo:** `tests/test_spec_006_holdout.py`
- **Comando:** `uv run pytest tests/test_spec_006_holdout.py -v`

| AC | Test |
|---|---|
| AC1 | `test_ac1_optimize_no_muta_modelo` |
| AC2 | `test_ac2_tuning_no_ve_datos_posteriores` |
| AC3 | `test_ac3_exit_menor_que_entry` |
| AC4 | `test_ac4_evaluate_holdout_existe` |
| AC5 | `test_ac5_holdout_no_ve_validacion` |
| AC6 | `test_ac6_validate_split` |
| AC7 | `test_ac7_nombre_del_sharpe_de_validacion` |
| AC8 | `test_ac8_grid_vacio_falla` |
| AC9 | `test_ac9_cuenta_de_combinaciones` |

## 6. Fuera de alcance

- Walk-forward con purging y embargo → P1.4, `BACKLOG.md`. Es la evolución natural;
  este spec establece el mínimo honesto.
- Corregir el Sharpe del grid search por multiple testing (N pares × 9 combinaciones).
  Relacionado con SPEC-002 pero sobre un espacio distinto (umbrales, no pares) →
  `BACKLOG.md`.
- Hacer `PairModel` `frozen=True`. Lo correcto a futuro, pero rompería a cualquier
  caller que asigne campos → `BACKLOG.md`.
- Versionado y fecha en los modelos serializados (`model.save_model` escribe un `.pkl`
  sin metadata) → `BACKLOG.md`.

## 7. Referencias

- López de Prado (2018), cap. 7 — purging/embargo y por qué un split único es el piso,
  no el techo; cap. 8 — *backtest overfitting* y el sesgo del máximo de N evaluaciones.
- `docs/METHODOLOGY.md` §P0.7 — el hallazgo original.
