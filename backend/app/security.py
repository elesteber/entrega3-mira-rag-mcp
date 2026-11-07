"""Módulo de seguridad, sesiones simuladas y control de acceso (PR-1, PR-6, PR-7).

Gestiona la identidad de demostración académica para los 4 usuarios reales de DPRIME
presentes en el kit CU-3, emitiendo sesiones firmadas con HMAC-SHA256 (JWT) y tokens efímeros
de confirmación de acción con control anti-replay mediante token_hash.

ARQUITECTURA DE SEGURIDAD Y CONTROL DE CONCURRENCIA:
- Simulación de identidad académica:
  Este módulo implementa una simulación de identidad para evaluación y demostración académica.
  No debe presentarse como un sistema de autenticación empresarial en producción (SAML/OIDC).
  Toda validación de permisos se realiza exclusivamente en el servidor (PR-7).
- Flujo de mutación seguro en 2 pasos (PR-1, PR-6):
  1. Preparación (/api/action/prepare): El servidor (no el LLM ni parámetros arbitrarios del cliente)
     obtiene la identidad verificada desde la sesión activa y consulta el estado efectivo actual
     directamente desde la base de datos (SQLite: v_tareas_estado_efectivo). Con esa información
     genera una propuesta y emite un token de confirmación criptográfico firmado (JWT efímero con TTL=5m).
  2. Confirmación (/api/action/confirm): El usuario confirma interactivamente en la UI.
     Al recibir la confirmación, se verifica criptográficamente el token y, dentro de una transacción
     atómica SQLite (BEGIN IMMEDIATE), se ejecutan los controles definitivos:
     a) Control Anti-Replay: Verificación de unicidad del hash SHA-256 (token_hash) en la tabla
        de auditoría (tarea_eventos_cambio). Si ya existe, se rechaza la mutación.
     b) Control de Concurrencia Optimista: Verificación de que el estado_actual registrado en el token
        coincida exactamente con el estado efectivo vigente en v_tareas_estado_efectivo. Si otro usuario
        o proceso modificó la tarea mientras se confirmaba, la transacción aborta con conflicto.
"""

from datetime import datetime, timedelta, timezone
import hashlib
import re
from typing import Any, Dict, List, Optional, Tuple
import uuid

from fastapi import Header, HTTPException, status
import jwt
from pydantic import BaseModel, Field

from backend.app.config import get_settings


# ==============================================================================
# Expresiones Regulares y Conjuntos de Validación de Dominio
# ==============================================================================

TAREA_ID_PATTERN = re.compile(r"^T-[0-9]{3}$")
ORG_ID_PATTERN = re.compile(r"^ORG-[0-9]{2}$")
VALID_TASK_STATES = frozenset({"pendiente", "en_curso", "completada"})
MANDATORY_CONFIRMATION_CLAIMS = frozenset(
    {"sub", "tarea_id", "org_id", "estado_actual", "nuevo_estado", "jti", "iat", "exp", "type"}
)
MANDATORY_SESSION_CLAIMS = frozenset({"sub", "iat", "exp", "type"})


# ==============================================================================
# Modelos de Dominio de Seguridad y Sesión
# ==============================================================================

class SimulatedUser(BaseModel):
    """Modelo de usuario simulado del personal de DPRIME según el kit CU-3."""

    usuario_id: str = Field(description="Identificador del usuario (U-I1 a U-I4)")
    nombre: str = Field(description="Nombre completo del funcionario")
    rol: str = Field(description="Rol: ejecutivo_implementacion, jefe_implementacion, comercial")
    orgs_asignadas: List[str] = Field(
        default_factory=list,
        description="Lista de códigos de organización asignadas para gestión operativa",
    )


class SessionTokenResponse(BaseModel):
    """Respuesta al conmutar o inicializar sesión de demostración."""

    session_token: str
    user: SimulatedUser
    expires_at: datetime


class SecurityError(Exception):
    """Excepción base para errores de seguridad del módulo."""

    def __init__(self, message: str, code: str = "SECURITY_ERROR", status_code: int = 401):
        super().__init__(message)
        self.message = message
        self.code = code
        self.status_code = status_code


class TokenExpiredError(SecurityError):
    """El token ha expirado."""

    def __init__(self, message: str = "El token de sesión ha expirado."):
        super().__init__(message, code="TOKEN_EXPIRED", status_code=401)


class InvalidTokenError(SecurityError):
    """El token es inválido o su firma es errónea."""

    def __init__(self, message: str = "Token inválido o firma digital no verificada."):
        super().__init__(message, code="INVALID_TOKEN", status_code=401)


class AccessForbiddenError(SecurityError):
    """El usuario no posee permisos para el recurso solicitado (PR-7)."""

    def __init__(self, message: str = "Acceso denegado según rol u organización asignada."):
        super().__init__(message, code="FORBIDDEN_ACCESS", status_code=403)


# ==============================================================================
# Catálogo de Usuarios Reales del Kit CU-3 (Inmutables)
# ==============================================================================

SIMULATED_USERS: Dict[str, SimulatedUser] = {
    "U-I1": SimulatedUser(
        usuario_id="U-I1",
        nombre="Sofía Tapia",
        rol="ejecutivo_implementacion",
        orgs_asignadas=["ORG-05", "ORG-07"],
    ),
    "U-I2": SimulatedUser(
        usuario_id="U-I2",
        nombre="Diego Fuentes",
        rol="ejecutivo_implementacion",
        orgs_asignadas=["ORG-06", "ORG-08"],
    ),
    "U-I3": SimulatedUser(
        usuario_id="U-I3",
        nombre="Carolina Vera",
        rol="jefe_implementacion",
        orgs_asignadas=["ORG-05", "ORG-06", "ORG-07", "ORG-08"],
    ),
    "U-I4": SimulatedUser(
        usuario_id="U-I4",
        nombre="Pablo Reyes",
        rol="comercial",
        orgs_asignadas=[],
    ),
}


# ==============================================================================
# Funciones de Gestión de Usuarios y Sesión Demo
# ==============================================================================

def get_simulated_user(usuario_id: str) -> Optional[SimulatedUser]:
    """Obtiene una copia profunda del usuario simulado a partir de su ID si existe.

    Garantiza la inmutabilidad del catálogo interno SIMULATED_USERS.
    """
    user = SIMULATED_USERS.get(usuario_id.strip().upper())
    return user.model_copy(deep=True) if user else None


def list_simulated_users() -> List[SimulatedUser]:
    """Retorna una lista de copias profundas de todos los usuarios de demostración.

    Garantiza que el catálogo interno SIMULATED_USERS no pueda ser mutado por consumidores.
    """
    return [u.model_copy(deep=True) for u in SIMULATED_USERS.values()]


def create_session_token(
    usuario_id: str, expires_delta: Optional[timedelta] = None
) -> Tuple[str, SimulatedUser, datetime]:
    """Emite un token de sesión firmado con HMAC-SHA256 para el usuario simulado.

    Args:
        usuario_id: Identificador de usuario ('U-I1', 'U-I2', 'U-I3', 'U-I4').
        expires_delta: Duración opcional de la sesión.

    Returns:
        Tupla con (token_jwt, objeto_usuario_copia, fecha_expiracion_utc).

    Raises:
        InvalidTokenError: Si el identificador de usuario no existe en el kit.
    """
    user = get_simulated_user(usuario_id)
    if not user:
        raise InvalidTokenError(f"El usuario simulado '{usuario_id}' no existe en el catálogo del kit.")

    settings = get_settings()
    now = datetime.now(timezone.utc)
    delta = expires_delta or timedelta(minutes=settings.SESSION_TTL_MINUTES)
    expires_at = now + delta

    payload = {
        "sub": user.usuario_id,
        "nombre": user.nombre,
        "rol": user.rol,
        "orgs_asignadas": list(user.orgs_asignadas),
        "iat": int(now.timestamp()),
        "exp": int(expires_at.timestamp()),
        "type": "demo_session",
    }

    token = jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)
    return token, user, expires_at


def verify_session_token(token: str) -> SimulatedUser:
    """Verifica la firma, algoritmo y validez de un token de sesión demo.

    Args:
        token: Cadena JWT de sesión.

    Returns:
        Copia profunda del objeto SimulatedUser verificado.

    Raises:
        TokenExpiredError: Si el token ya expiró.
        InvalidTokenError: Si la firma es inválida, el algoritmo no coincide o el formato es incorrecto.
    """
    settings = get_settings()
    try:
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
    except jwt.ExpiredSignatureError as e:
        raise TokenExpiredError("La sesión de demostración ha expirado.") from e
    except jwt.PyJWTError as e:
        raise InvalidTokenError(f"Token de sesión no válido: {str(e)}") from e

    # Validar claims obligatorios
    missing = [c for c in MANDATORY_SESSION_CLAIMS if c not in payload]
    if missing:
        raise InvalidTokenError(f"Token de sesión incompleto: faltan claims obligatorios: {sorted(missing)}.")

    if payload.get("type") != "demo_session":
        raise InvalidTokenError("El token provisto no corresponde a una sesión de demostración.")

    usuario_id = payload.get("sub")
    if not isinstance(usuario_id, str):
        raise InvalidTokenError("Claim 'sub' inválido en token de sesión.")

    user = get_simulated_user(usuario_id)
    if not user:
        raise InvalidTokenError(f"El usuario '{usuario_id}' codificado en la sesión no es válido.")

    return user


# ==============================================================================
# Tokens Efímeros de Confirmación de Acción (Flujo en 2 Pasos, PR-1 y PR-6)
# ==============================================================================

def create_confirmation_token(
    usuario_id: str,
    tarea_id: str,
    org_id: str,
    estado_actual: str,
    nuevo_estado: str,
    justificacion: Optional[str] = None,
    expires_delta: Optional[timedelta] = None,
) -> Tuple[str, str, datetime]:
    """Genera un token de confirmación criptográfico efímero y su hash anti-replay.

    NOTA DE ARQUITECTURA:
    El endpoint que invoca esta función (/api/action/prepare) debe obtener obligatoriamente
    la identidad del usuario desde la sesión verificada en el servidor y consultar el estado_actual
    directamente desde la base de datos (v_tareas_estado_efectivo), jamás a partir de datos no
    confiables aportados libremente por el modelo LLM o el cliente.

    Args:
        usuario_id: Usuario autenticado que preparó la acción.
        tarea_id: Código de la tarea ('T-001' a 'T-037').
        org_id: Código de la organización propietaria de la tarea.
        estado_actual: Estado efectivo antes del cambio (verificado en BD).
        nuevo_estado: Estado confirmado hacia el que transiciona.
        justificacion: Texto descriptivo de respaldo.
        expires_delta: TTL del token (por defecto CONFIRMATION_TOKEN_TTL_MINUTES = 5m).

    Returns:
        Tupla con (token_jwt, token_hash_sha256, fecha_expiracion_utc).
    """
    user = get_simulated_user(usuario_id)
    if not user:
        raise InvalidTokenError(f"Usuario '{usuario_id}' no reconocido en el catálogo del kit.")

    clean_tarea = tarea_id.strip().upper()
    if not TAREA_ID_PATTERN.match(clean_tarea):
        raise InvalidTokenError(f"Formato inválido de tarea_id: '{tarea_id}'. Se esperaba 'T-XXX'.")

    clean_org = org_id.strip().upper()
    if not ORG_ID_PATTERN.match(clean_org):
        raise InvalidTokenError(f"Formato inválido de org_id: '{org_id}'. Se esperaba 'ORG-XX'.")

    clean_estado_act = estado_actual.strip().lower()
    clean_nuevo_est = nuevo_estado.strip().lower()

    if clean_estado_act not in VALID_TASK_STATES:
        raise InvalidTokenError(
            f"estado_actual '{estado_actual}' no es válido. Permitidos: {sorted(VALID_TASK_STATES)}."
        )
    if clean_nuevo_est not in VALID_TASK_STATES:
        raise InvalidTokenError(
            f"nuevo_estado '{nuevo_estado}' no es válido. Permitidos: {sorted(VALID_TASK_STATES)}."
        )
    if clean_estado_act == clean_nuevo_est:
        raise InvalidTokenError("Transición inválida: estado_actual y nuevo_estado no pueden ser idénticos.")

    settings = get_settings()
    now = datetime.now(timezone.utc)
    delta = expires_delta or timedelta(minutes=settings.CONFIRMATION_TOKEN_TTL_MINUTES)
    expires_at = now + delta

    payload = {
        "sub": user.usuario_id,
        "rol": user.rol,
        "tarea_id": clean_tarea,
        "org_id": clean_org,
        "estado_actual": clean_estado_act,
        "nuevo_estado": clean_nuevo_est,
        "justificacion": justificacion.strip() if justificacion else None,
        "jti": str(uuid.uuid4()),
        "iat": int(now.timestamp()),
        "exp": int(expires_at.timestamp()),
        "type": "action_confirmation",
    }

    token = jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)
    token_hash = compute_token_hash(token)
    return token, token_hash, expires_at


def compute_token_hash(token: str) -> str:
    """Calcula el hash SHA-256 de un token para almacenamiento auditable anti-replay."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def verify_confirmation_token(token: str) -> Dict[str, Any]:
    """Verifica la firma, vigencia temporal y coherencia de claims de un token de confirmación.

    NOTA DE ARQUITECTURA (PR-1, PR-6):
    Esta función verifica la validez criptográfica y consistencia de los datos del token.
    El control definitivo de anti-replay (comprobando que el hash SHA-256 no haya sido utilizado
    previamente) y el control de concurrencia optimista (verificando que el estado_actual del token
    coincida exactamente con el estado registrado en v_tareas_estado_efectivo en ese instante)
    se ejecutan dentro de la transacción atómica SQLite (BEGIN IMMEDIATE) en el endpoint /api/action/confirm.

    Args:
        token: Cadena JWT de confirmación.

    Returns:
        Diccionario con los claims decodificados y validados.

    Raises:
        TokenExpiredError: Si transcurrió la ventana de vigencia (máx. 5 minutos).
        InvalidTokenError: Si el token está alterado, incompleto, tiene algoritmo incorrecto
                           o sus valores son inconsistentes.
    """
    settings = get_settings()
    try:
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
    except jwt.ExpiredSignatureError as e:
        raise TokenExpiredError("El token de confirmación ha expirado (límite: 5 minutos).") from e
    except jwt.PyJWTError as e:
        raise InvalidTokenError(f"Token de confirmación inválido o alterado: {str(e)}") from e

    # 1. Validar presencia de claims obligatorios
    missing_claims = [c for c in MANDATORY_CONFIRMATION_CLAIMS if c not in payload]
    if missing_claims:
        raise InvalidTokenError(
            f"Token de confirmación incompleto: faltan claims obligatorios: {sorted(missing_claims)}."
        )

    # 2. Validar tipo de token
    if payload.get("type") != "action_confirmation":
        raise InvalidTokenError("El token no corresponde a una propuesta de confirmación de acción.")

    # 3. Validar sujeto (usuario simulado existente)
    sub = payload.get("sub")
    if not isinstance(sub, str) or not get_simulated_user(sub):
        raise InvalidTokenError(f"El usuario '{sub}' codificado en el token no existe en el catálogo.")

    # 4. Validar formato de tarea_id y org_id
    tarea_id = payload.get("tarea_id")
    if not isinstance(tarea_id, str) or not TAREA_ID_PATTERN.match(tarea_id.strip()):
        raise InvalidTokenError(f"Identificador de tarea inválido en token: '{tarea_id}'. Formato esperado: 'T-XXX'.")

    org_id = payload.get("org_id")
    if not isinstance(org_id, str) or not ORG_ID_PATTERN.match(org_id.strip()):
        raise InvalidTokenError(f"Identificador de organización inválido en token: '{org_id}'. Formato esperado: 'ORG-XX'.")

    # 5. Validar coherencia de estados de tarea
    estado_actual = payload.get("estado_actual")
    if estado_actual not in VALID_TASK_STATES:
        raise InvalidTokenError(
            f"estado_actual '{estado_actual}' inválido en token. Permitidos: {sorted(VALID_TASK_STATES)}."
        )

    nuevo_estado = payload.get("nuevo_estado")
    if nuevo_estado not in VALID_TASK_STATES:
        raise InvalidTokenError(
            f"nuevo_estado '{nuevo_estado}' inválido en token. Permitidos: {sorted(VALID_TASK_STATES)}."
        )

    if estado_actual == nuevo_estado:
        raise InvalidTokenError("Transición inválida: estado_actual y nuevo_estado no pueden ser idénticos.")

    # 6. Validar identificador único de token (jti)
    jti = payload.get("jti")
    if not isinstance(jti, str) or not jti.strip():
        raise InvalidTokenError("Claim 'jti' inválido o vacío en token de confirmación.")

    # 7. Validar consistencia de marcas temporales
    iat = payload.get("iat")
    exp = payload.get("exp")
    if not isinstance(iat, (int, float)) or not isinstance(exp, (int, float)) or exp <= iat:
        raise InvalidTokenError("Claims temporales (iat, exp) inválidos o inconsistentes en token.")

    return payload


# ==============================================================================
# Reglas de Validación de Permisos y Control de Acceso por Rol (PR-7)
# ==============================================================================

def check_user_organization_access(user: SimulatedUser, org_id: str) -> bool:
    """Valida si el usuario en sesión tiene autorización para acceder a una organización.

    Reglas de negocio:
    - Rol comercial (U-I4): Acceso denegado a todas las organizaciones operativas.
    - Rol jefe_implementacion (U-I3): Supervisión global sobre todas las organizaciones.
    - Rol ejecutivo_implementacion (U-I1, U-I2): Únicamente las organizaciones asignadas.
    """
    clean_org = org_id.strip().upper()
    if user.rol == "comercial":
        return False
    if user.rol == "jefe_implementacion":
        return True
    return clean_org in user.orgs_asignadas


def check_user_task_mutation_permission(
    user: SimulatedUser, org_id: str, etapa: str
) -> Tuple[bool, Optional[str]]:
    """Valida si el usuario tiene autorización para mutar una tarea específica.

    Reglas de negocio:
    1. El rol comercial jamás puede mutar tareas.
    2. El usuario debe tener asignada la organización de la tarea.
    3. La tarea de salida a producción (etapa E5) solo puede ser autorizada por jefatura.

    Returns:
        Tupla con (es_autorizado, mensaje_error_si_aplica).
    """
    clean_org = org_id.strip().upper()
    clean_etapa = etapa.strip().upper()

    if user.rol == "comercial":
        return False, "El rol comercial no posee facultades operativas para modificar tareas."

    if not check_user_organization_access(user, clean_org):
        return (
            False,
            f"El usuario {user.usuario_id} ({user.nombre}) no tiene permisos sobre la organización {clean_org}.",
        )

    if clean_etapa == "E5" and user.rol != "jefe_implementacion":
        return (
            False,
            "La salida a producción (etapa E5) exige autorización exclusiva de la jefatura de implementación (GUI-INC v2 §4).",
        )

    return True, None


# ==============================================================================
# Dependencias de Inyección para Endpoints FastAPI
# ==============================================================================

def get_current_user_from_header(
    authorization: Optional[str] = Header(None, alias="Authorization"),
    x_mira_demo_session: Optional[str] = Header(None, alias="X-MIRA-Demo-Session"),
) -> SimulatedUser:
    """Dependencia de FastAPI que extrae y valida la sesión demo de los encabezados.

    Admite:
    1. 'Authorization: Bearer <session_token>'
    2. 'X-MIRA-Demo-Session: <session_token>'

    Reglas de consistencia (PR-7):
    - Si se proveen ambos encabezados y contienen tokens diferentes, se rechaza
      la petición con HTTP 400 (AMBIGUOUS_SESSION_HEADERS) para evitar desincronización
      o ambigüedad entre el frontend y llamadas directas.
    - Si el encabezado Authorization no utiliza el esquema 'Bearer', se rechaza con HTTP 401.
    - Si no se provee ningún token, se rechaza con HTTP 401 (MISSING_SESSION_TOKEN).

    Raises:
        HTTPException(400): Si se detectan encabezados de sesión contradictorios.
        HTTPException(401): Si falta el token, el esquema es incorrecto o la firma es inválida.
    """
    auth_token: Optional[str] = None
    if isinstance(authorization, str) and authorization.strip():
        parts = authorization.strip().split(" ", 1)
        if len(parts) == 2 and parts[0].lower() == "bearer":
            auth_token = parts[1].strip()
        else:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={
                    "code": "INVALID_AUTHORIZATION_SCHEME",
                    "message": "Esquema de autenticación inválido. Formato requerido: 'Bearer <token>'.",
                    "principle_violated": "PR-7",
                },
            )

    demo_token: Optional[str] = None
    if isinstance(x_mira_demo_session, str) and x_mira_demo_session.strip():
        demo_token = x_mira_demo_session.strip()

    if auth_token and demo_token:
        if auth_token != demo_token:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "code": "AMBIGUOUS_SESSION_HEADERS",
                    "message": (
                        "Se han provisto encabezados de sesión contradictorios "
                        "(Authorization y X-MIRA-Demo-Session contienen tokens diferentes)."
                    ),
                    "principle_violated": "PR-7",
                },
            )
        token = auth_token
    elif auth_token:
        token = auth_token
    elif demo_token:
        token = demo_token
    else:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "code": "MISSING_SESSION_TOKEN",
                "message": (
                    "No se ha provisto una sesión de demostración válida. "
                    "Seleccione un usuario activo en el selector superior."
                ),
                "principle_violated": "PR-7",
            },
        )

    try:
        return verify_session_token(token)
    except SecurityError as e:
        raise HTTPException(
            status_code=e.status_code,
            detail={
                "code": e.code,
                "message": e.message,
                "principle_violated": "PR-7",
            },
        ) from e
