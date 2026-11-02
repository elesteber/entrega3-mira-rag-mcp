# Guía de colas y servicios externos

| Campo | Valor |
|---|---|
| Código | GUI-COL |
| Versión | 1 |
| Estado | Vigente |
| Vigencia | Desde el 1 de agosto de 2026 |
| Responsable | Equipo de Ingeniería de Plataforma, DPRIME |

> Documento ficticio elaborado para el Taller de Desarrollo de Software Conducido por Agentes de IA (Universidad de Valparaíso). No corresponde a una política real de DPRIME ni de ninguna organización.

## 1. Servicios de los que depende MIRA

| Código | Servicio | Tipo |
|---|---|---|
| SRV-MOD | Proveedor de modelos de lenguaje y visión | Externo |
| SRV-OCR | Extracción de texto | Externo |
| SRV-ROS | Comparación de rostros | Interno |
| SRV-REG | Consulta a registros públicos | Externo |
| SRV-COL | Cola de procesamiento | Interno |
| SRV-API | Interfaz de programación pública | Interno |

## 2. Comportamiento ante una falla

Cuando un servicio externo no responde, la plataforma sigue aceptando casos y los mantiene en cola. Un caso en cola nunca se descarta por esa causa.

Los reintentos automáticos se hacen con espera creciente: al minuto, a los 5 minutos, a los 15 minutos y luego cada 30 minutos.

## 3. Umbrales de alerta

- Un caso que lleva más de seis horas en cola genera un incidente S2.
- Un servicio con latencia sostenida sobre 5.000 milisegundos durante 15 minutos se marca como degradado.
- Un servicio que no responde durante 5 minutos se marca como caído.
