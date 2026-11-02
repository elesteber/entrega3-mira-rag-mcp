# Entregables del Informe Escrito (Caso MIRA CU-3)

Este directorio está reservado para la redacción, artefactos y generación del informe escrito final en formato PDF para la Entrega 3.

> **Estado actual:** ESTRUCTURA Y LÍMITES DE PÁGINAS DOCUMENTADOS.  
> La redacción del informe se consolidará conforme avance la implementación y se obtengan las métricas experimentales reales.

---

## 1. Estructura Oficial del Informe (Límite Máximo: 12 Planas)

Según la pauta oficial (`PAUTA_ENTREGA_3.md` / PDF oficial capítulo 11), el informe debe estructurarse estrictamente en las siguientes secciones:

| Sección | Extensión Máxima | Foco Principal |
|---|---|---|
| **11.1 Resumen ejecutivo** | 1/2 plana | Qué hace el asistente, para quién, desempeño numérico comprensible, qué no hace y recomendaciones (sin jerga técnica). |
| **11.2 Caso de uso y especificación** | 1,5 planas | Justificación de CU-3, contradicción de fuentes identificada y citada, flujos principal y alternativos, clasificación RAG vs MCP, IDs de requisitos y principios PR-1 a PR-7. |
| **11.3 Diseño e implementación del RAG** | 2 planas | Inventario del corpus con metadatos y tokens, justificación experimental del chunking y búsqueda, pipeline desacoplado, formato de citas y manejo de vigencia/conflictos. |
| **11.4 Diseño e implementación del servidor MCP** | 1,5 planas | Primitivas mínimas parametrizadas sobre SQLite, contratos de tools, validación de reglas de negocio en servidor, manejo de errores y permisos. |
| **11.5 Arquitectura e implementación front y back** | 1,5 planas | Diagramas de arquitectura y secuencia, datos enviados al modelo, trazabilidad en UI, honestidad ante fallos. |
| **11.6 Evaluación** | 3 planas | Estrategia de pruebas, composición del Golden Set (mínimo 20 preguntas), métricas (Recall@k, Fidelidad, Precisión de citas, Abstención), matriz de fallos recuperación vs generación y ciclo de mejora. |
| **11.7 Riesgos y controles** | 1 plana | Identificación y configuración de al menos 3 riesgos con sus guardrails y pruebas. |
| **11.8 Discusión y conclusiones** | 1 plana | Reflexión crítica de qué resolvió cada componente, limitaciones honestas, aprendizajes transferibles y pendientes concretos. |

---

## 2. Ponderación de la Evaluación

- **Informe escrito + Repositorio:** 50% de la nota final.
- **Presentación oral + Demostración en vivo:** 50% de la nota final.
