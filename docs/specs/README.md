# Specs

Cada spec convierte **un hallazgo** en un contrato ejecutable: firmas, invariantes y
criterios de aceptación atados 1:1 a tests. Un hallazgo sin spec es prosa; un spec sin
test es una intención.

`docs/METHODOLOGY.md` es la **auditoría de origen** (7 hallazgos P0 de correctitud, 7
P1 de metodología). Los specs son su traducción a trabajo verificable.

## Ciclo de vida

```
Borrador ──la acepta el dueño del modelado──▶ Aceptada ──implementación──▶ Implementada ──auditoría──▶ Verificada
   ▲                                                      │
   └──────────── contrato incorrecto, con nota ────────────┘
```

| Estado | Significado | Quién lo mueve |
|---|---|---|
| **Borrador** | Escrito, contrato aún discutible | `spec-author` |
| **Aceptada** | Aceptado por el dueño del modelado: §3 Contrato y §4 ACs quedan **congelados** | el dueño del modelado |
| **Implementada** | Código escrito, tests del spec en verde | `spec-implementer` |
| **Verificada** | ACs reproducidos sobre datos sintéticos, sin regresión | `backtest-auditor` |

**Regla dura:** una vez *Aceptada*, el implementador **no edita §3 ni §4**. Si el
contrato está mal, devuelve el spec a *Borrador* con una nota explicando qué no cierra
y para. Un implementador que ajusta el criterio de aceptación para que su código pase
no está implementando: está borrando la verificación.

## Índice

| Spec | Título | Origen | Estado |
|---|---|---|---|
| [001](001-correlation-snapshot.md) | Correlación: snapshot, no rolling | P0.1 | Borrador |
| [002](002-fdr-multiple-testing.md) | Corrección BH-FDR en screening | P0.2 | **Implementada** |
| [003](003-zscore-consistente-backtest-live.md) | z-score consistente backtest ≡ live | P0.3 | Borrador |
| [004](004-sharpe-anualizado.md) | Sharpe anualizado | P0.4 | Borrador |
| [005](005-pnl-sobre-capital.md) | PnL sobre capital invertido | P0.5 | Borrador |
| [006](006-holdout-test-thresholds.md) | Hold-out test tras tuning | P0.7 | Borrador |
| [007](007-cointegracion-bidireccional.md) | Engle-Granger bidireccional / Johansen | P0.6 | Descartada (ADR-0005) |
| [008](008-deduplicar-hedge-ratio.md) | Deduplicar `compute_hedge_ratio` | sesión | Descartada (ADR-0005) |
| [009](009-artefacto-resultados-y-dashboard.md) | Artefacto de resultados + dashboard Streamlit | sesión | **Implementada** (AC11 bloqueado) |
| [010](010-data-loader.md) | Loader de precios | sesión | **Implementada** |
| [011](011-modelo-de-factores-y-residuos.md) | Modelo de factores PCA, residuos y s-score | ADR-0005 | **Verificada** (2026-10-17) |
| [012](012-screening-de-residuos.md) | Screening de residuos con FDR | ADR-0005 | Borrador |
| [013](013-backtest-multi-pierna.md) | Backtest multi-pierna sobre residuos | ADR-0005 | Borrador |

Pendientes sin spec: [`BACKLOG.md`](BACKLOG.md).

## Pivote a factores: ADR-0005 aceptado (2026-10-15)

**ADR-0005** abandona la cointegración por pares a favor de residuos de un modelo de
factores (Opción A), con base en `docs/LITERATURE.md` y en dos corridas sin resultados
(0 de 496 y 0 de 465 pares):

- **SPEC-011, 012 y 013** son el camino nuevo. Desbloqueadas; falta aceptar sus
  contratos y escribir sus tests.
- **SPEC-007 y SPEC-008 están descartadas**: eran trabajo sobre
  `compute_hedge_ratio` y `test_cointegration`, que el pivote borra.
- **SPEC-001, 002, 003, 004, 005 y 006 sobreviven al pivote.** Son sobre look-ahead,
  multiple testing, consistencia backtest≡live, unidades de las métricas y hold-out:
  agnósticas a la técnica.

## Orden de implementación

**Vigente (tras ADR-0005): 011 → 012 → 005 → 004 → 013**, con 003 y 006 detrás. 001
es independiente y de 10 minutos.

*Orden original, previo al pivote (se conserva como registro; 007 y 008 ya no aplican):*
**008 → 001 → 007 → ~~002~~ → 005 → 004 → 003 → 006**. Fuera de la cadena:
~~009~~ y ~~010~~ ya implementadas.

Por qué ese orden:

1. **008** primero: hay dos copias de `compute_hedge_ratio`. Arreglar cualquier cosa
   del hedge ratio antes de deduplicar deja una copia divergente.
2. **001** y **007** son locales a `statistical_validation.py` y no dependen de nada.
3. ~~**002** consume el resultado de 007~~ — **implementada el 2026-10-12** sin
   esperar a 007: la corrección FDR no necesita que el p-value sea bidireccional,
   solo que esté bien definido. Cuando 007 entre, los p-values que alimentan a BH
   serán los corregidos por dirección y el screening se endurece un poco más.
4. **005 antes de 004**: el Sharpe se calcula sobre la serie de retornos, así que
   primero hay que fijar qué *es* un retorno (ADR-0003).
5. **003** al final de los de backtest: ADR-0001 ya está decidido (Opción A,
   rolling en backtest y live), así que su contrato es estable.
6. **006** último: reorganiza el flujo train/val/test, y es más fácil sobre un
   `run_backtest` cuyas métricas ya son correctas.
7. **009 no está en la cadena.** Sus ACs de contrato (AC1–AC10) no dependen de ningún
   otro spec, así que se puede implementar cuando quieras — incluso primero, para poder
   mirar los resultados mientras se arregla el resto. Solo AC11 (integración
   pipeline → artefacto) está bloqueado por 002, 004 y 005. Mientras esos tres sigan
   abiertos, el artefacto se escribe declarando sus caveats en `advertencias` y el
   dashboard los muestra arriba.

## Cómo se cierra un spec

```bash
uv run pytest tests/test_spec_00X_*.py -v   # todos los ACs del spec en verde
uv run pytest -q                            # sin regresiones en el resto
```

Los tests de ACs no implementados llevan `@pytest.mark.xfail(strict=True)`. Al
implementar el spec el test pasa, el XPASS **rompe** la suite, y eso obliga a quitar
el marker y actualizar el estado del spec. Es intencional: no se puede implementar en
silencio.

## Flujo con agentes

| Comando | Agente | Qué hace |
|---|---|---|
| `/spec-new <hallazgo>` | `spec-author` | Escribe el spec desde `TEMPLATE.md` |
| `/spec-do <id>` | `spec-implementer` | Implementa un spec *Aceptada* |
| `/spec-verify <id>` | `backtest-auditor` | Verifica ACs y busca leakage |
| `/review-strategy <ruta>` | — | Revisión metodológica con checklist |
