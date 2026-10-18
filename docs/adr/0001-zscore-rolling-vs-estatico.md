# ADR-0001 — z-score rolling vs estático

- **Estado:** Aceptada ✅
- **Fecha:** 2026-10-12
- **Decidido por:** Leonel, 2026-10-12 — Opción A
- **Specs que dependen:** SPEC-003
- **Origen:** `docs/METHODOLOGY.md` §P0.3

## Contexto

Hoy conviven **tres** formas distintas de calcular el z-score del spread:

| Lugar | Cómo se calcula |
|---|---|
| `src/botcito_core/model.py:40-41` | `spread_mean = spread.mean()`, `spread_std = spread.std()` — **estáticos** del período de entrenamiento, guardados en el `PairModel` |
| `src/botcito_core/backtest.py:21` | `zscore = (spread - model.spread_mean) / model.spread_std` — usa los **estáticos** del training |
| `src/botcito_core/monitoring.py:25` | `compute_zscore(spread, window=model.zscore_window)` — z **rolling** |

**Lo que mide el backtest no es lo que ejecuta producción.** No son dos
implementaciones de la misma estrategia: son dos estrategias distintas con
distribuciones de señal distintas. Cualquier Sharpe que reporte el backtest actual
no describe el comportamiento del live.

Nótese que el `PairModel` (`src/botcito_core/types.py`) carga **ambos** mundos a la
vez: `spread_mean`/`spread_std` (estático) y `zscore_window` (rolling). El dataclass
no fuerza una elección, y por eso la divergencia pasó desapercibida.

## Opciones consideradas

### Opción A — rolling en ambos (recomendada para daily)

El backtest simula el cálculo rolling exactamente como lo hace producción: en cada
barra `t`, `mean` y `std` se calculan sobre las últimas `zscore_window` observaciones
**hasta `t` inclusive**, sin mirar adelante.

- ✅ Se adapta a drift del spread sin re-entrenar.
- ✅ El live no necesita conocer `spread_mean`/`spread_std` del training → menos
  estado que sincronizar entre entrenamiento y ejecución.
- ✅ Es lo que `monitoring.py` ya hace, así que el live no cambia de comportamiento.
- ⚠️ Las primeras `zscore_window - 1` barras del backtest son `NaN` y hay que
  descartarlas explícitamente (hoy `backtest.py` no lo contempla porque usa estáticos).
- ⚠️ Una ventana corta vuelve el z-score ruidoso; una larga lo vuelve lento. La
  ventana pasa a ser un hiperparámetro real que hay que validar.

### Opción B — estático en ambos, con re-train periódico

El live carga `spread_mean`/`spread_std` del último training y los usa fijos hasta el
siguiente re-entrenamiento (mensual o trimestral).

- ✅ Mantiene la interpretación clásica: "el spread está a 2σ de *su* media histórica".
- ✅ Determinista y trivial de auditar: dos corridas con el mismo modelo dan lo mismo.
- ⚠️ Requiere infraestructura de re-train y versionado de modelos que hoy no existe
  (`model.save_model` escribe un `.pkl` con `joblib`, sin versión ni fecha).
- ⚠️ Entre re-trains, si el spread driftea, el z-score se sesga sistemáticamente y
  la estrategia opera con una media equivocada — el modo de fallo más peligroso.

## Decisión

**Opción A: z-score rolling causal en backtest y en live.** El backtest simula el
cálculo rolling tal como lo hace producción; `spread_mean`/`spread_std` del training
dejan de ser insumo de la señal.

Razones, en orden de peso para este proyecto:

1. No hay pipeline de re-train todavía. La Opción B es correcta solo *con* ese
   pipeline; sin él, degrada al modo de fallo del drift silencioso — la estrategia
   operando contra una media que ya no es la del spread.
2. `monitoring.py` ya es rolling. La Opción A alinea el backtest hacia el live, no al
   revés: menos superficie de cambio en lo que ya ejecuta.
3. A daily, con `zscore_window` de 20–60 observaciones (1–3 meses), la ventana es
   suficientemente larga para no ser ruido y suficientemente corta para seguir drift.

Con esto **SPEC-003 queda desbloqueado** y su contrato (§3) es el vigente.

## Consecuencias

- `backtest.run_backtest` deja de usar `model.spread_mean`/`model.spread_std` y pasa
  a llamar la misma función de z-score que el live.
- `spread_mean`/`spread_std` quedan en el `PairModel` como **diagnóstico del
  training** (útiles para detectar drift comparándolos con los rolling actuales), no
  como insumo de la señal. Hay que documentarlo en el docstring del dataclass o se
  volverán a usar por error.
- `zscore_window` pasa a ser hiperparámetro a validar, no una constante elegida a ojo
  (hoy `model.train` lo fija en `30` por defecto).
- Invariante nueva a testear: para la misma serie de precios, backtest y live deben
  producir **el mismo** z-score en la misma barra. Es el AC central de SPEC-003.
