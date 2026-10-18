# Plan de técnicas: A (trend following) y B (residuos + señal aprendida)

- **Fecha:** 2026-10-18
- **Estado:** Fase 1 **terminada** (2026-10-18) — esperando que el dueño del modelado acepte los pre-registros
- **Origen:** la línea de residuos con s-score lineal no pasó su pre-registro
  (`research/wf_universo/PREREGISTRO.md`, sección "Universo ampliado" de `STATUS.md`)
- **Orden decidido por el dueño del modelado:** **A primero, después B.** Ejecución en
  **paralelo por fases**: la fase 1 (solo documentos) va en paralelo; la implementación
  arranca por A.

---

## 1. Por qué cambiar de técnica

Tres pruebas con potencia, cada vez más grandes (96 acciones con un corte, 96 con
walk-forward y 455 pre-registradas), dicen lo mismo: **el s-score lineal sobre
residuos de factores no predice el residuo** en acciones de EE.UU. en daily, 2016–2026.
Eso coincide con la literatura: en *Attention Factors* (2025) el OU paramétrico con
umbrales es el benchmark con Sharpe neto **negativo**. El ~1.57 que citaba ADR-0005
viene de una **señal aprendida** sobre la trayectoria del residuo, no del s-score.

El instrumento de evaluación (walk-forward, nula por permutación conjunta, potencia
con datos sintéticos, pre-registro, umbral económico) funcionó y **se reusa tal cual**
en las dos técnicas nuevas.

---

## 2. Técnica A — Trend following multi-activo

**Qué es.** Momentum de serie temporal: en cada activo, posición en la dirección de su
retorno pasado, escalada por volatilidad. No compara activos entre sí; cada uno sigue
su propia tendencia.

**Evidencia** (detalle en `LITERATURE.md` §3.1): Hurst, Ooi & Pedersen (2017),
67 mercados, 1880–2016, Sharpe 0.76; Moskowitz, Ooi & Pedersen (2012). Es la evidencia
más larga que existe en finanzas cuantitativas. Contra: década pobre en los 2010s y
drawdowns largos.

**Por qué va primero.**

- Rotación baja → los costos casi no la afectan (fue lo que mató a los residuos).
- Implementación simple, diaria, con ETFs vía yfinance.
- **Tiene un período post-publicación limpio**: los papers usan datos hasta 2016. Medir
  2017–2026 es un test fuera de muestra genuino del paper, sin que lo hayamos mirado.

**Lo que hay que definir en la fase 1:** universo de ETFs por clase de activo
(acciones, bonos, commodities, divisas) con historia suficiente; señal canónica de la
literatura (horizontes y escalado por volatilidad), **una sola**, sin optimizar;
modelo de costos; test contra nula; umbral de decisión.

**Expectativa realista:** Sharpe neto 0.3–0.7 después de McLean-Pontiff. Su valor es
de diversificación y de baja correlación, no un Sharpe alto.

---

## 3. Técnica B — Residuos de factores + señal aprendida

**Qué es.** Los mismos residuos de SPEC-011 (ya implementado y verificado), pero la
señal sale de un modelo que mira la **trayectoria completa** del residuo acumulado
(p. ej. los últimos 30–60 días), no solo su z-score. En Guijarro-Ordóñez, Pelger &
Zanotti la red optimiza directamente el Sharpe de la cartera.

**Evidencia** (`LITERATURE.md` §3.2): Guijarro-Ordóñez, Pelger & Zanotti
(Management Science), Sharpe > 4; *Attention Factors* (2025, preprint), PCA + señal
temporal ≈ 1.57 neto. Ambos con el descuento de McLean-Pontiff pendiente.

**Por qué va segundo.**

- Es la técnica con más riesgo de autoengaño: una red con 455 acciones × 11 años tiene
  muchas formas de aprender ruido.
- **Los datos 2016–2026 ya se miraron** con el s-score lineal. B necesita un **período
  de test sellado**, definido antes de entrenar nada, y probablemente forward / paper
  trading como prueba final.
- Probablemente requiera PyTorch (dependencia nueva, cómputo en la PC).

**Lo que hay que definir en la fase 1:** qué entra al modelo (ventana, features), qué
arquitectura y por qué (empezar por el baseline más simple que pueda ganarle al lineal),
cómo se parte la muestra (train / validación / test sellado), costos incluyendo las
patas de cobertura, umbral de decisión, presupuesto de cómputo.

**Expectativa realista:** si el lineal da cero, cualquier Sharpe alto del modelo
aprendido es sospechoso hasta probar lo contrario en el test sellado.

---

## 4. Fases y compuertas

| Fase | A | B | Compuerta |
|---|---|---|---|
| **1. Investigación y pre-registro** (solo docs) | agente A | agente B, **en paralelo** | El dueño del modelado acepta ADR + pre-registro de cada una |
| **2. Implementación y corrida** | primero | después, o en paralelo si la carga de revisión lo permite | Resultado contra el umbral pre-registrado |
| **3. Verificación** | `backtest-auditor` | `backtest-auditor` | Spec → *Verificada* |

**Prerrequisito transversal para la fase 2:** SPEC-005 (PnL sobre capital) y SPEC-004
(Sharpe anualizado). Las dos técnicas deciden por Sharpe neto: sin esos specs el
número que decide está mal calculado.

---

## 5. Reglas de trabajo en paralelo

El andamiaje (`docs/`, `tests/`, `research/`, `.claude/`) **no está commiteado**, así
que los agentes trabajan en la misma carpeta, no en copias aisladas. Para que no se
pisen, cada uno escribe **solo** en lo suyo:

| | A — trend following | B — residuos + ML |
|---|---|---|
| Carpeta de trabajo | `docs/tecnicas/A-trend-following/` | `docs/tecnicas/B-residuos-ml/` |
| ADR | **ADR-0006** | **ADR-0007** |
| Specs (fase 2) | **SPEC-014 a 019** | **SPEC-020 a 029** |
| Research (fase 2) | `research/trend/` | `research/residuos_ml/` |

**Archivos compartidos que solo edita el orquestador** (la sesión principal), después
de cada compuerta: `docs/STATUS.md`, `docs/LITERATURE.md`, `docs/specs/README.md`,
`docs/specs/BACKLOG.md`, `docs/adr/README.md`, `pyproject.toml`, `uv.lock`,
`src/botcito_core/types.py`.

En la fase 1 **ningún agente toca** `src/`, `tests/`, `app/` ni `research/`.

---

## 6. Entregables de la fase 1 (por técnica)

1. `LITERATURA.md` — citas **verificadas** (con enlace) y sus números; qué decayó
   después de publicarse; Sharpe esperado tras McLean-Pontiff. Lo que no se pudo
   verificar se marca como tal.
2. `PREREGISTRO.md` (borrador) — universo, señal, costos, partición de la muestra,
   test y nula, umbral de decisión. Con el mismo formato que
   `research/wf_universo/PREREGISTRO.md`.
3. `docs/adr/000X-*.md` en estado **Propuesta**, con el formato de `docs/adr/README.md`.
4. `DATOS.md` — qué datos hacen falta, si yfinance los da (fechas de inicio reales) y
   qué dependencias nuevas implica.
