# Fichas de módulos de análisis

| Campo | Valor |
|---|---|
| Código | FIC-MOD |
| Versión | 2 |
| Estado | Vigente |
| Vigencia | Desde el 1 de septiembre de 2026 |
| Responsable | Dirección de Producto, DPRIME |

> Documento ficticio elaborado para el Taller de Desarrollo de Software Conducido por Agentes de IA (Universidad de Valparaíso). No corresponde a una política real de DPRIME ni de ninguna organización.

## 1. Módulos incluidos en la tarifa base

| Código | Módulo | Qué hace |
|---|---|---|
| MOD-OCR | Extracción de campos | Lee el texto y los campos relevantes de documentos e imágenes |
| MOD-QR | Lectura de códigos | Lee códigos de barras y códigos QR y verifica su contenido |

## 2. Módulos adicionales

Los módulos adicionales se cobran por cada validación en que el módulo se ejecutó, además de la tarifa del tramo.

| Código | Módulo | Qué hace | Cargo adicional por validación |
|---|---|---|---|
| MOD-FIR | Validación de firmas | Detecta y compara firmas y timbres | 0,004 UF |
| MOD-ROS | Comparación de rostros | Compara el rostro de una captura con el del documento de identidad | 0,008 UF |
| MOD-VID | Prueba de vida | Verifica que la captura corresponda a una persona presente | 0,010 UF |
| MOD-VDO | Análisis de video | Responde preguntas sobre un video y detecta eventos | 0,025 UF |

## 3. Módulos en evaluación

| Código | Módulo | Estado |
|---|---|---|
| MOD-AUD | Análisis de audio | En evaluación. No disponible comercialmente y sin tarifa definida |

## 4. Versiones

Cada flujo queda fijado a una versión específica de cada módulo. Activar un módulo, o actualizar su versión, no altera el comportamiento de un flujo que ya está en producción sin la autorización explícita de la organización.
