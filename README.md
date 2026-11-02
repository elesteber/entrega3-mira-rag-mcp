# MIRA CU-3 · Asistente de Incorporación de Organizaciones
**Entrega 3 — Taller de Desarrollo de Software Conducido por Agentes de IA**  
**Escuela de Ingeniería Informática — Universidad de Valparaíso**

- **Repositorio:** `https://github.com/elesteber/entrega3-mira-rag-mcp`
- **Fecha y Hora de Entrega:** Lunes 9 de noviembre de 2026, 14:00 hrs.
- **Equipo:** 4 integrantes.
- **Caso de Uso Seleccionado:** **CU-3 — Asistente de incorporación de organizaciones** (*Onboarding Assistant*).
- **Estado Actual del Proyecto:** **Fase Preparatoria Documental (Previa a inicialización de GitHub Spec Kit)**.

---

## 1. Propósito y Objetivo General

El objetivo de este proyecto es diseñar, construir y evaluar un asistente conversacional inteligente para el **Equipo de Implementación de DPRIME SpA** en la plataforma **MIRA**. El asistente permite auditar el avance del proceso de incorporación de organizaciones clientes, verificar el cumplimiento de los criterios normativos de salida a producción según su plantilla (tales como admisión clínica o apertura de cuentas), consultar métricas de integración técnica y preparar la actualización de tareas con estricto control de acceso y confirmación humana.

El foco evaluativo no radica en la elocuencia de conversación del modelo, sino en su **evidencia verificable, trazabilidad y control**:
- Cada regla proviene de un fragmento documental indexado por RAG y citado con precisión (fuente, sección, versión).
- Cada dato vivo proviene de una llamada registrada a una herramienta del servidor MCP propio.
- El asistente reconoce explícitamente cuándo no existe evidencia y se abstiene.
- **Ninguna acción con efecto colateral se ejecuta sin confirmación explícita de un humano (Human-in-the-Loop).**

> **Pregunta de Referencia Oficial:**  
> *«¿Qué le falta a la organización ORG-07 para pasar a producción con la plantilla de admisión clínica?»*

---

## 2. Principios Innegociables del Asistente (PR-1 a PR-7)

El comportamiento del agente está gobernado por siete principios operativos:

1. **PR-1 (Decisión humana):** El asistente no decide sobre un caso. Explica, sugiere y prepara; la decisión final la confirma una persona.
2. **PR-2 (Citas obligatorias):** Toda afirmación sobre reglas, políticas o contratos cita el fragmento que la respalda (fuente, sección y versión). Sin cita, no se afirma.
3. **PR-3 (Abstención):** Si la respuesta no está en el corpus, el asistente lo dice explícitamente. La ausencia de evidencia jamás se presenta como respuesta favorable.
4. **PR-4 (Conflicto entre fuentes vigentes):** Si dos fuentes vigentes o normas difieren, el asistente expone ambas posturas y no toma partido por su cuenta.
5. **PR-5 (Datos vivos vía MCP):** Todo dato sobre una organización o tarea proviene de una herramienta MCP visible en la interfaz; el LLM jamás inventa datos.
6. **PR-6 (Acciones con confirmación):** Las acciones que modifiquen el estado del sistema requieren confirmación explícita del usuario. Las consultas nunca deben producir efectos secundarios.
7. **PR-7 (Control de acceso por rol):** El asistente solo permite acceder y operar sobre las organizaciones asignadas al rol del usuario conectado.

---

## 3. Stack Tecnológico Propuesto

| Capa / Componente | Tecnología Seleccionada | Justificación Técnica |
|---|---|---|
| **IDE & Agente de Desarrollo** | Antigravity (`agy`) | Entorno oficial del taller con soporte para desarrollo agentic. |
| **Metodología de Desarrollo** | GitHub Spec Kit (Spec-Driven Development) | Especificaciones formales, constitución inmutable y desglose de tareas trazables. |
| **Backend REST & Orquestador** | Python 3.12 + FastAPI + Pydantic v2 | Alto rendimiento asincrónico, validación tipada y ruteo limpio. |
| **Gestión de Entorno Python** | `uv` | Gestión determinista de dependencias ultrarrápida. |
| **Servidor MCP** | FastMCP (Python) | Servidor MCP propio con consultas SQL parametrizadas a SQLite. |
| **Base de Datos Relacional** | SQLite (`mira_cu3.db`) | Portabilidad local y persistencia de las 6 tablas del kit. |
| **Motor RAG & Vector Store** | ChromaDB (embebido) | Almacén vectorial local con filtrado estructurado por metadatos. |
| **Modelo de Embeddings** | `paraphrase-multilingual-MiniLM-L12-v2` | Modelo denso con alta calidad semántica en español y bajo consumo de CPU. |
| **Proveedor LLM** | Google Gemini Flash (API) | Modelo de alta velocidad con amplio contexto y bajo costo. |
| **Frontend Web** | React 18 + Vite + TypeScript | Aplicación web en español con trazabilidad de citas, llamadas MCP y modales. |
| **Evaluación Automatizada** | `pytest` + Golden Set (20 preguntas) | Métricas cuantitativas de Recall@k, Precisión de citas y Fidelidad. |

---

## 4. Estructura del Repositorio

```text
entrega3-mira-rag-mcp/
├── .gitignore                   # Exclusión de entornos virtuales, cachés, DBs y temporales
├── .env.example                 # Variables de entorno y configuración de ejemplo
├── AGENTS.md                    # Directrices de colaboración para agentes de IA
├── PAUTA_ENTREGA_3.md           # Transcripción textual completa del PDF oficial de la entrega
├── README.md                    # Documento principal del repositorio
│
├── archivos-base/               # Fuentes primarias inmutables del proyecto
│   ├── Entrega_3_MIRA_RAG_MCP.pdf
│   ├── Kit_Entrega_3_MIRA.zip
│   └── Kit_Entrega_3_MIRA/      # Material descomprimido con los 4 casos de uso
│       └── CU-3_incorporacion_organizaciones/
│           ├── corpus/          # GUI-INC_v1, GUI-INC_v2, FIC-PLA, REQ-INT, POL-FOR
│           └── datos/           # CU-3_datos.xlsx (7 hojas de datos de prueba)
│
├── docs/                        # Documentación preparatoria previa a Spec Kit
│   ├── contexto-proyecto.md     # Contexto de MIRA, DPRIME y alcance del CU-3
│   ├── auditoria-fuentes.md     # Inspección técnica, discrepancias y trampas detectadas
│   ├── alcance-cu3.md           # Requisitos funcionales (REQ-F-*), historias BDD y exclusiones
│   ├── corpus-cu3.md            # Inventario del corpus, tokens, vigencias y metadatos
│   ├── datos-cu3.md             # Diccionario de datos, tablas, claves y casos de prueba
│   ├── arquitectura-propuesta.md# Diagramas Mermaid de arquitectura y flujos de secuencia
│   ├── contratos-borrador.md    # Especificaciones preliminares de API REST y Tools MCP
│   ├── plan-evaluacion.md       # Golden Set (20 preguntas), métricas y guion demo D1-D8
│   ├── riesgos-controles.md     # Matriz de riesgos y guardrails de seguridad (C7)
│   ├── organizacion-equipo.md   # Asignación de responsabilidades de los 4 integrantes
│   ├── decisiones.md            # Registro formal de decisiones de arquitectura (ADRs)
│   └── spec-kit-handoff.md      # Guía de transición e insumos para GitHub Spec Kit
│
├── backend/                     # Código fuente del backend (FastAPI, RAG, MCP, DB)
│   ├── app/                     # API REST, autenticación simulada y orquestador
│   ├── rag/                     # Pipeline de indexación y recuperación vectorial
│   ├── mcp/                     # Servidor FastMCP y validaciones de negocio
│   ├── data/                    # SQLite y directorio persistente de ChromaDB
│   └── README.md                # Estado y responsabilidades del backend
│
├── frontend/                    # Aplicación web React + Vite (en español)
│   └── README.md                # Componentes visuales, chat, citas y modales
│
├── tests/                       # Suite de pruebas y benchmarking
│   └── README.md                # Golden Set y framework de evaluación con pytest
│
└── informe/                     # Artefactos y redacción del informe final (máx. 12 planas)
    └── README.md                # Estructura del informe según capítulo 11 de la pauta
```

---

## 5. Distribución de Responsabilidades del Equipo (4 Integrantes)

- **Integrante 1 (Especialista RAG):** Preprocesamiento del corpus, metadatos, embeddings, indexación offline en ChromaDB, recuperación y comparativa experimental de chunking.
- **Integrante 2 (Especialista MCP y Datos):** Ingestión del Excel a SQLite, desarrollo del servidor FastMCP, consultas parametrizadas y validación de reglas de negocio en el backend.
- **Integrante 3 (Arquitecto Backend):** API FastAPI, cliente MCP, integración con Google Gemini Flash, orquestación, gestión de contexto seguro y trazabilidad.
- **Integrante 4 (Ingeniero Frontend y Evaluación):** Aplicación React, experiencia de usuario, despliegue de citas, modales de confirmación, Golden Set y preparación de la demo D1-D8.

---

## 6. Documentación Preparatoria de Referencia

Para consultar los detalles de diseño antes de inicializar la implementación:
- [Contexto del Proyecto](docs/contexto-proyecto.md)
- [Auditoría de Fuentes y Discrepancias Detectadas](docs/auditoria-fuentes.md)
- [Alcance Funcional y Requisitos del CU-3](docs/alcance-cu3.md)
- [Inventario del Corpus Documental](docs/corpus-cu3.md)
- [Modelo de Datos y Análisis del Excel](docs/datos-cu3.md)
- [Arquitectura Propuesta y Diagramas Mermaid](docs/arquitectura-propuesta.md)
- [Borrador de Contratos de API y MCP](docs/contratos-borrador.md)
- [Plan de Evaluación y Golden Set](docs/plan-evaluacion.md)
- [Matriz de Riesgos y Guardrails (C7)](docs/riesgos-controles.md)
- [Organización y Protocolo Git del Equipo](docs/organizacion-equipo.md)
- [Registro de Decisiones de Arquitectura (ADRs)](docs/decisiones.md)
- [Guía de Transición a Spec Kit (Handoff)](docs/spec-kit-handoff.md)

---

## 7. Próximos Pasos

1. **Inicialización de GitHub Spec Kit:**  
   Ejecutar en la raíz del repositorio el comando oficial:
   ```bash
   specify init --ai agy
   ```
2. **Generación de la Constitución:** Consagrar los principios PR-1 a PR-7 a partir de `AGENTS.md`.
3. **Especificación y Planificación SDD:** Crear las especificaciones funcionales (`spec.md`) y el plan de implementación (`plan.md`) alimentándose de los documentos de `docs/`.
4. **Versionado del Golden Set:** Asegurar el commit del Golden Set definitivo en `tests/` antes de la primera ejecución completa del pipeline.
