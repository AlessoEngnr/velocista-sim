# Interfaz: validador del contrato (`velocista_sim.contract`)

Interfaz pública del módulo que valida mensajes contra el contrato v1. La usan los tests de este
repo, los del servidor en specs posteriores y cualquier cliente en Python (backend, optimizador).
Los identificadores van en inglés; los textos de `Violation.message`, en español.

## Tipos

```python
@dataclass(frozen=True)
class Violation:
    rule: str        # palabra clave de JSON Schema ("required", "maximum", …) o regla de data-model.md
    path: str        # JSON Pointer dentro del mensaje ("" = raíz, "/sensors/3")
    message: str     # explicación en español

@dataclass(frozen=True)
class ValidationResult:
    violations: tuple[Violation, ...]
    context_checked: bool   # False si faltó hello y no se aplicaron reglas contextuales

    @property
    def ok(self) -> bool: ...   # True si no hay violaciones
```

## Funciones

| Firma | Qué hace |
|---|---|
| `validate_message(message: dict, hello: dict \| None = None) -> ValidationResult` | Mensaje servidor→cliente. Elige el schema por `type`; con `hello`, aplica además la capa contextual. Si `message` es un `hello`, se usa a sí mismo como contexto. |
| `validate_command(command: dict) -> ValidationResult` | Comando cliente→servidor. Elige el schema por `cmd`; para `load_track` aplica también la semántica de pista. |
| `validate_track(track: dict) -> ValidationResult` | Pista track v1: schema + semántica de pista. |
| `validate_profile(profile: dict) -> ValidationResult` | Perfil del robot. |
| `effective_profile(profile: dict) -> dict[str, object]` | Valor efectivo por parámetro (`measured` si no es `null`; si no, `default`). |

Ninguna función lanza excepciones por mensajes inválidos; las devuelve como `Violation`. Un
`message` que no es `dict` produce la violación `rule="type"`, `path=""`. Un `type`/`cmd`
ausente o desconocido produce `unknown_type`/`unknown_cmd`.

Las reglas de secuencia de una sesión (orden de mensajes, `seq`, `t_ms`) no forman parte de esta
interfaz; quedan para la spec del servidor (research R8).

## Carga de schemas

`load_schemas(schema_dir: Path | None = None)` devuelve el registro de schemas. Por defecto busca
`contract/schemas/` subiendo desde el módulo hasta la raíz del repo (ver research R6). Los
schemas se cargan una vez por proceso y se reutilizan.

## Garantías

- Determinismo: el mismo mensaje y el mismo `hello` producen las mismas violaciones, en orden
  estable (por `path` y luego por `rule`).
- Sin E/S salvo leer `contract/schemas/` la primera vez.
- Compatibilidad: agregar reglas nuevas es compatible; cambiar el identificador de una regla
  existente requiere actualizar los ejemplos inválidos que la usan.
