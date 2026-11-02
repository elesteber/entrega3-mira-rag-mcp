# Kit de la Entrega 3 · Caso MIRA

Material de trabajo para la Entrega 3 del Taller de Desarrollo de Software Conducido por Agentes de IA (Universidad de Valparaíso).

Todo el contenido es **ficticio** y fue elaborado para fines docentes. No corresponde a políticas, personas ni organizaciones reales.

## Contenido

Una carpeta por caso de uso. Cada equipo trabaja solo con la carpeta del caso que eligió.

| Carpeta | Caso de uso |
|---|---|
| CU-1_operador_revision | Asistente del operador de revisión |
| CU-2_soporte_operacion | Asistente de soporte y operación de la plataforma |
| CU-3_incorporacion_organizaciones | Asistente de incorporación de organizaciones |
| CU-4_modulos_consumo | Asistente de módulos y consumo |

Cada carpeta contiene:

- `corpus/`: documentos en Markdown que el RAG debe indexar. Cada documento declara en su encabezado su código, versión, estado y vigencia.
- `datos/`: un Excel con las tablas de la base de datos que consulta el servidor MCP. La hoja `LEEME` describe cada tabla.

## Cómo usarlo

1. Indexar los documentos de `corpus/`, conservando como metadatos el código, la versión, el estado y la vigencia de cada documento, además de la sección de cada fragmento.
2. Agregar al corpus los capítulos de la Descripción del proyecto MIRA que sean pertinentes al caso de uso.
3. Cargar cada hoja del Excel como una tabla en la base de datos elegida.
4. Implementar el servidor MCP con herramientas que consulten esa base mediante consultas parametrizadas.

## Advertencia

El material reproduce las condiciones reales de un corpus empresarial: hay documentos derogados junto a sus versiones vigentes, fuentes que no coinciden entre sí o con los datos, preguntas razonables que ninguna fuente responde y contenido que intenta manipular al asistente. Nada de esto está señalado. Encontrarlo y tratarlo correctamente es parte de la evaluación.
