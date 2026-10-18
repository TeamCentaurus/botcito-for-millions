---
description: Revisa código de estrategia cuantitativa con checklist de sesgos, validación, costos, métricas y microestructura.
argument-hint: <ruta-al-archivo-o-módulo>
---

Eres un ML engineer cuantitativo. Estás revisando: **$ARGUMENTS**

Lee el archivo/módulo objetivo y cualquier dependencia que importe. Luego produce un reporte con esta estructura exacta:

## Resumen
Una frase: ¿es código apto para producción real con dinero, o tiene problemas que harían inválidos los resultados?

## Hallazgos por categoría

Para cada categoría, marca cada item como:
- ✅ **OK** — implementado correctamente
- ⚠️ **GAP** — falta o está mal implementado (explicar)
- ➖ **N/A** — no aplica al alcance de este código

### 1. Sesgos estadísticos
- [ ] **Look-ahead bias**: ¿se usa información del futuro en decisiones del pasado? Revisar especialmente: stats globales (mean/std) calculadas sobre datasets que incluyen el período de evaluación; uso de `tail()` o `iloc[-N:]` durante entrenamiento; resampling/normalización antes del split.
- [ ] **Survivorship bias**: ¿el universo de tickers excluye delisteados/quebrados?
- [ ] **Data snooping / multiple testing**: si se prueban N pares/hipótesis, ¿hay corrección Bonferroni / Benjamini-Hochberg sobre los p-values?
- [ ] **Selection bias**: ¿el filtro de "pares válidos" se calibró en un período distinto al de evaluación?

### 2. Validación
- [ ] **Train/val/test split**: ¿hay test hold-out final que **no** se tocó durante tuning?
- [ ] **Walk-forward**: ¿se mueve la ventana en el tiempo o es split único?
- [ ] **Purging y embargo** (López de Prado): ¿se purgan observaciones cerca de la frontera train/test cuando hay overlap por etiquetado?
- [ ] **Estabilidad temporal**: ¿se prueba que los parámetros (hedge ratio, mean, std) son estables, o se asume estacionariedad sin verificar?

### 3. Costos y ejecución
- [ ] **Transaction cost** modelado por leg, no por trade.
- [ ] **Bid-ask spread** modelado (especialmente crítico bajo daily, en intraday domina).
- [ ] **Slippage** y **market impact** considerados.
- [ ] **Latencia** entre señal y ejecución simulada (la data llega tarde respecto al evento).

### 4. Métricas y reporting
- [ ] **Sharpe ratio anualizado** correctamente (× √(periodos_por_año), no per-trade crudo).
- [ ] **Denominador del PnL** es capital invertido (notional), no varianza del spread ni nada raro.
- [ ] **Max drawdown**, **Calmar**, **win rate**, **avg trade**, **profit factor** reportados.
- [ ] **Distribución de retornos** examinada (no solo media): skew, kurtosis, peor trade.

### 5. Microestructura (solo si timeframe < daily)
- [ ] **Mid-price** o último trade — no usar bid o ask como precio de referencia.
- [ ] **Bid-ask bounce** filtrado o modelado.
- [ ] **Volumen / liquidez** mínimos respetados.
- [ ] **Latencia del feed** (`is_late`, `lateness_seconds`) usada para descartar o ajustar.

### 6. Estadística (específico a pairs / cointegración)
- [ ] **Cointegración probada** (Engle-Granger o Johansen), con p-value reportado.
- [ ] **Estacionariedad del spread** probada (ADF, KPSS).
- [ ] **Half-life** dentro de rango razonable para el timeframe (daily: 5–30 d; minute: 30–240 min).
- [ ] **Direccionalidad de Engle-Granger** considerada (A~B vs B~A) o reemplazado por Johansen.
- [ ] **Hedge ratio**: si es estático, ¿se valida estabilidad? Si es Kalman, ¿está bien especificado el state-space?

### 7. Riesgo
- [ ] **Stop-loss** definido.
- [ ] **Position sizing** (no equal-dollar fijo): vol-targeting, Kelly fractional, risk parity, etc.
- [ ] **Correlación entre posiciones abiertas** monitoreada (no apilar pares correlacionados).
- [ ] **Max drawdown circuit breaker** o reducción de exposición.

## Recomendaciones priorizadas

| Prioridad | Item | Esfuerzo | Impacto |
|---|---|---|---|
| P0 | ... | ... | ... |
| P1 | ... | ... | ... |

P0 = correctitud (sin esto los resultados pueden ser inválidos).
P1 = mejor metodología (mejora demostrable).
P2 = nice-to-have.

## Referencias relevantes

Cita 2–4 referencias canónicas que apliquen al hallazgo principal (López de Prado, Chan, Bertram, Vidyamurthy, Krauss, etc.).
