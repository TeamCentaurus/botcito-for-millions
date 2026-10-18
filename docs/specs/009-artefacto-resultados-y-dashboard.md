# SPEC-009 — Artefacto de resultados + dashboard Streamlit

- **Estado:** Implementada ✅ (con enmienda al schema, ver §3.1)
- **Aceptada por:** Leonel, 2026-10-12
- **Implementada:** 2026-10-12
- **Origen:** pedido de sesión (2026-10-12) — observar resultados de forma interactiva
- **ADRs relacionados:** ADR-0004 (el reporting lee un artefacto), ADR-0003 (métricas), ADR-0002 (daily)
- **Timeframe objetivo:** daily
- **Archivos afectados:** `src/botcito_core/reporting.py` (nuevo), `app/dashboard.py` (nuevo), `pyproject.toml`

## 1. Problema

Los resultados del pipeline no existen fuera de la memoria del notebook. En
`notebooks/01_selector_pairs.ipynb` el screening de 528 pares, los 16 `PairModel` y los
backtests viven en variables de Python; `data/` está vacío y no hay ningún artefacto
serializado en el repo. Para volver a mirar un resultado hay que re-descargar los datos
y re-correr todo.

Eso tiene dos consecuencias concretas hoy:

1. **No se puede inspeccionar lo que pasó.** La salida de la celda 13 del notebook dice
   `NVDA/BAC: sharpe=1179.75, trades=2`. Para entender si eso es una estrategia o un
   artefacto de medición hay que mirar la curva de equity, los 2 trades, el z-score de
   entrada y el half-life — y ninguno de esos datos quedó accesible.
2. **El segundo consumidor ya está pedido.** `src/notifications_service/main.py` es un
   stub que tiene que mandar señales por Telegram. Si el dashboard y el notificador
   cada uno llama a `run_backtest` por su cuenta, son dos implementaciones paralelas del
   pipeline que van a divergir.

Y hay una trampa específica de este momento del proyecto: **las métricas actuales están
mal** (SPEC-004 sin anualizar, SPEC-005 con PnL en unidades de `spread_std`). Un
dashboard que las muestre sin marcarlas convierte un número roto en un número con
apariencia de autoridad.

## 2. Decisión metodológica

Definida en **ADR-0004**: el pipeline escribe un artefacto versionado y el dashboard es
un **lector puro**. No importa ninguna función de cómputo, y eso se verifica por
inspección de imports (AC4).

Renderer: **Streamlit, solo local** (`streamlit run app/dashboard.py`). Sin despliegue
en la VM, sin puerto en el firewall de IAP, sin servicio en `docker-compose.yml`. El
export a HTML estático queda en `BACKLOG.md` como segundo renderer del mismo contrato.

El campo `advertencias` del artefacto es lo que permite tener el dashboard **antes** de
arreglar las métricas: la corrida declara sus propios caveats y el dashboard los muestra
arriba, de forma que `sharpe=1179.75` se lee junto a "el Sharpe no está anualizado y el
PnL está en unidades de desviación estándar del spread".

## 3. Contrato

### 3.1 `src/botcito_core/reporting.py`

```python
RUN_SCHEMA_VERSION = 1

def build_run(*,
              data_source: dict,
              split: dict,
              params: dict,
              screening: list[dict],
              models: list[PairModel],
              backtests: list[dict],
              advertencias: list[str] | None = None,
              run_id: str | None = None) -> dict:
    """Ensambla un artefacto de resultados. `run_id` por defecto es el timestamp UTC."""

def validate_run(run: dict) -> None:
    """Lanza ValueError nombrando el campo que falta o está mal tipado."""

def write_run(run: dict, path: str | Path) -> Path:
    """Valida y escribe JSON (indent=2, UTF-8). Crea el directorio padre si falta."""

def read_run(path: str | Path) -> dict:
    """Lee, valida, y falla si `schema_version` no es soportada."""

def list_runs(directory: str | Path) -> list[Path]:
    """Artefactos de un directorio, del más reciente al más antiguo."""
```

Estructura del artefacto:

| Campo | Tipo | Contenido |
|---|---|---|
| `schema_version` | `int` | `RUN_SCHEMA_VERSION` |
| `run_id` | `str` | Identificador único de la corrida |
| `created_at` | `str` | ISO-8601 UTC |
| `data_source` | `dict` | `provider` (`"yfinance"` \| `"gcs"`), `interval`, `tickers`, `start`, `end` |
| `split` | `dict` | `train_end`, `val_start`, `val_end`, `test_start`, `test_end` |
| `params` | `dict` | `alpha`, `capital`, `transaction_cost`, `annualization_factor`, `zscore_window` |
| `screening` | `list[dict]` | Un elemento por par evaluado: `par`, `p_value`, `p_value_corregido`, `rechaza_h0_fdr`, `cumple_filtros_locales`, `valido`, `adf_p_value`, `half_life_dias`, `hedge_ratio` |
| `models` | `list[dict]` | `PairModel` serializado por par entrenado |
| `backtests` | `list[dict]` | Por par y período: `par`, `periodo` (`"val"` \| `"test"`), las métricas, `series` y `trades`. Detalle abajo |
| `advertencias` | `list[str]` | Caveats declarados por quien escribió la corrida |

Cada entrada de `backtests`:

| Campo | Tipo | Nota |
|---|---|---|
| `par`, `periodo` | `str` | `periodo` ∈ {`"val"`, `"test"`} |
| `total_trades`, `win_rate` | `int`, `float` | Correctos hoy |
| `sharpe_ratio`, `total_pnl`, `max_drawdown` | `float` | **Degradados** hasta SPEC-004/005 |
| `total_return`, `annualization_factor` | `float \| None`, `int \| None` | `None` hasta SPEC-004/005 |
| `series` | `dict` | `fechas`, `spread`, `zscore`, `equity_curve`, `returns` — listas de igual longitud; las que el backtest no produzca van `[]` |
| `trades` | `list[dict]` | Lo que `run_backtest` registre |

### Enmienda al schema (2026-10-12)

Dos cambios respecto al borrador original, decididos al planear la implementación:

1. **Se añade `series` con `spread` y `zscore`.** El borrador pedía en §3.2 un gráfico de
   spread y z-score pero no los incluía en el artefacto. El dashboard no puede
   calcularlos (ADR-0004 lo prohíbe y AC4 lo verifica), así que el artefacto los carga.
   Era una inconsistencia entre §3.1 y §3.2.
2. **Los campos que el pipeline todavía no produce admiten `None` o `[]`**, y entonces
   `advertencias` **no puede estar vacío**: si algo va degradado, hay que declararlo.
   Es lo que permite tener el dashboard antes de arreglar las métricas sin que el número
   engañe. Invariante I8.

**Invariantes:**

- **I1 (round-trip)** — `read_run(write_run(run, p)) == run`. Sin pérdida ni
  reordenamiento.
- **I2 (autocontenido)** — Un artefacto válido incluye `data_source`, `split` y
  `params`. Un resultado sin sus parámetros no es interpretable y `validate_run` lo
  rechaza.
- **I3 (versión)** — `read_run` sobre un artefacto con `schema_version` distinto de
  `RUN_SCHEMA_VERSION` lanza `ValueError` nombrando ambas versiones. No se interpretan
  campos a medias.
- **I4 (serializable)** — El artefacto es JSON puro: sin `np.float64`, sin
  `np.bool_`, sin `Timestamp`. `build_run` convierte a tipos nativos de Python. (Los
  dicts que devuelve `botcito_core` hoy están llenos de tipos numpy — ver la salida de
  la celda 7 del notebook.)
- **I5 (consistencia interna)** — Todo `par` que aparece en `models` o en `backtests`
  existe en `screening`.
- **I8 (degradación declarada)** — Si algún campo de métricas de un backtest es `None`
  o alguna lista de `series` está vacía, `advertencias` tiene que ser no vacío.
  Un resultado degradado sin declararlo es peor que no tenerlo.
- **I9 (series alineadas)** — Dentro de un `series`, todas las listas no vacías tienen
  la misma longitud que `fechas`.

**Errores:**

- `ValueError` si falta cualquier campo de nivel superior, nombrándolo.
- `ValueError` si `screening` está vacío.
- `ValueError` si un `par` de `backtests` no está en `screening` (I5).
- `FileNotFoundError` en `read_run` si la ruta no existe.

### 3.2 `app/dashboard.py`

```python
def main() -> None:
    """Punto de entrada del dashboard. TODO el render va aquí dentro."""

if __name__ == "__main__":
    main()
```

**Sin efectos secundarios al importar.** Es un requisito duro, no estilo: es
exactamente el error de `src/botcito_core/monitoring.py`, que ejecuta
`schedule.every(...)` y un `while True` en el cuerpo del módulo y por eso no se puede
importar desde un test. Aquí el módulo se tiene que poder importar para verificarlo.

Lo que el dashboard debe exponer:

1. **Selector de corrida** — lista los artefactos de `runs/` vía `list_runs`, muestra
   `run_id`, fuente de datos y split de la seleccionada.
2. **Banner de advertencias** — `advertencias` en un bloque visible **arriba**, antes de
   cualquier métrica. Si la lista está vacía, no se muestra nada.
3. **Tabla de screening** — un renglón por par con `p_value` crudo **y**
   `p_value_corregido` en columnas adyacentes, ordenable, con filtro por `valido`. Que
   los dos p-values se vean juntos es el punto: es lo que hace evidente que 16 pares
   "válidos" sin corregir son 0 con BH.
4. **Detalle por par** — para el par seleccionado: spread y z-score con las líneas de
   `entry`/`exit`/`stop` del modelo, curva de equity, y tabla de trades.
5. **Métricas** — Sharpe, retorno total, PnL, max drawdown, win rate y nº de trades,
   con el `annualization_factor` de la corrida a la vista.

**Invariantes:**

- **I6 (lector puro)** — `app/dashboard.py` no importa `run_backtest`,
  `screen_universe`, `screen_pair`, `train` ni `optimize_thresholds`, ni directa ni
  indirectamente a través de `botcito_core.backtest` / `.model` /
  `.statistical_validation`. Solo `botcito_core.reporting`.
- **I7** — Importar el módulo no renderiza nada ni abre ningún archivo.

Dependencias a añadir al grupo `dev` de `pyproject.toml`: `streamlit` y `plotly`.
Van en `dev` porque el dashboard es herramienta de laboratorio, no runtime del pipeline
— Airflow y la Cloud Function no deben arrastrarlas.

> Nota para quien implemente: antes de escribir código de gráficos, cargar la skill
> `dataviz`. Este spec define **qué** tiene que ser visible, no cómo se ve.

## 4. Criterios de aceptación

- **AC1 (I1)** — Round-trip: `write_run` + `read_run` sobre un artefacto construido a
  mano devuelve un dict igual al original.
- **AC2 (I2)** — Quitar cada campo de nivel superior, uno por vez, hace que
  `validate_run` lance `ValueError` **nombrando ese campo**.
- **AC3 (I3)** — Un artefacto con `schema_version=999` hace que `read_run` lance
  `ValueError` que menciona `999` y `1`.
- **AC4 (I6)** — Análisis del AST de `app/dashboard.py`: ninguno de los nombres de
  cómputo aparece en sus imports, y el único módulo de `botcito_core` importado es
  `reporting`.
- **AC5 (I7)** — `importlib.import_module("dashboard")` no lanza y no produce salida:
  todo el render está dentro de `main()`.
- **AC6 (I4)** — `build_run` sobre entradas que contienen `np.float64`, `np.bool_` y
  `pd.Timestamp` produce un dict que `json.dumps` serializa sin `default=`.
- **AC7 (I5)** — Un `backtests` con un `par` que no está en `screening` hace que
  `validate_run` lance `ValueError`.
- **AC8** — `list_runs` devuelve los artefactos del más reciente al más antiguo y
  ignora los archivos que no son `.json`.
- **AC9** — `read_run` sobre una ruta inexistente lanza `FileNotFoundError`.
- **AC10** — `advertencias` sobrevive el round-trip, y `app/dashboard.py` referencia
  el campo (sin esto, el banner no existe y el dashboard muestra números rotos sin
  marcarlos).
- **AC12 (I8)** — Un artefacto con `total_return=None` y `advertencias=[]` hace que
  `validate_run` lance `ValueError`; con una advertencia declarada, pasa.
- **AC13 (I9)** — Un `series` con `zscore` de longitud distinta a `fechas` hace que
  `validate_run` lance `ValueError`.
- **AC11 ⛔ (bloqueado)** — Integración: `screen_universe` → `train` → `run_backtest`
  → `build_run` → `write_run` → `read_run` produce un artefacto válido sobre datos
  sintéticos. **Depende de SPEC-002 (`screen_universe`), SPEC-004 y SPEC-005** (las
  claves de métricas que el artefacto declara). Queda en `xfail` hasta que esos tres
  estén implementados.

## 5. Verificación

- **Archivo:** `tests/test_spec_009_reporting.py`
- **Comando:** `uv run pytest tests/test_spec_009_reporting.py -v`

| AC | Test |
|---|---|
| AC1 | `test_ac1_round_trip` |
| AC2 | `test_ac2_campos_obligatorios` |
| AC3 | `test_ac3_version_no_soportada` |
| AC4 | `test_ac4_dashboard_es_lector_puro` |
| AC5 | `test_ac5_dashboard_sin_efectos_al_importar` |
| AC6 | `test_ac6_json_puro_sin_tipos_numpy` |
| AC7 | `test_ac7_consistencia_screening_backtests` |
| AC8 | `test_ac8_list_runs_ordena_por_fecha` |
| AC9 | `test_ac9_ruta_inexistente` |
| AC10 | `test_ac10_advertencias_sobreviven_y_se_muestran` |
| AC11 | `test_ac11_integracion_pipeline_a_artefacto` |
| AC12 | `test_ac12_degradacion_exige_advertencia` |
| AC13 | `test_ac13_series_alineadas` |

El dashboard en sí no se testea con un servidor Streamlit corriendo: los ACs verifican
el **contrato** (serialización, validación) y las **fronteras** (lector puro, sin
efectos al importar), que es donde están los modos de fallo que importan. Verificar que
un gráfico "se ve bien" no es automatizable y no se pretende.

## 6. Fuera de alcance

- **Export a HTML estático** → `BACKLOG.md`, como segundo renderer del mismo contrato.
- **Desplegar el dashboard en la VM** (docker-compose + puerto 8501 en el firewall de
  IAP, `infra/variables.tf`) → `BACKLOG.md`.
- **Que el dashboard dispare backtests.** Prohibido por ADR-0004: sería un consumidor
  acoplado y la corrida no quedaría registrada.
- **Que `notifications_service` consuma el artefacto.** El contrato queda listo para
  eso, pero el servicio es otro spec.
- **Arreglar las métricas que el dashboard va a mostrar** → SPEC-004 y SPEC-005. Este
  spec solo garantiza que los caveats se declaren y se vean.
- **Loader de datos reutilizable** (hoy `load_prices` vive en la celda 1 del notebook y
  `monitoring.py:4` importa un `src.data_loader` que no existe) → spec aparte.

## 7. Referencias

Ninguna metodológica. La decisión de diseño está en ADR-0004; el antecedente concreto de
"módulo con efectos secundarios al importar" es `src/botcito_core/monitoring.py`.
