# Pre-registro — Técnica B: residuos de factores + señal aprendida

- **Estado:** **Borrador** — pendiente de aceptación del dueño del modelado. Nada de
  lo que sigue se corre sobre datos reales hasta que esté aceptado; una vez aceptado,
  las secciones 3 a 8 se congelan (igual que §3–§4 de un spec).
- **Escrito:** 2026-10-18, **antes** de descargar datos nuevos, de instalar
  dependencias y de entrenar cualquier modelo.
- **ADR:** `docs/adr/0007-residuos-con-senal-aprendida.md` (Propuesta).
- **Contexto:** `LITERATURA.md` y `DATOS.md` de este directorio; `docs/STATUS.md` §1
  ("Walk-forward 2026-10-18" y "Universo ampliado"); formato tomado de
  `research/wf_universo/PREREGISTRO.md`.

---

## 0. Lo que ya sabemos y no se puede des-saber

Este pre-registro existe porque **los datos 2016–2026 ya se miraron**. Lo que se
miró, para que nadie lo redescubra y lo llame señal:

| Ya visto (2016–2026, 96 y 455 acciones) | Resultado |
|---|---|
| s-score lineal de 60 días, IC a h = 1/5/10/20 | Nulo con train 252 (PCA K = 5 y K = 15) |
| Reversión dentro de cada año | Sí, z anual hasta −8.7, anulada por **drift persistente** del residuo |
| PCA con ventana expansiva | Sharpe bruto de juguete 0.53–0.77, decayendo 2016–20 → 2021–26 |
| Residuo contra ETF sectorial | **Momentum** a 5–20 días (z +3.7 a +5.1) |

Lo que **no** se miró: la reversión corta del residuo (≤ 5 días), cualquier función
no lineal de la trayectoria, objetivos de Sharpe, y nada anterior a 2014.

---

## 1. Hipótesis

**H_B:** una señal aprendida sobre la trayectoria de los últimos 30 días del residuo
PCA, con re-entrenamiento rodante, produce una cartera neutral a factores con Sharpe
**neto** positivo y económicamente relevante en acciones grandes de EE.UU., daily,
**después de la publicación** de Guijarro-Ordóñez/Pelger/Zanotti (arXiv, junio 2021).

Es un test fuera de muestra de la literatura (`LITERATURA.md` §1–2), no una búsqueda
abierta: arquitectura, ventana, objetivo y costos se copian de los papers salvo
donde se dice lo contrario.

---

## 2. Datos y universo

- **Universo:** las 455 acciones del S&P 500 actual de `research/wf_universo/`
  (snapshot 2026-10-18). Precios ajustados de yfinance (`load_yfinance`, SPEC-010).
- **Extensión:** re-descarga desde **2004-01-01** para tener desarrollo con ventanas
  de 1,000 días (`DATOS.md` §1). Panel **no balanceado**: en cada re-entrenamiento
  entran las acciones con cobertura completa en la ventana de entrenamiento *y* en
  el año que se predice — esto último es look-ahead de supervivencia declarado,
  inevitable con yfinance.
- **Sesgo declarado:** supervivencia + entrada al índice (`DATOS.md` §1). Favorece
  reversión en desarrollo. En el test es menor (~5 años) pero no nulo.

---

## 3. Partición de la muestra (se congela al aceptar)

```
2004-01 ──── 2005-01 ─────────── 2009-07 ─────────────────────── 2021-07-01 ─────── 2026-10-16 ──── →
  │  PCA burn-in │ primera ventana de │      DESARROLLO (12 años)       │  TEST SELLADO  │  FORWARD
  │   (252 d)    │  entrenamiento     │  walk-forward, se puede mirar   │  (1,330 días)  │  (paper)
                     (1,000 d)                                            una sola vez
```

| Bloque | Fechas (señal OOS) | Uso |
|---|---|---|
| **Desarrollo** | 2009-07-01 → 2021-06-30 | Walk-forward completo. Elegir escalón, depurar, comparar con baselines. Se mira todo lo que haga falta, **contando configuraciones** (§6) |
| **Test sellado** | 2021-07-01 → 2026-10-16 | Se corre **una vez**, con **un** modelo congelado, después de pasar la compuerta de desarrollo. Decide |
| **Forward / paper** | desde la apertura del test | Prueba operativa (§8.3), no estadística |

**Por qué este corte:**

1. **2021-07-01 es la primera fecha posterior a la publicación de GPZ** en arXiv
   (2021-06-08). Medir ahí es el test de McLean-Pontiff: ¿sobrevive la señal a su
   publicación? Mismo argumento que la técnica A con el período posterior a 2016.
2. **El desarrollo cae dentro de la muestra de los papers** (GPZ 2002–2016, AF
   1998–2021). Si nuestra implementación no encuentra nada ahí, donde la literatura
   dice que había, el problema es nuestro (datos, implementación o costos) y **se
   para sin abrir el test**. Es barato y diagnóstico.
3. **El sesgo de supervivencia es mínimo justo donde se decide** (los últimos 5 años).

**Contaminación declarada del test.** 2021–2026 está dentro de lo que ya se miró con
estadísticos **lineales** (§0). Lo único que se usa de eso en este diseño es
negativo (el s-score no sirve → se descarta como señal). K = 5, L = 30 y la
arquitectura salen de los papers, no de nuestros datos. El único dato limpio de
verdad es el **forward** desde la fecha de apertura; por eso existe §8.3.

**Mecanismo de sellado (para la fase 2):** el cargador de datos de B corta en
2021-06-30 salvo que se pase un parámetro explícito de apertura, y la apertura se
registra en este archivo (fecha, hash de la configuración, quién la autorizó) **antes**
de correr. Ver SPEC-026 en §10.

---

## 4. Diseño común a todos los escalones (se congela)

| Pieza | Valor | Origen |
|---|---|---|
| Factores | **PCA, K = 5**, matriz de correlación, ventana rodante de **252 días**, re-estimado cada día con datos hasta t−1 | GPZ/AF (PCA 252 d). K = 5: GPZ con costos da 0.81 (K = 5) vs −0.87 (K = 15); no se elige K mirando nuestros datos |
| Residuo | `compute_residuals` / `cumulative_residual` de SPEC-011, proyectando con el modelo de t−1 | SPEC-011 |
| Input de la señal | Últimos **L = 30** días del residuo acumulado, rebasado a 0 en t−29, dividido por la vol del residuo de 60 días | GPZ |
| Entrenamiento | Ventana rodante de **1,000 días**, re-entrenado **cada 1 de julio**; purga de los últimos 5 días de la ventana (el objetivo mira 5 días adelante) | GPZ (1,000 d); re-entrenamiento anual en vez de cada 125 días por cómputo |
| Cartera | Señal → pesos en espacio de residuos `w_ε(t)` → **pesos por acción `w_R(t) = Φ(t)ᵀ w_ε(t)`**, con `Φ` la matriz de composición del residuo (ε = Φ R − α), normalizada a ‖w_R‖₁ = 1. Rebalanceo diario | GPZ (normalización L1 en acciones) |
| PnL | `w_R(t)ᵀ R(t+1)` sobre **retornos de acciones**, no sobre residuos. (El juguete de wf011 cobraba ε; acá se cobra lo que se puede operar) | ADR-0003 |
| Costos base | `5 bps · ‖w_R(t) − w_R(t−1)‖₁ + 1 bp · ‖min(w_R(t), 0)‖₁` por día | GPZ/AF, para comparar |
| Costos estrés | Igual con **10 bps** por transacción | Propio |

**La cobertura de factores está incluida en los costos** por construcción: `w_R` es la
posición **neta** por acción después de sumar la pierna idiosincrática y las K patas
de cobertura (la decisión práctica de SPEC-013 §2). Lo que cambia `Φ` día a día
(re-estimación del PCA) también genera rotación y se cobra.

Lo que **no** se modela: impacto de mercado, mínimos por orden, acciones enteras.
Para una cuenta personal estos pueden dominar (`LITERATURA.md` §6); quedan para
SPEC-027 y para la prueba forward.

---

## 5. Escalera de modelos (se congela)

Regla general: **empezar por lo más simple que pueda ganarle al s-score lineal**, y
subir solo si la regla de subida lo permite. Todo escalón produce un puntaje por
acción-día; salvo E3b/E4 (que producen pesos directamente), el puntaje se convierte
en `w_ε` con el **rango transversal centrado** (mismo mapeo para todos, para que las
diferencias sean de la señal y no de la cartera).

| Escalón | Qué es | Configs | Por qué está |
|---|---|---|---|
| **E0a** | s-score lineal de 60 días, `w_ε = −s` | 1 | Nuestro nulo conocido. Referencia, **no candidato** |
| **E0b** | OU + umbrales de Avellaneda-Lee sobre ventana de 30 días (abrir con \|s\| > 1.25, cerrar con 0.75 / 0.50 — valores del paper, a confirmar contra el texto en la fase 2) | 1 | Benchmark de GPZ y AF. Referencia, **no candidato** |
| **E0c** | Reversión corta del residuo: `w_ε = −rango(X(t) − X(t−5))` | 1 | Lo que Fischer & Krauss encontraron dentro de su LSTM; nunca lo medimos. **Candidato** |
| **E0d** | Reversión corta **sin factores** (K = 0): `w_R = −rango(retorno 5 días)` | 1 | GPZ K = 0. Si el candidato no le gana, los factores no aportan. Referencia, **no candidato** |
| **E1** | **Ridge** sobre 16 features de la trayectoria (abajo), objetivo = rango de ε(t+1..t+5) | 1 | ¿Hay información en la forma de la trayectoria más allá del z? Lineal, sin hiperparámetros salvo α (CV interna temporal fija) |
| **E2** | **Árboles** (`HistGradientBoosting`), mismas features y objetivo; (a) profundidad 3 / 200 iteraciones, (b) 31 hojas / 500 iteraciones, ambos lr 0.05 con early stopping en los últimos 250 días de la ventana | 2 | No linealidad e interacciones sin red. El hueco que los papers no reportan |
| **E3** | **CNN 1D chica** sobre la ventana cruda de 30 días (2 capas, 8 filtros de tamaño 2): (a) objetivo MSE sobre el rango de ε(t+1..t+5); (b) objetivo **Sharpe neto** de la cartera con los costos base | 2 | Filtro temporal aprendido (el elemento que GPZ identifica como crítico) sin transformer; (b) aísla el aporte del objetivo Sharpe |
| **E4** | **CNN + Transformer de GPZ** con los hiperparámetros publicados (Tabla A.II: D = 8, 4 cabezas, HDN = 2D, dropout 0.25, filtro 2, Adam lr 0.001, 100 épocas, lote 125 días), objetivo Sharpe con costos: (a) L = 30; (b) L = 60 | 2 | La réplica. Sin tuning propio |

**Features de E1/E2** (16, todas causales, rango transversal diario en [−0.5, 0.5]):
`X(t) − X(t−h)` para h ∈ {1, 2, 3, 5, 10, 20, 30} (7); s-score de 30 y 60 días (2);
vol del residuo de 20 días y su cociente con la de 60 (2); coeficiente AR(1) de ε en
60 días (1); `max₃₀(X) − X(t)` y `X(t) − min₃₀(X)` normalizados (2); pendiente MCO de
X en 30 días (1); retorno total de la acción a 5 días (1).

**Regla de subida:**

1. E0a–E0d, E1 y E2 se corren **siempre** (baratos, sin dependencias pesadas salvo
   scikit-learn).
2. **E3** se corre si se aprueba la dependencia `torch` (ADR-0007). Es la prueba del
   filtro temporal aprendido y no se condiciona a E1–E2: la literatura dice que las
   features fijas pueden no capturarlo.
3. **E4** se corre solo si E3 muestra **señal de vida** en desarrollo: Sharpe bruto
   ≥ 1.0 en algún E3, **o** Sharpe neto de E3 mayor que el mejor de E0c–E2.
   Justificación: GPZ reporta Fourier+FFN con PCA K = 5 en 1.98 bruto antes de 2016;
   si un filtro convolucional aprendido no llega a 1.0 bruto en un período que se
   solapa con el de ellos, el transformer no va a rescatarlo, y correrlo solo suma
   configuraciones al conteo de §6.

**Elección del candidato** (uno solo va al test): entre E0c, E1, E2, E3 y E4, el de
mayor Sharpe neto (costos base) en desarrollo, **con preferencia por lo simple**: un
escalón más complejo se elige solo si supera al mejor más simple por **≥ 0.2** de
Sharpe neto. (El error estándar del Sharpe en 12 años es ≈ 0.3; 0.2 no es
"significativo", es un margen para no premiar complejidad por ruido.)

---

## 6. Protocolo anti-overfitting (se congela)

1. **Primero sintético.** Todo el código se valida contra `tests/synthetic.py`
   (`factor_panel` con OU de half-life conocida, random walks para falsos positivos,
   `corrupt_after` para leakage) hasta pasar los ACs de sus specs. Esas corridas
   **no cuentan** como configuraciones.
2. **Presupuesto: como máximo 24 configuraciones sobre datos reales**, sumando todos
   los escalones (el diseño usa 11). Cualquier corrida sobre datos reales que cambie
   un número reportado —incluido arreglar un bug descubierto mirando resultados
   reales— es una configuración nueva. Se anotan **todas**, en orden, en un registro
   append-only (`research/residuos_ml/registro.jsonl`: fecha, hash de configuración,
   métricas de desarrollo). Si se agota el presupuesto, B se cierra sin abrir el test.
3. **Deflated Sharpe Ratio** (Bailey & López de Prado 2014) del candidato en
   desarrollo, con N = cantidad de configuraciones del registro y la varianza de los
   Sharpe entre ellas, sobre retornos netos diarios.
4. **Nula por permutación conjunta** (el instrumento de wf011): la misma permutación
   de fechas aplicada a los retornos realizados `R(t+1)` de **todas** las acciones,
   con los pesos `w_R(t)` fijos; 1,000 permutaciones. No hace falta re-entrenar: la
   nula mide si los pesos de t están alineados con el retorno de t+1 más allá de lo
   que da la estructura transversal. Estadístico: PnL bruto medio diario.
5. **Potencia antes de mirar**: inyectar en un panel sintético del tamaño real un
   residuo 10 % OU (hl 10 días) y verificar que el pipeline completo (E1 y E4) lo
   detecta con la nula del punto 4 en el tamaño del test (1,330 días). Si no lo
   detecta, el test no puede decidir y se rediseña **antes** de abrirlo.
6. **Nada se ajusta con el test.** Ni K, ni L, ni costos, ni el umbral. Si el
   contrato está mal, este documento vuelve a Borrador con una nota, como un spec.

---

## 7. Compuerta de desarrollo (para poder abrir el test)

El candidato tiene que cumplir **las cuatro**:

| Condición | Umbral |
|---|---|
| Sharpe neto (costos base) en desarrollo 2009-07 → 2021-06 | **≥ 0.5** |
| Deflated Sharpe Ratio con N = configuraciones del registro | **≥ 0.95** |
| Sharpe neto en la **segunda mitad** del desarrollo (2015-07 → 2021-06) | **≥ 0.3** (no puede vivir solo de los años viejos: Fischer & Krauss) |
| Sharpe neto del candidato − Sharpe neto de E0d en desarrollo | **> 0** (los factores aportan) |

Si ningún candidato pasa: **B se cierra sin abrir el test.** El test queda sellado y
utilizable para otra hipótesis.

---

## 8. Test sellado y umbral de decisión

### 8.1 Qué se corre

El candidato congelado (código + configuración con hash), en walk-forward sobre
2021-07-01 → 2026-10-16, re-entrenando cada 1 de julio con los 1,000 días previos
(esto es legítimo: solo usa datos anteriores a cada predicción). E0a, E0b y E0d se
corren junto a él como referencia.

### 8.2 Regla de decisión

B **pasa** si se cumplen **las cuatro**:

| | Condición | Umbral |
|---|---|---|
| **Estadística** | PnL bruto medio diario contra la nula conjunta (§6.4) | **p < 0.05** unilateral (un solo candidato, una sola prueba) |
| **Económica** | Sharpe neto con costos base (5 bps + 1 bp short) | **≥ 0.5** |
| **Robustez a costos** | Sharpe neto con costos estrés (10 bps) | **≥ 0** |
| **Breakeven** | Costo por unidad de rotación que lleva el PnL a cero | **≥ 10 bps** |

Además se reporta (no decide): Sharpe neto contra E0a/E0b/E0d, drawdown máximo, rotación
diaria, Sharpe por año, exposición a factores ex post, y la cartera rala (top 10 % de
pesos) para la discusión de costos reales.

**Potencia, dicha antes de mirar.** 1,330 días ≈ 5.3 años; el error estándar de un
Sharpe anual es ≈ √((1 + SR²/2) / 5.3) ≈ 0.46–0.53. Consecuencias:

- Si el Sharpe **neto** verdadero es 0.5, la probabilidad de observar ≥ 0.5 es
  ≈ 50 %. Si es 1.0, ≈ 83 %.
- La condición estadística usa el PnL **bruto**, que en la literatura es 2–3 veces el
  neto: un Sharpe bruto verdadero de 1.5 se detecta con p < 0.05 con ≈ 89 % de
  probabilidad.

Es decir: **este test solo confirma una B que sea casi tan buena como lo que la
literatura reporta antes de su publicación.** Una B con Sharpe neto real de 0.3 muy
probablemente no pasa, y eso se acepta a propósito: para un proyecto personal, una
señal que en 5 años no se distingue de cero no justifica una red neuronal, PyTorch y
una cartera de 455 acciones.

### 8.3 Si pasa

1. ADR-0007 → Aceptada en su versión operativa; specs de producción (SPEC-027).
2. **Forward / paper trading de 6 meses** desde la fecha de apertura, con el mismo
   código. No es una prueba estadística (6 meses no tienen potencia); es operativa:
   - los pesos del paper trading se reproducen **bit a bit** con el backtest sobre los
     mismos datos (espíritu de ADR-0001: backtest ≡ live);
   - el costo realizado (simulado contra precios de apertura/cierre reales) no supera
     **2×** el costo modelado;
   - corte si el drawdown supera el percentil 99 del drawdown a 6 meses de
     desarrollo + test.
3. Recién después de eso, dinero real, con tamaño a definir.

### 8.4 Si no pasa

**Se cierra la técnica B** y, con ella, la línea de residuos de factores para
acciones de EE.UU. en daily (salvo que el dueño del modelado decida otra cosa en un
ADR). **El test queda gastado**: no hay "versión 2" de B evaluada sobre 2021–2026.
Cualquier variante futura necesita datos posteriores a la fecha de apertura.

---

## 9. Qué se reusa del repo

| Pieza | Para qué en B |
|---|---|
| `fit_factor_model`, `compute_factor_returns`, `compute_residuals`, `cumulative_residual` (SPEC-011, Verificada) | Residuos y la matriz Φ (sale de `eigenvectors`, `loadings` y `return_stds` del `FactorModel`, sin cambiar el tipo) |
| `compute_sscore` (ADR-0001) | E0a y features de E1/E2 |
| `load_yfinance`, `clean_prices` (SPEC-010) | Re-descarga 2004 → hoy |
| `research/wf011/walk_forward.py` | Nula por permutación conjunta, `_juguete` como referencia de E0a, potencia con sintéticos |
| `research/wf_universo/` | Universo de 455 y su CSV de constituyentes |
| `tests/synthetic.py` | Validación de todo el pipeline antes de datos reales; test de potencia §6.5 |
| `reporting.py` + dashboard (ADR-0004) | El resultado de B es un artefacto; el dashboard lo lee, no recalcula |
| `screen_universe` / SPEC-012 | **No se usa**: B opera todos los residuos, no filtra acciones una por una |

---

## 10. Specs que harían falta (rango reservado SPEC-020 a 029)

**Prerrequisitos (de otros):** **SPEC-004** (Sharpe anualizado) y **SPEC-005** (PnL
sobre capital). Todas las condiciones de §7–§8 son Sharpe neto: sin esos dos, el
número que decide está mal calculado (`PLAN_TECNICAS.md` §4).

| Spec | Qué contrata | Depende de |
|---|---|---|
| **SPEC-020** | Panel de residuos walk-forward: PCA rodante diario de 252 días, residuos OOS proyectados y matriz de composición Φ(t), con panel no balanceado | 011 |
| **SPEC-021** | Features causales de la trayectoria (las 16 de §5) + ventanas de L días normalizadas para redes | 020 |
| **SPEC-022** | Cartera en espacio de residuos → pesos netos por acción (`w_R = Φᵀ w_ε`, ‖·‖₁ = 1) y modelo de costos (rotación + short). **Reemplaza la parte de piernas de SPEC-013** para B (a decidir por el orquestador si 013 se reescribe o se descarta) | 020, 004, 005 |
| **SPEC-023** | Arnés de walk-forward para señales aprendidas: ventanas, re-entrenamiento anual, purga, registro de configuraciones, nula conjunta, DSR | 022 |
| **SPEC-024** | Baselines E0a–E0d y modelos E1–E2 | 021, 023 |
| **SPEC-025** | Modelos E3–E4 (PyTorch, CPU, semillas fijas, determinismo) | 023, ADR-0007 aceptado |
| **SPEC-026** | Sellado del test: corte de datos, registro de apertura, prueba de que nada antes de la apertura toca fechas ≥ 2021-07-01 | 023 |
| **SPEC-027** | (Solo si B pasa) inferencia diaria, paper trading y costos realistas de broker | todo lo anterior |

---

## 11. Decisiones que tiene que tomar el dueño del modelado para aceptar esto

1. **Partición:** aceptar 2021-07-01 → 2026-10-16 como test sellado (contaminado solo
   por estadísticos lineales, declarado en §0) + forward de 6 meses, **o** exigir que
   el test sea solo forward (más limpio, pero años de espera para tener potencia).
2. **Datos de desarrollo:** re-descargar desde 2004 con el universo actual y aceptar
   el sesgo de supervivencia en el desarrollo, **o** limitar el desarrollo a lo que
   ya está en disco (2014-07 →), que no alcanza para ventanas de 1,000 días antes de
   2019 y obligaría a cambiar §4.
3. **Umbral y dependencia:** confirmar Sharpe neto ≥ 0.5 en el test (sabiendo que una
   B real de 0.3 no pasa) y aprobar `torch` CPU como grupo opcional para E3–E4.

---

## Historial

- 2026-10-18 — Borrador inicial (agente B, fase 1).
