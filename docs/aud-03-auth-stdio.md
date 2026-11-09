# AUD-03: especificación, plan y contrato de delegación MCP

Estado: diseño para la corrección en `fix/pr7-auth-stdio`, sobre PR #7.
Complementa FR-017 y PR-7 de la especificación Spec Kit existente.

## Especificación

La identidad efectiva procede únicamente de una credencial de delegación verificada
por solicitud `tools/call`. `usuario_id` opcional solo comprueba coincidencia.
Una mutación requiere además el token de confirmación humana y conserva RBAC,
E5, transacción y anti-replay. Las funciones unitarias mantienen su contexto directo.
El servidor ignora cualquier contexto heredado al entrar a una invocación MCP.

## Plan

1. Verificar la API instalada de FastMCP 4.1.6: `Middleware.on_call_tool`,
   `context.fastmcp_context.request_context.meta` y `Client.call_tool(meta=...)`.
2. Validar JWT HS256 y crear/restablecer un ContextVar dentro de `try/finally`.
3. Corregir la resolución de identidad de consultas sin cambiar firmas de negocio.
4. Ejecutar regresiones reales por stdio con SQLite temporal y la suite original.

## Contrato de integración

Campo metadata MCP `_meta["mira_delegation"]`: cadena JWT compacta, sin prefijo Bearer.
Encabezado `alg=HS256`, `typ=mira-mcp-delegation+jwt`.
Claims obligatorios: `sub` (usuario existente en SQLite), `iss=mira-api`,
`aud=mira-cu3-mcp`, `token_type=mcp_delegation`, `iat` y `exp` enteros NumericDate,
`jti` cadena no vacía. Vigencia máxima: 300 segundos. Sin roles ni permisos del cliente:
se resuelven desde SQLite. No se vincula a una organización en el JWT; RBAC valida
cada organización solicitada contra la asignación vigente.

Variable `MIRA_MCP_DELEGATION_SECRET`: secreto independiente de `JWT_SECRET`,
al menos 32 bytes UTF-8, sin valor predeterminado; ausencia, debilidad o igualdad con
la clave de confirmación se rechazan. También se rechaza explícitamente
`DEFAULT_JWT_SECRET`, aunque `JWT_SECRET` tenga otro valor seguro.
Configuración declarada en `backend/mcp/.env.example`.
`SQLITE_DB_PATH` selecciona SQLite. `JWT_SECRET` sigue siendo la clave del mecanismo
existente de confirmación humana; para `marcar_tarea` por transporte es obligatorio,
de al menos 32 bytes y distinto del valor histórico de demostración. Ese valor
histórico permanece para compatibilidad de pruebas directas, pero no autoriza
mutaciones por transporte. La delegación no reemplaza la confirmación.

El futuro `MiraMcpClient` debe obtener `sub` exclusivamente de la sesión FastAPI
verificada, emitir una delegación corta con el secreto compartido y enviar:
`await client.call_tool(nombre, argumentos, meta={"mira_delegation": credencial})`.
Debe construir metadata fuera del LLM, sin aceptar metadata del modelo y sin incluirla
en respuestas, logs ni trazas. No registrar cuerpos MCP completos ni usar middleware
de logging que capture metadata. La credencial es de portador y requiere protección
del proceso y del canal local; `jti` identifica la delegación, no sustituye el anti-replay
del token de confirmación de mutaciones.

La integración FastAPI–MCP del PR #17 queda **pendiente**: esta rama no contiene
ese cliente. El cliente histórico de pruebas invoca funciones directamente y no
constituye evidencia de autenticación por transporte.

## Evidencia de pruebas

`tests/clients/test_external_mcp_client.py` llama funciones directamente y prepara
el contexto con `set_current_user_id`; comprueba comportamiento de negocio, sin
atravesar el transporte ni autenticar una solicitud MCP.

Las pruebas de `tests/integration/test_auth_stdio.py` que usan `cliente(env)`
inician el servidor en un proceso independiente mediante `StdioTransport`, envían
metadata MCP real y usan SQLite temporal. Incluyen el rechazo de una delegación
firmada con `DEFAULT_JWT_SECRET` cuando la clave de confirmación es otra clave segura.
La prueba `test_contexto_directo_no_autentica_servidor_y_se_restaura` usa
`Client(mcp)` en memoria para comprobar el aislamiento del contexto heredado;
esa prueba no usa stdio.

Estas pruebas no completan la integración con `MiraMcpClient` del PR #17,
que continúa **pendiente**.
