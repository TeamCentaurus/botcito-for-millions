---
description: Implementa un spec en estado Aceptada y deja sus criterios de aceptación en verde.
argument-hint: <número de spec, p.ej. 008>
---

Implementa el spec **$ARGUMENTS**.

Antes de lanzar nada, verifica tú mismo dos cosas y para si alguna falla:

1. El spec existe en `docs/specs/` y su estado es `Aceptada`. Si está en `Borrador`,
   dile al usuario qué falta (típicamente aceptar un ADR del que depende) y no sigas.
2. El orden de implementación de `docs/specs/README.md` no deja un prerrequisito
   abierto. Si lo deja, dilo y pregunta si seguir igual.

Luego lanza el agente `spec-implementer` pasándole:

- La ruta del spec y la del archivo de test asociado (`tests/test_spec_00X_*.py`).
- Que **no puede editar §3 Contrato ni §4 Criterios de aceptación**; si el contrato
  está mal, devuelve el spec a `Borrador` con una nota y para.
- Que debe quitar los `@pytest.mark.xfail` de los ACs que pasen (el `strict=True` hace
  fallar la suite si no).
- Que la condición de salida es `uv run pytest -q` en verde y
  `uv run ruff check tests/` limpio.

Al terminar, reporta al usuario: ACs en verde, salida de la suite, qué se anotó en
`BACKLOG.md` y el nuevo estado del spec.
