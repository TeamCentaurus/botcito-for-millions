---
description: Convierte un hallazgo metodológico en un spec con contrato y criterios de aceptación falsificables.
argument-hint: <hallazgo, o referencia tipo "P1.4" / "BACKLOG: imports rotos de monitoring">
---

Escribe un spec nuevo para: **$ARGUMENTS**

Lanza el agente `spec-author` con la tarea. Pásale en el prompt:

- El hallazgo tal como lo escribió el usuario, textual.
- Que debe leer `docs/specs/TEMPLATE.md`, `docs/specs/README.md` (ciclo de vida y
  numeración), `docs/specs/BACKLOG.md`, los ADRs de `docs/adr/` y `tests/synthetic.py`
  antes de escribir.
- Que si el hallazgo viene de `docs/METHODOLOGY.md`, cite la sección de origen.
- Que verifique con `tests/synthetic.py` cualquier número que afirme en un AC, en vez
  de estimarlo.
- Que el spec nace en estado `Borrador` y, si depende de un ADR sin aceptar, lo marque
  como bloqueado.

Cuando el agente termine, resume al usuario: número y título del spec, cuántos ACs
tiene, qué quedó bloqueado o fuera de alcance, y qué tiene que decidir él para que el
spec pase a `Aceptada`.
