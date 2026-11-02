# Frontend del Asistente MIRA CU-3

Este directorio contendrá la aplicación web en español para los usuarios del equipo de implementación de DPRIME (ejecutivos y jefatura).

> **Estado actual:** PREPARACIÓN DOCUMENTAL PREVIA A SPEC KIT.  
> El proyecto web, librerías y componentes UI se encuentran **pendientes** de inicialización formal.

---

## 1. Responsabilidades del Directorio

- **Interfaz de Chat Asistido:** Comunicación interactiva con el asistente para consultas sobre estado de incorporación, checklist y requisitos de plantillas.
- **Despliegue Visible de Evidencia:**
  - Componente de citas documentales con código de documento, sección, versión y extracto fiel.
  - Indicador visual claro de cuándo el asistente responde con evidencia documental.
  - Indicador explícito de **abstención** (cuando no hay información en el corpus).
  - Indicador de **conflicto entre fuentes vigentes**.
- **Trazabilidad MCP:** Panel o vista expandible que muestra las llamadas a herramientas MCP ejecutadas durante la consulta (argumentos, resultado retornado y tiempo).
- **Flujo de Confirmación Humana (Human-in-the-Loop):** Diálogo modal de confirmación obligatoria antes de ejecutar acciones de escritura (ej: marcar una tarea como completada).
- **Manejo de Errores y Caídas:** Mensajes claros y comprensibles ante indisponibilidad del modelo o servicios, sin alucinaciones ni inventos.

---

## 2. Tecnologías Planificadas

- **Framework:** React 18+ con TypeScript y Vite.
- **Estilos:** Vanilla CSS / CSS Modules enfocado en diseño limpio, accesible y responsivo.
- **Componentes:** Renderizado de Markdown con resaltado de citas e inspectores de trazas JSON.
- **Cliente HTTP:** Fetch API / Axios para consumir la API de FastAPI.

---

## 3. Próximos Pasos

1. Crear especificación de UI y experiencia de usuario en Spec Kit.
2. Inicializar proyecto Vite con React y TypeScript (`npm create vite@latest`).
3. Construir componentes base de conversación, visualizador de citas y modales de confirmación.
