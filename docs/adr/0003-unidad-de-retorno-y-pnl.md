# ADR-0003 — Unidad de retorno y PnL

- **Estado:** Aceptada ✅
- **Fecha:** 2026-10-12
- **Specs que dependen:** SPEC-004, SPEC-005
- **Origen:** `docs/METHODOLOGY.md` §P0.4 y §P0.5

## Contexto

`backtest.run_backtest` acumula un retorno **por trade** y lo normaliza por la
volatilidad del spread:

```python
# backtest.py:61-67
pnl = position * (spread.iloc[i] - entry_spread)
pnl = pnl / model.spread_std      # ← unidades de "desviaciones estándar del spread"
pnl -= transaction_cost
```

y después calcula el Sharpe sobre esa serie:

```python
# backtest.py:107
sharpe = returns_arr.mean() / returns_arr.std()
```

Dos problemas encadenados, y es importante tratarlos juntos: **no se puede arreglar
el Sharpe sin fijar primero qué es un retorno.**

1. **Unidad equivocada.** `pnl / spread_std` no son dólares ni retorno sobre capital.
   El `total_pnl` reportado no es interpretable y no se puede comparar con un
   benchmark ni con otra estrategia.
2. **Granularidad equivocada.** La serie es por *trade*, no por *período*. El Sharpe
   de una serie por trade no se anualiza con `√252`; depende de cuántos trades
   hubo y en cuánto tiempo.

## Opciones consideradas

- **Retornos por trade** con Sharpe anualizado vía `√(N_trades / T_años)`. Funciona,
  pero el denominador cambia con la frecuencia de trading, lo que vuelve el Sharpe
  sensible al número de trades y difícil de comparar entre configuraciones de umbral.
- **Retornos por período** (una observación por barra, cero cuando se está flat) con
  Sharpe anualizado vía `√252`. Es la convención de la literatura y de cualquier
  benchmark; permite comparar contra buy-and-hold directamente.

## Decisión

**Retornos por período, en unidades de capital.**

1. **Serie de retornos:** una observación por barra del backtest, no por trade. Si la
   posición está flat, el retorno de esa barra es `0.0`. Es lo que hace comparable el
   Sharpe con 252 como factor.
2. **Denominador:** capital invertido (`capital`), no `spread_std`. El PnL intermedio
   se calcula en dólares.
3. **Sizing por unidades de spread, con notional desplegado = capital.**

   ⚠️ **Esto corrige la fórmula de METHODOLOGY §P0.5.** El boceto de la auditoría
   asigna `C/2` de notional a cada pierna *y además* multiplica la pierna B por
   `hedge_ratio`, con lo que B termina con `β · C/2` de notional: la posición no queda
   dollar-neutral y el notional bruto desplegado es `(1 + β) · C/2`, no `C`. Con β=2
   eso es 1.5× el capital que se cree estar usando, y el retorno queda subestimado en
   ese factor.

   La formulación consistente parte de la unidad de spread: una unidad es *long 1
   acción de A, short β acciones de B*, y cuesta `p_a + β·p_b` de notional. Para
   desplegar capital `C`:

   ```python
   unidades = capital / (price_a_entry + model.hedge_ratio * price_b_entry)
   shares_a = unidades
   shares_b = unidades * model.hedge_ratio
   pnl_dolares = position * (
       shares_a * (price_a_t - price_a_entry)
       - shares_b * (price_b_t - price_b_entry)
   )
   ```

   De donde sale la forma cerrada del retorno, que es la pieza interpretable:

   ```
   retorno = position * Δspread / (price_a_entry + β * price_b_entry)
   ```

   El denominador es el notional bruto de entrada — una cantidad económica — en lugar
   de `spread_std`, que no lo es.

4. **Costos por leg, no por trade.** Un round-trip toca 4 legs (abrir A, abrir B,
   cerrar A, cerrar B) y `transaction_cost` aplica a cada uno **sobre el notional de
   ese leg**. Como los dos legs de la apertura suman `C` por construcción, el costo de
   apertura en unidades de retorno es exactamente `transaction_cost`, y el round-trip
   completo cuesta ≈ `2 * transaction_cost` (0.2% con el default de 0.001 — que es lo
   que el docstring original de `run_backtest` ya decía).
5. **Sharpe:** `(mean / std) * sqrt(annualization_factor)` con
   `annualization_factor=252` como **parámetro explícito** de la función, no una
   constante escondida en el cuerpo.

## Consecuencias

- `run_backtest` necesita acceso a los **precios** en el momento de entrada y de
  salida, no solo al spread. Hoy guarda `entry_spread`; tendrá que guardar
  `entry_price_a` y `entry_price_b`, y registrarlos en el dict de cada trade para que
  el PnL sea reauditable desde fuera.
- El notional bruto desplegado es exactamente `capital`, así que `total_return` es
  comparable contra buy-and-hold sin ajustes.
- Aparece un parámetro `capital` en la firma. Los retornos son invariantes a su valor
  (el `C` se cancela entre numerador y denominador), lo que da un AC verificable
  gratis: duplicar el capital no debe cambiar el Sharpe.
- `total_pnl` pasa a estar en dólares y se puede reportar junto con `total_return`.
- `max_drawdown` debe calcularse sobre la curva de equity acumulada de los retornos
  por período, no sobre la suma de PnLs por trade como hoy (`backtest.py:121-129`).
- El Sharpe reportado va a **bajar** respecto al actual. No es una regresión: el
  número de ahora no mide lo que su nombre dice.
