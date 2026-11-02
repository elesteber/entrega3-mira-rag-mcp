# Guía de incorporación de organizaciones

| Campo | Valor |
|---|---|
| Código | GUI-INC |
| Versión | 2 |
| Estado | **Vigente** |
| Vigencia | Desde el 1 de septiembre de 2026 |
| Reemplaza a | GUI-INC versión 1 |
| Responsable | Equipo de Implementación, DPRIME |

> Documento ficticio elaborado para el Taller de Desarrollo de Software Conducido por Agentes de IA (Universidad de Valparaíso). No corresponde a una política real de DPRIME ni de ninguna organización.

## 1. Meta

Una organización nueva debe poder procesar casos de prueba el mismo día en que firma, a partir de la plantilla de su caso de uso, y estar en producción dentro de diez días hábiles desde la firma. La incorporación consiste en adaptar lo que difiere de la plantilla, no en construir el proceso completo.

## 2. Etapas

| Etapa | Contenido | Días hábiles desde la firma |
|---|---|---|
| E0. Alta | Creación de la organización, del ambiente de integración y de los usuarios iniciales | Día 0 |
| E1. Plantilla | Asignación de la plantilla del caso de uso (ver FIC-PLA) y carga de casos de ejemplo | Día 0 |
| E2. Adaptación | Ajuste de módulos, reglas y umbrales; registro de formularios propios | Días 1 a 5 |
| E3. Integración | Conexión con los sistemas de la organización y prueba en el ambiente de integración | Días 1 a 8 |
| E4. Pruebas | Ejecución de casos de ejemplo de punta a punta y revisión de resultados con la organización | Días 6 a 9 |
| E5. Salida a producción | Verificación de criterios y paso a producción | Día 10 |

## 3. Criterios de salida a producción

Una organización pasa a producción solo si se cumplen todos los criterios siguientes:

1. Todas las tareas obligatorias de las etapas E0 a E4 están completadas.
2. La integración fue probada con éxito en el ambiente de integración.
3. Los umbrales de decisión fueron aprobados por dos supervisores de la organización, según la política de decisión y umbrales.
4. Si el proveedor de modelos procesa datos fuera del país de la organización, está firmada la autorización de transferencia internacional de datos.
5. Si la plantilla incluye módulos biométricos, está firmada la autorización de tratamiento de datos biométricos.
6. Todos los formularios propios de la organización están en estado «operativo».

Ninguna organización pasa a producción con tareas obligatorias pendientes, aunque se haya cumplido la fecha objetivo.

## 4. Permisos

- Cada ejecutivo de implementación ve y modifica solo las organizaciones que tiene asignadas.
- Un ejecutivo puede marcar como completadas las tareas de las etapas E0 a E4 de sus organizaciones.
- La tarea de salida a producción (E5) solo la marca el jefe de implementación.
