# Catálogo de códigos de error

| Campo | Valor |
|---|---|
| Código | CAT-ERR |
| Versión | 2 |
| Estado | **Vigente** |
| Vigencia | Desde el 1 de septiembre de 2026 |
| Reemplaza a | CAT-ERR versión 1 |
| Responsable | Equipo de Ingeniería de Plataforma, DPRIME |

> Documento ficticio elaborado para el Taller de Desarrollo de Software Conducido por Agentes de IA (Universidad de Valparaíso). No corresponde a una política real de DPRIME ni de ninguna organización.

## 1. Códigos

| Código | Significado | ¿Reprocesable? | Acción |
|---|---|---|---|
| E-101 | Evidencia ilegible | No | Solicitar el reenvío de la evidencia. No se reprocesa: el resultado sería el mismo |
| E-102 | Formato de archivo no soportado | No | Informar a la organización los formatos aceptados |
| E-207 | Tiempo de espera agotado con el proveedor de modelos | Sí, con condición | Reprocesar solo si el servicio SRV-MOD está operativo. Si está degradado o caído, no reprocesar: el caso permanece en cola y se reintenta automáticamente |
| E-208 | Cuota del proveedor de modelos agotada | No | Registrar incidente S2 y escalar a Ingeniería |
| E-305 | Módulo de análisis no disponible | Sí, con condición | Reprocesar cuando el servicio del que depende el módulo vuelva a estar operativo |
| E-311 | La versión de módulo fijada en el flujo no está disponible | No | Escalar a Ingeniería. No reprocesar con otra versión: un flujo no cambia de versión de módulo sin autorización de la organización |
| E-410 | Límite de llamadas por minuto superado | No aplica | La llamada no se rechaza: se encola y se procesa cuando hay capacidad. No requiere acción de soporte salvo que la cola supere seis horas |
| E-512 | Error interno de la plataforma | Sí, con condición | Reprocesar una vez. Si vuelve a fallar, escalar a Ingeniería |

## 2. Cambios respecto de la versión 1

- E-207 deja de ser reprocesable de inmediato: depende del estado del servicio de modelos.
- E-410 deja de rechazar llamadas: ahora se encolan.
- E-512 admite un reproceso antes de escalar.
- Se agregan E-208 y E-311.
