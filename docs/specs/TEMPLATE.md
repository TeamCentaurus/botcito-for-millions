# SPEC-00X — <título>

- **Estado:** Borrador
- **Origen:** `docs/METHODOLOGY.md` §P0.x  ·  (o: hallazgo de sesión / issue #N)
- **ADRs relacionados:** ADR-000X  ·  (o: ninguno)
- **Timeframe objetivo:** daily
- **Archivos afectados:** `src/botcito_core/<módulo>.py`

## 1. Problema

Qué está mal hoy, con `archivo:línea` y el código actual citado. Sin esto el spec no
es auditable: quien lo lea en seis meses no podrá confirmar que el problema existía.

## 2. Decisión metodológica

Qué se adopta y por qué. Si la decisión es transversal a varios specs, vive en un ADR
y aquí solo se la referencia — no se duplica el razonamiento.

## 3. Contrato

Firmas exactas: nombre, parámetros con tipos, valor de retorno con su forma.
Invariantes que deben cumplirse siempre. Errores o excepciones esperados ante
entradas inválidas.

```python
def nombre_funcion(arg: tipo, otro: tipo = default) -> TipoRetorno:
    ...
```

**Invariantes:**
- I1 — ...

**Errores:**
- `ValueError` si ...

## 4. Criterios de aceptación

Cada AC debe ser **falsificable** con datos sintéticos (`tests/synthetic.py`) o con un
caso numérico cerrado. "El código es más claro" no es un AC.

- **AC1** — <afirmación verificable>
- **AC2** — ...

## 5. Verificación

- **Archivo:** `tests/test_spec_00X_<nombre>.py`
- **Comando:** `uv run pytest tests/test_spec_00X_<nombre>.py -v`

| AC | Test |
|---|---|
| AC1 | `test_ac1_<nombre>` |

## 6. Fuera de alcance

Qué NO cubre este spec, y a qué spec o a `BACKLOG.md` pertenece.

## 7. Referencias

Solo las que sustentan el hallazgo. Sin apelación a autoridad decorativa.
