# ADR-0002 — Daily primero, 1-min diferido

- **Estado:** Aceptada ✅
- **Fecha:** 2026-10-12
- **Specs que dependen:** todos (fija las constantes del dominio)
- **Origen:** `docs/METHODOLOGY.md` §4

## Contexto

La Cloud Function `functions/handle_stock_request/` ingesta precios **cada minuto** a
GCS, así que existe la tentación de operar a 1-min. Pero tener el dato a 1-min no
obliga a operar a 1-min: se puede resamplear a daily.

METHODOLOGY §4.2 documenta por qué la metodología actual **no** aplica directamente a
1-min: bid-ask bounce domina la varianza del "close" (Twelvedata 1-min OHLCV no da
bid/ask), la cointegración daily no se preserva bajo desagregación temporal, los
costos round-trip (0.05%–0.20%) exigen Sharpe pre-costos > ~3, y el feed llega 30–90s
tarde por construcción.

## Opciones consideradas

- **Daily primero** — valida la pipeline donde la metodología es estándar y los
  costos son irrelevantes frente a los movimientos diarios.
- **1-min desde ya** — aprovecha el dato que ya se está ingestando, pero requiere
  modelar microestructura, latencia y costos desde cero antes de poder confiar en
  cualquier número.
- **Ambos, parametrizado** — no amarra, pero duplica el trabajo de diseño antes de
  tener un solo resultado out-of-sample válido.

## Decisión

**Daily primero.** Todo spec de esta iteración se escribe y verifica contra daily.

Constantes del dominio que los specs usan y los tests asumen:

| Parámetro | Valor | Nota |
|---|---|---|
| Factor de anualización | **252** | Días hábiles. Usado por SPEC-004 |
| Half-life válida | **5 < hl < 30** días | El código hoy usa `1 < hl < 60` (`statistical_validation.py:163`); el límite inferior de 1 día admite ruido estadístico |
| Costo de transacción | **0.1% por leg** | Razonable para retail con broker low-cost (IBKR, Schwab). Round-trip de un par = 4 legs |
| Ventana de correlación | **252** observaciones | Un año bursátil |
| Microestructura | **fuera de alcance** | A daily, el bid-ask spread es ruido frente al movimiento diario |

## Condiciones para reabrir 1-min

No se retoma intraday por entusiasmo. Se retoma cuando se cumplan **las tres**:

1. **Sharpe out-of-sample positivo en daily**, medido sobre un hold-out que no se
   tocó durante el tuning (SPEC-006 es lo que lo hace posible).
2. **P&L interpretable en dólares** (SPEC-005), no en unidades de `spread_std`.
3. **Un feed con bid/ask** (Polygon, Alpaca, IEX) — o aceptar subir a 5-min/15-min,
   donde los costos son manejables y el bounce pesa menos.

## Consecuencias

- Los tests sintéticos generan `DatetimeIndex` de **días hábiles** (`freq="B"`).
- `screen_pair` seguirá aceptando el rango `1 < hl < 60` hasta que un spec lo cambie;
  el endurecimiento a `5 < hl < 30` está en `docs/specs/BACKLOG.md`, no en esta
  iteración (cambia qué pares se consideran válidos — es decisión de modelado, no de
  correctitud).
- La ingesta a 1-min **no se detiene**: el dato se acumula en GCS y se resamplea. No
  hay que cambiar la Cloud Function ni el Scheduler.
- Cuando se reabra 1-min, este ADR se marca *Reemplazada* por el que lo suceda.
