# Frontend del Asistente MIRA CU-3 (Release v3.0)

**Requisitos de Entorno:** Node.js `^20.19.0` o `>=22.12.0` y npm.

Este directorio contiene la aplicación web en español para los operadores del equipo de implementación de DPRIME SpA en la plataforma **MIRA (CU-3)**. La interfaz prioriza la **evidencia verificable**, la **trazabilidad de llamadas MCP** y el **control humano en dos pasos (Human-in-the-Loop)** antes de cualquier mutación de datos.

> **Estado de Implementación:** 100% implementado, integrado y probado (62 pruebas aprobadas en Vitest, compilación limpia en TypeScript y 0 errores/advertencias en ESLint).

---

## 1. Componentes Principales de la Interfaz

```text
frontend/src/
├── App.tsx                     # Componente raíz: orquestación de layout, sesión y modales
├── main.tsx                    # Punto de entrada Vite / React 19
├── types/                      # Contratos y tipos TypeScript (ActionDraft, ActionProposal, etc.)
├── services/                   # Cliente API REST y catálogo de mocks
│   ├── api.ts                  # Cliente fetch con timeout, sanitización y manejo de errores (ApiClientError)
│   └── mocks.ts                # Mocks de respaldo con citas literales del corpus para desarrollo aislado
└── components/                 # Componentes visuales especializados
    ├── ChatInterface.tsx       # Conversación interactiva, Markdown, feedback y tarjetas de acción
    ├── CitationCard.tsx        # Citas documentales desplegables (código, sección, versión, texto)
    ├── EvidenceBadge.tsx       # Insignias de estado de evidencia (Completa, Parcial, Abstención, Conflicto)
    ├── McpTracePanel.tsx       # Panel de auditoría de llamadas MCP (herramienta, argumentos, tiempo ms)
    ├── ActionConfirmationModal.tsx # Modal de confirmación en dos pasos con expiración automática de token
    └── SessionSelector.tsx     # Selector de usuario autenticado (U-I1 a U-I4) con asignación de roles
```

### Funcionalidades Destacadas:
1. **Evidencia Documental Abierta (PR-2):** Las respuestas con sustento normativo incluyen tarjetas de cita (`CitationCard`) que muestran documento, sección, versión y extracto fiel.
2. **Abstención y Conflicto Explícito (PR-3, PR-4):** Badges visuales inmediatos cuando el asistente carece de evidencia o detecta normas vigentes contradictorias.
3. **Trazabilidad MCP en Vivo (PR-5):** Panel lateral que registra cada llamada al servidor FastMCP con parámetros exactos, duración en milisegundos y resultado sanitizado.
4. **Confirmación Humana en Dos Pasos (PR-1, PR-6):** Las solicitudes de mutación generan un borrador informativo (`ActionDraft`). El operador revisa los detalles en el modal, ejecuta la preparación (recibiendo un token HMAC efímero con temporizador de 5 minutos) y confirma la mutación. Si el token expira o el estado de la tarea cambia concurrentemente, la confirmación se deshabilita automáticamente.
5. **Control de Sesión por Rol (PR-7):** Cambio inmediato entre ejecutivos (`U-I1`, `U-I2`), jefatura (`U-I3`) y área comercial (`U-I4`), validando permisos y organizaciones autorizadas.

---

## 2. Configuración de Variables de Entorno

Copiar el archivo de ejemplo a `.env`:
```bash
cp .env.example .env
```

| Variable | Valor Recomendado | Propósito |
|---|---|---|
| `VITE_API_URL` | `http://localhost:8000` | URL base del backend FastAPI (sin barra al final). |
| `VITE_USE_MOCKS` | `false` | `false` conecta con el backend real FastAPI + FastMCP + SQLite + RAG. `true` utiliza datos simulados en memoria para desarrollo o pruebas aisladas. |

---

## 3. Comandos de Desarrollo y Verificación

```bash
# 1. Instalar dependencias exactas
npm ci

# 2. Iniciar servidor de desarrollo local
npm run dev

# 3. Compilar para producción (TypeScript + Vite)
npm run build

# 4. Ejecutar la suite de pruebas unitarias y de integración (62 pruebas)
npm run test

# 5. Ejecutar análisis estático y linter de código (ESLint)
npm run lint
```
