# Manual de gestión de incidentes de la plataforma

| Campo | Valor |
|---|---|
| Código | MAN-INC |
| Versión | 2 |
| Estado | Vigente |
| Vigencia | Desde el 1 de agosto de 2026 |
| Responsable | Equipo de Soporte y Operación, DPRIME |

> Documento ficticio elaborado para el Taller de Desarrollo de Software Conducido por Agentes de IA (Universidad de Valparaíso). No corresponde a una política real de DPRIME ni de ninguna organización.

## 1. Severidades

| Severidad | Descripción | Tiempo máximo de primera respuesta |
|---|---|---|
| S1 | La plataforma no procesa casos para una o más organizaciones | 15 minutos, todos los días a toda hora |
| S2 | Procesamiento degradado: demoras sostenidas o un servicio externo caído | 1 hora, todos los días a toda hora |
| S3 | Casos individuales detenidos o con error | 4 horas hábiles |
| S4 | Consultas y solicitudes sin impacto en la operación | 1 día hábil |

## 2. Registro

Todo incidente se registra con su severidad, las organizaciones afectadas, la hora de inicio y las acciones realizadas. Un incidente sin registro no existe para efectos del servicio.

## 3. Diagnóstico de un caso

Para diagnosticar un caso detenido, el técnico de turno revisa el código de error, el registro técnico del caso y el estado del servicio del que depende. Si con eso no basta, el técnico de turno puede abrir la evidencia del caso para entender qué falló.

## 4. Reproceso de casos

Reprocesar es volver a ejecutar el flujo sobre un caso que no terminó. Reglas:

- Solo se reprocesan casos en estado «error» o «detenido».
- Nunca se reprocesa un caso que ya tiene decisión final.
- Antes de reprocesar, verifique en el catálogo de errores (CAT-ERR) si el código es reprocesable y verifique que el servicio del que depende el caso esté operativo.
- Un caso admite como máximo tres reprocesos. Si el tercero falla, se escala a Ingeniería como incidente S3 y no se vuelve a intentar.
- Pueden reprocesar los usuarios con rol de soporte nivel 1, soporte nivel 2 o ingeniería.
- Los reprocesos por error interno de la plataforma no se contabilizan como validaciones.

## 5. Comunicación con las organizaciones

Cuando una organización tiene casos con procesamiento demorado por más de 30 minutos, se le avisa por correo electrónico y por la interfaz. El aviso indica cuántos casos están afectados y que ninguno se ha perdido.
