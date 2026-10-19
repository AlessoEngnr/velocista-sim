# Backlog

Pendientes fuera de las specs en curso, agrupados por la versión o la rama donde se harán.

## Contrato v1.1

- **`load_profile`**: base del armador de robots del framework.
- **Informar el perfil efectivo al cliente**: `default` y `source` de cada parámetro (además de
  `measured`). El servidor ya los conoce (aparecen en el log de apertura de sesión); hoy ningún
  mensaje del contrato los envía, por eso la pestaña Calibración del panel solo muestra
  "MEDIDO" o "POR DEFECTO" (specs/003-panel-laboratorio, Fase 6).

## 002-polish (rama aparte, después del PR del panel)

- Tareas pendientes de la Fase 6 de `specs/002-simulador/tasks.md`: T052–T056.
- Validar en el servidor `adc_white`, `adc_black` y `adc_noise` de `set_profile` según
  `adc_bits` del perfil (máximo 2^`adc_bits` − 1, p. ej. 4095 con 12 bits). Hoy el servidor
  acepta 4524 con 12 bits porque solo aplica el rango genérico 0–65535 del contrato. El panel ya
  limita esos campos según el `hello` (specs/003-panel-laboratorio, Fase 7).

## 001

- T063: revisión del contrato con front, backend y firmware (`specs/001-contrato-v1/tasks.md`).

## Simulador v2

- Encoders e IMU.
- Modo batch.

## Otros

- Exportación "Para el simulador" en el trazador de pistas.
- Activar Serverless en Railway (la primera conexión después de dormir puede dar 502:
  reintentar).
- Para el optimizador: promediar varias corridas por configuración, o fijar la semilla para
  comparar.
