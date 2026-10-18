# SPEC-004 — Sharpe anualizado

- **Estado:** Borrador
- **Origen:** `docs/METHODOLOGY.md` §P0.4
- **ADRs relacionados:** ADR-0002 (factor 252 para daily), ADR-0003 (retornos por período)
- **Timeframe objetivo:** daily
- **Archivos afectados:** `src/botcito_core/backtest.py`
- **Depende de:** SPEC-005 (la serie de retornos debe estar en la unidad correcta antes de medir su Sharpe)

## 1. Problema

```python
# backtest.py:104-107
if returns_arr.std() == 0:
    sharpe = 0
else:
    sharpe = returns_arr.mean() / returns_arr.std()
```

Esto es un Sharpe **por trade sin anualizar**, reportado bajo la clave
`sharpe_ratio` como si fuera comparable con la literatura o con un benchmark. No lo es:

- Falta el factor de anualización. A daily son `√252 ≈ 15.87`.
- La serie es por trade, no por período, así que ni siquiera `√252` sería el factor
  correcto sobre ella (habría que usar `√(N_trades / T_años)`, que depende de la
  frecuencia de trading y hace el número incomparable entre configuraciones).

El efecto es grande y en la dirección peligrosa: **el número reportado hoy es mucho
menor que el Sharpe anualizado**, así que una estrategia puede parecer mediocre
cuando es buena — o, peor, al "arreglarlo" a ojo multiplicando por un factor
equivocado, parecer excelente cuando no lo es. METHODOLOGY §P0.4 señala que a 1-min el
factor sería ~98,280, una diferencia de ×313 respecto a daily.

## 2. Decisión metodológica

Definida en **ADR-0003**: Sharpe sobre **retornos por período**, anualizado con
`√annualization_factor`, donde el factor es **parámetro explícito** de la función.

Explícito y no constante escondida porque el factor es la pieza que cambia al mover de
timeframe, y dejarlo implícito es cómo se llega a comparar un Sharpe daily con uno
intraday sin notarlo. ADR-0002 fija `252` como default para daily.

Se extrae una función aislada `annualized_sharpe` para que el cálculo sea testeable
con casos numéricos cerrados sin montar un backtest completo.

## 3. Contrato

```python
def annualized_sharpe(returns: np.ndarray, annualization_factor: int = 252) -> float:
    """
    Sharpe anualizado de una serie de retornos POR PERÍODO.
        (mean / std) * sqrt(annualization_factor)
    Devuelve 0.0 si la serie está vacía o su desviación estándar es 0.
    No asume tasa libre de riesgo (excess returns = returns).
    """

def max_drawdown(returns: np.ndarray) -> float:
    """
    Máximo peak-to-trough de la curva de equity (1 + returns).cumprod(),
    como fracción en [0, 1].
    """
```

`run_backtest` recibe `annualization_factor: int = 252` y lo propaga.

**Invariantes:**

- **I1** — `annualized_sharpe(r, f) == (mean(r) / std(r)) * sqrt(f)`.
- **I2 (escalado)** — `annualized_sharpe(r, 252) == annualized_sharpe(r, 1) * sqrt(252)`.
- **I3** — Serie vacía → `0.0`. `std == 0` → `0.0`. No lanza, no devuelve `inf`/`NaN`:
  son casos normales (ningún trade, o un solo trade).
- **I4** — Invariante a la escala de los retornos: multiplicar todos los retornos por
  una constante positiva no cambia el Sharpe.
- **I5** — `annualization_factor` aparece en la firma de `run_backtest` con default
  `252`, y el valor usado se refleja en el dict devuelto (clave
  `annualization_factor`) para que el número reportado sea auditable.

**Errores:**

- `ValueError` si `annualization_factor <= 0`.

**Convención de `std`:** se usa `np.std(ddof=1)` (muestral) por consistencia con
`pd.Series.std()`, que es lo que usa el resto del pipeline. Documentarlo: con series
cortas la diferencia entre `ddof=0` y `ddof=1` es material.

## 4. Criterios de aceptación

- **AC1 (I1)** — Caso numérico cerrado: para `returns = [0.01, -0.005, 0.02, 0.0]`,
  `annualized_sharpe` coincide con el cálculo manual a `1e-12`.
- **AC2 (I2)** — `annualized_sharpe(r, 252) / annualized_sharpe(r, 1) == sqrt(252)`.
- **AC3 (I3)** — `annualized_sharpe(np.array([]))` y una serie constante devuelven
  exactamente `0.0`.
- **AC4 (I4)** — Multiplicar todos los retornos por `10` no cambia el Sharpe.
- **AC5 (I5)** — `run_backtest` acepta `annualization_factor`, su default es `252`, y el
  dict devuelto incluye el valor usado.
- **AC6** — Pasar `annualization_factor=1` a `run_backtest` produce un Sharpe
  exactamente `sqrt(252)` veces menor que el default, sobre los mismos datos.
- **AC7** — `annualization_factor=0` y `-1` lanzan `ValueError`.
- **AC8** — `max_drawdown` sobre una curva con caída conocida (p. ej. retornos
  `[+0.10, -0.20, +0.05]`) coincide con el valor analítico, y es `0.0` para una serie
  monótonamente creciente.

## 5. Verificación

- **Archivo:** `tests/test_spec_004_sharpe.py`
- **Comando:** `uv run pytest tests/test_spec_004_sharpe.py -v`

| AC | Test |
|---|---|
| AC1 | `test_ac1_formula_caso_cerrado` |
| AC2 | `test_ac2_escalado_por_raiz_del_factor` |
| AC3 | `test_ac3_series_degeneradas_dan_cero` |
| AC4 | `test_ac4_invariante_a_escala` |
| AC5 | `test_ac5_run_backtest_expone_el_factor` |
| AC6 | `test_ac6_factor_uno_vs_default` |
| AC7 | `test_ac7_factor_invalido_falla` |
| AC8 | `test_ac8_max_drawdown_caso_cerrado` |

## 6. Fuera de alcance

- Tasa libre de riesgo en el numerador (excess returns). A daily y con capital
  pequeño es ruido; anotado en `BACKLOG.md`.
- Sortino, Calmar, profit factor y distribución de retornos (skew/kurtosis) →
  `BACKLOG.md`. Este spec solo arregla el Sharpe y el drawdown.
- El factor para intraday (~98,280) → bloqueado por ADR-0002 (daily primero).

## 7. Referencias

- `docs/METHODOLOGY.md` §P0.4 — el hallazgo y la magnitud del error por timeframe.
- Lo (2002), *The Statistics of Sharpe Ratios*, Financial Analysts Journal — por qué
  `√T` solo es válido con retornos i.i.d., y qué pasa cuando hay autocorrelación
  (relevante: el spread de un par mean-reverting **está** autocorrelacionado, así que
  el Sharpe anualizado así es optimista; queda anotado en `BACKLOG.md`).
