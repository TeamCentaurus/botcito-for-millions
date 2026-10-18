# ADR-0004 — El reporting lee un artefacto, no recalcula

- **Estado:** Aceptada ✅
- **Fecha:** 2026-10-12
- **Decidido por:** Leonel, 2026-10-12
- **Specs que dependen:** SPEC-009 (dashboard), y el futuro `notifications_service`
- **Origen:** pedido de un dashboard para observar resultados

## Contexto

Hoy los resultados del pipeline **no existen fuera de la memoria del notebook**.
`notebooks/01_selector_pairs.ipynb` corre screening → train → tuning → backtest y los
resultados viven en variables de Python; `data/` está vacío y no hay ningún `.pkl` ni
`.parquet` en el repo. Para mirar un resultado hay que volver a correr el notebook.

Al mismo tiempo hay **dos consumidores** de esos resultados en el horizonte:

1. El dashboard que se pide ahora.
2. `src/notifications_service/` (hoy un stub que imprime "Hello"), que tiene que
   mandar señales por Telegram.

Si cada consumidor llama a `run_backtest` / `screen_universe` por su cuenta, cada uno
se convierte en una implementación paralela del pipeline. Es el mismo modo de fallo que
ADR-0001 acaba de cerrar — backtest y live midiendo cosas distintas — pero movido al
reporting, donde es peor: un dashboard que muestra un número que el backtest no produjo
es indistinguible de uno correcto hasta que alguien opera con él.

Hay un segundo problema, más silencioso: un consumidor que recalcula **no deja
registro**. No se puede responder "¿qué vi el martes y con qué parámetros?", que es la
pregunta que importa cuando una decisión de trading sale mal.

## Opciones consideradas

- **Cada consumidor recalcula.** Cero infraestructura nueva, resultados siempre
  frescos. A cambio: N implementaciones que divergen, nada reproducible, y el costo de
  re-correr un screening de 500 pares cada vez que se abre una pantalla.
- **Artefacto intermedio.** El pipeline escribe un archivo versionado con todo lo que
  produjo; los consumidores solo leen. Añade un contrato que mantener, pero hace el
  resultado reproducible, auditable y compartible, y los consumidores quedan triviales.

## Decisión

**El pipeline escribe un artefacto de resultados versionado. Todo consumidor de
resultados es un lector puro de ese artefacto.**

Reglas que se derivan:

1. **Un consumidor de resultados no importa funciones de cómputo.** Ni `run_backtest`,
   ni `screen_universe`, ni `train`, ni `optimize_thresholds`. Es verificable por
   inspección de imports, y así se verifica (SPEC-009 AC4).
2. **El artefacto lleva `schema_version`.** Un lector que encuentra una versión que no
   soporta falla con un error claro, no interpreta campos a medias.
3. **El artefacto es autocontenido.** Incluye los parámetros con los que se corrió
   (fuente de datos, split, capital, costos, alpha, factor de anualización), no solo
   los números de salida. Un resultado sin sus parámetros no es interpretable.
4. **El artefacto lleva un campo `advertencias`.** El escritor registra los caveats
   conocidos de esa corrida y el lector los muestra de forma prominente. Es lo que
   permite publicar un dashboard **antes** de arreglar las métricas sin que el número
   engañe a quien lo mira.

## Consecuencias

- Aparece un módulo nuevo, `src/botcito_core/reporting.py`, con el schema y las
  funciones de lectura/escritura/validación. Es el único lugar donde el formato vive.
- El dashboard es un lector; añadir un segundo renderer (export a HTML, resumen a
  Telegram) es trabajo chico porque el contrato ya está definido.
- El artefacto es lo que se archiva y se comparte, no una captura de pantalla.
- Costo real: cuando el contrato cambie hay que subir `schema_version` y los lectores
  tienen que manejarlo. Es el precio de tener resultados reproducibles.
- **El dashboard nunca va a mostrar un dato más fresco que la última corrida.** Es
  deliberado: para explorar en vivo se corre el pipeline y se escribe un artefacto
  nuevo.
