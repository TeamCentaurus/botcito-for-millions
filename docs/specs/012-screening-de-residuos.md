# SPEC-012 — Screening de residuos con corrección FDR

- **Estado:** Borrador (desbloqueado: ADR-0005 aceptado el 2026-10-15)
- **Origen:** consecuencia de ADR-0005; reemplaza el rol de `screen_pair`/`screen_universe` para pares
- **ADRs relacionados:** ADR-0005, ADR-0002 (rangos de half-life para daily)
- **Timeframe objetivo:** daily
- **Archivos afectados:** `src/botcito_core/statistical_validation.py`
- **Depende de:** SPEC-011 (necesita los residuos)

## 1. Problema

Con el pivote a factores, la pregunta de screening cambia de forma pero no de
naturaleza:

| | Pares (hoy) | Residuos (SPEC-011) |
|---|---|---|
| Unidad | un par `(i, j)` | una acción `i` |
| Hipótesis | ¿el spread es estacionario? | ¿el residuo acumulado es estacionario? |
| Nº de tests | `C(N,2)` = 496 con N=32 | **N** = 32 |
| Corrección | BH-FDR (SPEC-002) | **BH-FDR, igual** |

**El multiple testing no desaparece: se reduce.** Pasar de 496 a 32 tests sube el
umbral de BH del primer puesto de `0.05/496 = 1.0e-4` a `0.05/32 = 1.6e-3`, un factor
de 15. Eso es poder estadístico recuperado por diseño, no por aflojar el criterio —
y es exactamente el argumento de P1.5 (clustering) aplicado estructuralmente.

Pero sigue habiendo 32 tests, así que un residuo con p=0.03 evaluado en aislamiento
sigue siendo un falso positivo probable. La lección de SPEC-002 se mantiene:
**la unidad individual no puede emitir veredicto de validez.**

## 2. Decisión metodológica

Misma estructura que SPEC-002, trasladada a residuos:

- `screen_residual` reporta **diagnósticos de una acción** y no decide validez.
- `screen_residuals` barre las N acciones, aplica **Benjamini-Hochberg** sobre los
  p-values del ADF y emite el veredicto.

Los filtros locales también se trasladan: ADF sobre el residuo acumulado y half-life
en rango. ADR-0002 fija `5 < half_life < 30` días como el rango tradeable a daily;
se mantiene el `1 < hl < 60` del código actual para no cambiar dos cosas a la vez, y
el endurecimiento queda en `BACKLOG.md`.

Nota sobre qué p-value se corrige: acá **no hay test de cointegración** — la
estacionariedad del residuo *es* la hipótesis. Así que BH se aplica sobre los
p-values del **ADF**, que en SPEC-002 era el test confirmatorio. Es un cambio de rol,
no de método.

## 3. Contrato

```python
def screen_residual(cumulative: pd.Series, window: int) -> dict:
    """
    Diagnósticos del residuo acumulado de UNA acción. NO emite veredicto: eso
    requiere saber cuántas acciones se probaron (ver screen_residuals).
    """

def screen_residuals(cumulative: pd.DataFrame,
                     alpha: float = 0.05,
                     window: int = 60) -> list[dict]:
    """
    Barre las columnas de `cumulative`, aplica BH-FDR sobre los p-values del ADF y
    emite el veredicto `valido` por acción. Un dict por columna, en el mismo orden.
    """
```

Claves de `screen_residual`: `ticker`, `adf` (dict con `p_value`, `estadistico`,
`estacionario`), `half_life_dias`, `sscore_actual`, `cumple_filtros_locales`.

`screen_residuals` añade: `p_value_corregido`, `rechaza_h0_fdr`, `valido`,
`n_acciones_probadas`.

**Invariantes:**

- **I1** — `len(resultado) == n_columnas`, en el mismo orden que `cumulative.columns`.
- **I2** — `p_value_corregido >= adf["p_value"]` para toda acción.
- **I3** — `valido` implica `rechaza_h0_fdr`.
- **I4** — `screen_residual` no expone `valido`.
- **I5** — Monotonía en `alpha`: los válidos con `alpha=0.01` son subconjunto de los
  de `alpha=0.05`.
- **I6** — Los `p_value_corregido` coinciden exactamente con
  `multipletests(pvals, alpha, method="fdr_bh")[1]`.

**Errores:** `ValueError` si `cumulative` está vacío, si `alpha ∉ (0,1)`, o si alguna
columna tiene menos de `window` observaciones.

## 4. Criterios de aceptación

- **AC1 (I1)** — Un dict por columna, en orden, con el `ticker` correcto.
- **AC2** — Claves presentes: `p_value_corregido`, `rechaza_h0_fdr`, `valido`,
  `n_acciones_probadas`, `cumple_filtros_locales`.
- **AC3 (I6)** — Caso cerrado contra `multipletests` de statsmodels.
- **AC4 (I2)** — `p_value_corregido >= p_value` en todas las acciones.
- **AC5 (falsos positivos)** — Sobre un panel de residuos acumulados generados como
  **random walks** (no estacionarios), **ninguna** acción sale `valido=True`.
- **AC6 (no mata la señal)** — Sobre `factor_panel(theta=0.15)`, donde **todos** los
  residuos son OU por construcción, **la mayoría** (≥ 80 %) sale `valido=True`. Es el
  complemento de AC5: un screening que rechaza todo tampoco sirve.
- **AC7 (I4)** — `"valido" not in screen_residual(...)`.
- **AC8 (I5)** — Monotonía en `alpha`.
- **AC9** — `cumulative` vacío, `alpha=1.5`, y una columna más corta que `window`
  lanzan `ValueError`.
- **AC10 (poder recuperado)** — Caso numérico que documenta el punto de §1: con
  `m=32` el umbral BH del primer puesto es `1.6e-3`, contra `1.0e-4` con `m=496`.
  Verificable con `multipletests` sobre p-values construidos.

## 5. Verificación

- **Archivo:** `tests/test_spec_012_screening_residuos.py`
- **Comando:** `uv run pytest tests/test_spec_012_screening_residuos.py -v`

Mapeo AC → `test_acN_*` con los nombres de §4.

## 6. Fuera de alcance

- **Endurecer el rango de half-life** a `5 < hl < 30` → `BACKLOG.md`.
- **KPSS como test complementario** del ADF (hipótesis nulas opuestas, acuerdo entre
  ambos = más confianza) → `BACKLOG.md`.
- **Elegir `n_factors`** con este screening (p. ej. el K que maximiza residuos
  estacionarios). Tentador y peligroso: sería tunear sobre el mismo criterio que
  después se reporta. Si se hace, va en validación y se reporta en test (SPEC-006).

## 7. Referencias

- **Benjamini & Hochberg (1995)** — el procedimiento.
- **Avellaneda & Lee (2010)** §3 — criterios de selección sobre residuos.
- `docs/specs/002-fdr-multiple-testing.md` — la versión para pares, de la que este
  spec es la traducción.
