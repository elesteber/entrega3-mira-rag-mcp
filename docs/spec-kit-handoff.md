# Guía de Transición hacia GitHub Spec Kit (Handoff)

Este documento define el puente de conexión entre la documentación preparatoria elaborada en esta fase y la posterior inicialización formal del flujo de **Desarrollo Dirigido por Especificaciones (Spec-Driven Development - SDD)** utilizando **GitHub Spec Kit** con integración **Antigravity (`agy`)**.

---

## 1. Mapeo de Documentación como Entrada para Spec Kit

Cuando el equipo ejecute el flujo de Spec Kit, utilizará la documentación de este repositorio como insumos directos y trazables:

```text
Documentación Preparatoria               Artefactos Generados por Spec Kit
┌──────────────────────────────┐        ┌───────────────────────────────────┐
│ • AGENTS.md                  │ ────►  │ CONSTITUCIÓN                      │
│ • docs/contexto-proyecto.md  │        │ (.specify/memory/constitution.md) │
│ • Principios PR-1 a PR-7     │        │ Principios innegociables del bot  │
└──────────────────────────────┘        └───────────────────────────────────┘

┌──────────────────────────────┐        ┌───────────────────────────────────┐
│ • docs/alcance-cu3.md        │ ────►  │ ESPECIFICACIÓN FUNCIONAL          │
│ • docs/auditoria-fuentes.md  │        │ (specs/001-cu3-onboarding/spec.md)│
│ • docs/contratos-borrador.md │        │ Requisitos REQ-F-*, Historias BDD │
└──────────────────────────────┘        └───────────────────────────────────┘

┌──────────────────────────────┐        ┌───────────────────────────────────┐
│ • docs/arquitectura-propuesta│ ────►  │ PLAN TÉCNICO Y ARQUITECTURA       │
│ • docs/decisiones.md (ADRs)  │        │ (specs/001-cu3-onboarding/plan.md)│
│ • docs/corpus-cu3.md         │        │ Stack, diagramas, esquemas BD     │
│ • docs/datos-cu3.md          │        │                                   │
└──────────────────────────────┘        └───────────────────────────────────┘

┌──────────────────────────────┐        ┌───────────────────────────────────┐
│ • docs/organizacion-equipo.md│ ────►  │ DESGLOSE DE TAREAS                │
│ • docs/plan-evaluacion.md    │        │ (specs/001-cu3-onboarding/tasks.md│
│ • docs/riesgos-controles.md  │        │ Tareas atómicas por integrante    │
└──────────────────────────────┘        └───────────────────────────────────┘
```

---

## 2. Insumos Específicos por Etapa de Spec Kit

### 2.1 Para la Constitución del Proyecto (`constitution.md`)
- **Fuente principal:** `AGENTS.md` y `docs/contexto-proyecto.md §5`.
- **Reglas no negociables a consagrar:**
  1. Principios PR-1 (Decisión humana), PR-2 (Citas obligatorias), PR-3 (Abstención), PR-4 (Manejo de conflictos), PR-5 (Datos solo vía MCP), PR-6 (Confirmación de mutaciones) y PR-7 (Control de acceso por rol).
  2. Inmutabilidad de los datos base entregados en el kit (`archivos-base/`).
  3. Obligatoriedad de citas con código de documento, sección y versión.

### 2.2 Para la Especificación del Feature (`spec.md`)
- **Fuente principal:** `docs/alcance-cu3.md` y `docs/contratos-borrador.md`.
- **Contenido a incorporar:**
  - Historias de usuario HU-01 a HU-04 en formato *Given/When/Then*.
  - Requisitos funcionales identificados (`REQ-F-01` a `REQ-F-10`).
  - Casos de error y condiciones de borde (ej: superar tasa de llamadas de `REQ-INT`, falta de ejemplos en `POL-FOR`).

### 2.3 Para el Plan de Arquitectura (`plan.md`)
- **Fuente principal:** `docs/arquitectura-propuesta.md`, `docs/decisiones.md`, `docs/datos-cu3.md` y `docs/corpus-cu3.md`.
- **Contenido a incorporar:**
  - Selección tecnológica: FastAPI + SQLite + ChromaDB + FastMCP + Gemini Flash + React/Vite.
  - Diagramas Mermaid de arquitectura y secuencia de dos fases.
  - Esquema DDL para la base SQLite `mira_cu3.db` a partir de las 6 tablas del Excel.

### 2.4 Para el Plan de Tareas (`tasks.md`)
- **Fuente principal:** `docs/organizacion-equipo.md`, `docs/plan-evaluacion.md` y `docs/riesgos-controles.md`.
- **Contenido a incorporar:**
  - Tareas divididas por los 4 integrantes:
    - Rama RAG: Indexación, chunking semántico y benchmarking.
    - Rama MCP: Ingestión SQLite, herramientas parametrizadas y validación de reglas de negocio.
    - Rama Backend: Orquestador FastAPI, cliente MCP, cliente Gemini y trazabilidad.
    - Rama Frontend y Evaluación: UI React, visualizador de evidencias, Golden Set versionado y guion de demostración D1 a D8.

---

## 3. Instrucciones para la Inicialización Posterior de Spec Kit

Cuando el equipo decida inicializar Spec Kit, deberá seguir estos pasos:

1. **Requisitos Previos:**
   - Estar ubicado en la raíz del repositorio: `/home/lester/Documents/LLMtareas/tareas/trabajo-final/entrega3-mira-rag-mcp`.
   - Contar con la CLI de GitHub Spec Kit (`specify`).
2. **Comando de Inicialización Seleccionado:**
   - Se debe inicializar con el proveedor **Antigravity (`agy`)**:
     ```bash
     specify init --ai agy
     ```
   - ⚠️ **Recordatorio:** No usar `--ai gemini` ni inicializadores de otros agentes.
3. **Flujo de Ejecución Posterior:**
   - `/speckit-constitution` (usando `AGENTS.md` como base).
   - `/speckit-specify` (usando `docs/alcance-cu3.md`).
   - `/speckit-plan` (usando `docs/arquitectura-propuesta.md` y ADRs).
   - `/speckit-tasks` (usando `docs/organizacion-equipo.md`).
   - `/speckit-implement` (ejecución paso a paso).

---

## 4. Confirmación de No Interferencia

Se certifica que en esta etapa preparatoria:
- **NO** se ejecutó ningún comando de `specify-cli`.
- **NO** se crearon carpetas `.specify/` ni `.agents/skills/`.
- **NO** se alteraron las plantillas nativas de Spec Kit.
- La base documental queda completamente limpia y lista para ser consumida como contexto confiable.
