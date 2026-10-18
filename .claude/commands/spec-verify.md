---
description: Audita empíricamente un spec implementado — reproduce sus ACs y busca look-ahead con experimentos.
argument-hint: <número de spec, p.ej. 003>
---

Audita el spec **$ARGUMENTS**.

Lanza el agente `backtest-auditor` pasándole:

- La ruta del spec, su estado actual y la del archivo de test asociado.
- Que es **read-only sobre código**: puede correr lo que quiera y escribir scripts en
  el scratchpad de la sesión, pero no edita `src/` ni `tests/`.
- Que debe reproducir los ACs por su cuenta con `tests/synthetic.py` en vez de confiar
  en que el test suite pase, y atacar el código con los experimentos de causalidad
  (`corrupt_after`), falsos positivos (`independent_universe`), invarianzas de escala y
  ground truth (`cointegrated_pair`, `ou_series`).
- Que busque invariantes del §3 del spec que ningún AC cubre.

El veredicto es `VERIFICADA` o `REBOTADA`, y debe venir con evidencia numérica —
comandos y resultados, no impresiones. Si no hay evidencia, el veredicto no vale.

Pásale el veredicto al usuario tal cual, incluyendo los huecos de cobertura. Si la
auditoría pasa, actualiza el estado del spec a `Verificada` y el índice de
`docs/specs/README.md`.
