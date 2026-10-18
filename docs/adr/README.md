# Architecture Decision Records

Un ADR registra **una decisión transversal** y por qué se tomó. Vive aquí cuando la
decisión afecta a más de un spec; si solo afecta a uno, va dentro del spec (§2).

## Estados

| Estado | Significado |
|---|---|
| **Propuesta** | Escrita con recomendación, pendiente de que el dueño del modelado la acepte |
| **Aceptada** | Firmada. Los specs pueden depender de ella y congelar contratos |
| **Reemplazada** | Sustituida por otro ADR (enlazar al nuevo) |

## Índice

| ADR | Título | Estado |
|---|---|---|
| [0001](0001-zscore-rolling-vs-estatico.md) | z-score rolling vs estático | Aceptada (Opción A) |
| [0002](0002-timeframe-daily-primero.md) | Daily primero, 1-min diferido | Aceptada |
| [0003](0003-unidad-de-retorno-y-pnl.md) | Unidad de retorno y PnL | Aceptada |
| [0004](0004-reporting-lee-artefacto.md) | El reporting lee un artefacto, no recalcula | Aceptada |
| [0005](0005-pivote-a-residuos-de-factores.md) | Pivote a residuos de un modelo de factores | Aceptada (Opción A, 2026-10-15); s-score lineal sin señal (2026-10-18) |
| [0006](0006-trend-following-multi-activo.md) | Trend following multi-activo (técnica A) | Propuesta |
| [0007](0007-residuos-con-senal-aprendida.md) | Residuos con señal aprendida (técnica B) | Propuesta |

## Formato

```markdown
# ADR-000X — <título>

- **Estado:** Propuesta | Aceptada | Reemplazada
- **Fecha:** YYYY-MM-DD
- **Specs que dependen:** SPEC-00X

## Contexto
## Opciones consideradas
## Decisión
## Consecuencias
```

Regla: un ADR **Propuesta** bloquea a los specs que dependen de él. No se congela un
contrato sobre una decisión que todavía no se aceptó.

"Aceptar" acá no es nada ceremonial: es decidir, y dejar la decisión escrita cambiando
el campo **Estado** del archivo y añadiendo quién la tomó y cuándo.
