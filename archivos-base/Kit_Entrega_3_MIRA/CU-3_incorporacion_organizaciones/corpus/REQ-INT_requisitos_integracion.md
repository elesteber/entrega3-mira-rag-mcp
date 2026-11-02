# Requisitos técnicos de integración

| Campo | Valor |
|---|---|
| Código | REQ-INT |
| Versión | 2 |
| Estado | Vigente |
| Vigencia | Desde el 1 de septiembre de 2026 |
| Responsable | Equipo de Ingeniería de Plataforma, DPRIME |

> Documento ficticio elaborado para el Taller de Desarrollo de Software Conducido por Agentes de IA (Universidad de Valparaíso). No corresponde a una política real de DPRIME ni de ninguna organización.

## 1. Modos de integración

| Modo | Cuándo usarlo |
|---|---|
| Interfaz de programación asincrónica | Modo por defecto. La organización envía el caso, MIRA responde «recibido» en menos de un segundo y avisa el resultado mediante una llamada de vuelta |
| Interfaz de programación sincrónica | Solo para documentos livianos, con respuesta inmediata |
| Intercambio de archivos | Para sistemas que no exponen servicios web. MIRA lee y deja archivos en una carpeta compartida con ciclos de 30 minutos |

## 2. Autenticación

Los usuarios pueden autenticarse con credenciales administradas por MIRA o mediante federación con el directorio corporativo de la organización. Las integraciones de sistema usan credenciales propias por ambiente, que se almacenan cifradas.

## 3. Límites de llamadas

El límite general es de mil llamadas por minuto por organización, en todos los ambientes. Las llamadas que superan el límite se encolan.

## 4. Ambientes

- Cada organización tiene un ambiente de integración y uno de producción.
- El ambiente de integración se alimenta con casos de ejemplo provistos por DPRIME.
- Ningún dato real de la organización se usa fuera de producción, salvo autorización expresa y con los datos personales enmascarados.

## 5. Prueba de integración

Una integración se considera probada cuando la organización envía al menos 20 casos de ejemplo en el ambiente de integración y recibe la llamada de vuelta de todos ellos sin errores. Durante la carga de prueba no deben superarse cien llamadas por minuto.
