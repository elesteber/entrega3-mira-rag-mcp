"""
Pruebas unitarias de mutación atómica, inmutabilidad de tablas base,
concurrencia optimista y control anti-replay (US4, T034, T036, PR-1, PR-6, PR-7).
Endurecimiento de validación de tokens firmados y control estricto de identidad.
"""

from __future__ import annotations

import datetime
import os
import jwt
import pytest

from backend.data.db import create_connection
from backend.data.init_db import init_database
from backend.mcp.access_control import McpSecurityError, set_current_user_id
from backend.mcp.tools.mutation_tools import DEFAULT_JWT_SECRET, marcar_tarea
from backend.mcp.tools.sql_tools import checklist_organizacion


@pytest.fixture(autouse=True)
def setup_db(tmp_path):
    """Inicializa una base de datos limpia para cada prueba unitaria."""
    test_db = tmp_path / "test_mira_mutation.db"
    init_database(db_path=test_db, quiet=True)
    os.environ["SQLITE_DB_PATH"] = str(test_db)
    yield
    set_current_user_id(None)


def _generate_test_token(
    tarea_id: str,
    org_id: str,
    nuevo_estado: str,
    usuario_id: str,
    estado_anterior: str = "en_curso",
    expired: bool = False,
    secret: str = DEFAULT_JWT_SECRET,
    algorithm: str = "HS256",
    omit_claims: list[str] | None = None,
) -> str:
    """Helper para generar tokens efímeros firmados con HMAC-SHA256 >= 32 bytes."""
    now = datetime.datetime.now(datetime.timezone.utc)
    exp = now - datetime.timedelta(minutes=1) if expired else now + datetime.timedelta(minutes=5)
    payload = {
        "action_type": "CAMBIO_ESTADO_TAREA",
        "tarea_id": tarea_id,
        "org_id": org_id,
        "estado_anterior": estado_anterior,
        "nuevo_estado": nuevo_estado,
        "usuario_id": usuario_id,
        "exp": int(exp.timestamp()),
        "jti": f"test-jti-{os.urandom(8).hex()}",
    }
    if omit_claims:
        for c in omit_claims:
            payload.pop(c, None)

    if algorithm == "none":
        return jwt.encode(payload, key="", algorithm="none")
    return jwt.encode(payload, secret, algorithm=algorithm)


# =========================================================================
# Escenario exacto reportado en el PR #7 (Vulnerabilidad contenida)
# =========================================================================

def test_escenario_reportado_token_falso_sin_sesion_es_rechazado():
    """
    Reproduce exactamente el caso vulnerable reportado:
    - set_current_user_id(None)
    - marcar_tarea(tarea_id='T-006', nuevo_estado='completada', token_confirmacion='token-falso-no-firmado', usuario_id='U-I1')
    Asserts:
    1. La operación es rechazada con McpSecurityError.
    2. La tarea permanece en su estado original ('en_curso') en SQLite.
    3. No se inserta ningún registro en tarea_eventos_cambio.
    """
    set_current_user_id(None)

    with pytest.raises(McpSecurityError) as exc_info:
        marcar_tarea(
            tarea_id="T-006",
            nuevo_estado="completada",
            token_confirmacion="token-falso-no-firmado",
            usuario_id="U-I1",
        )
    # Debe ser rechazada por falta de sesión o token inválido
    assert exc_info.value.code in ("UNAUTHENTICATED_SESSION", "INVALID_CONFIRMATION_TOKEN")

    conn = create_connection()
    c = conn.cursor()
    # Tarea no modificada
    c.execute("SELECT estado FROM tareas WHERE tarea_id = 'T-006'")
    assert c.fetchone()["estado"] == "en_curso"
    c.execute("SELECT estado FROM v_tareas_estado_efectivo WHERE tarea_id = 'T-006'")
    assert c.fetchone()["estado"] == "en_curso"

    # Ningún evento insertado
    c.execute("SELECT COUNT(*) FROM tarea_eventos_cambio")
    assert c.fetchone()[0] == 0
    conn.close()


# =========================================================================
# Pruebas obligatorias de validación criptográfica del token (Fail-Closed)
# =========================================================================

def test_token_alterado_o_firma_invalida_es_rechazado():
    """
    Un token firmado con una clave distinta o con el payload alterado debe rechazarse
    sin modificar la base de datos ni registrar eventos.
    """
    set_current_user_id("U-I1")
    # Firmado con clave ajena
    fake_secret = "clave_ajena_falsa_completamente_invalida_32b"
    tampered_token = _generate_test_token("T-006", "ORG-05", "completada", "U-I1", secret=fake_secret)

    with pytest.raises(McpSecurityError) as exc_info:
        marcar_tarea(
            tarea_id="T-006",
            nuevo_estado="completada",
            token_confirmacion=tampered_token,
        )
    assert exc_info.value.code == "INVALID_CONFIRMATION_TOKEN"

    conn = create_connection()
    assert conn.execute("SELECT COUNT(*) FROM tarea_eventos_cambio").fetchone()[0] == 0
    conn.close()


def test_token_algoritmo_none_es_rechazado():
    """
    Un token que intente usar el algoritmo 'none' para omitir la firma debe rechazarse de inmediato.
    """
    set_current_user_id("U-I1")
    none_token = _generate_test_token("T-006", "ORG-05", "completada", "U-I1", algorithm="none")

    with pytest.raises(McpSecurityError) as exc_info:
        marcar_tarea(
            tarea_id="T-006",
            nuevo_estado="completada",
            token_confirmacion=none_token,
        )
    assert exc_info.value.code in ("INVALID_TOKEN_ALGORITHM", "INVALID_CONFIRMATION_TOKEN")

    conn = create_connection()
    assert conn.execute("SELECT COUNT(*) FROM tarea_eventos_cambio").fetchone()[0] == 0
    conn.close()


def test_token_claims_faltantes_es_rechazado():
    """
    Rechaza tokens si falta cualquiera de los claims obligatorios:
    tarea_id, org_id, usuario_id, estado_anterior o nuevo_estado.
    """
    set_current_user_id("U-I1")

    for missing in ["tarea_id", "org_id", "usuario_id", "estado_anterior", "nuevo_estado"]:
        incomplete_token = _generate_test_token(
            "T-006", "ORG-05", "completada", "U-I1", omit_claims=[missing]
        )
        with pytest.raises(McpSecurityError) as exc_info:
            marcar_tarea(
                tarea_id="T-006",
                nuevo_estado="completada",
                token_confirmacion=incomplete_token,
            )
        assert exc_info.value.code == "MISSING_TOKEN_CLAIMS"

    conn = create_connection()
    assert conn.execute("SELECT COUNT(*) FROM tarea_eventos_cambio").fetchone()[0] == 0
    conn.close()


# =========================================================================
# Pruebas obligatorias de identidad efectiva (PR-7) y assertions
# =========================================================================

def test_sin_sesion_autenticada_con_token_valido_es_rechazado():
    """
    Aunque se provea un token criptográficamente válido, si no existe sesión
    autenticada en el servidor (current_user_id is None), la operación se rechaza.
    """
    set_current_user_id(None)
    valid_token = _generate_test_token("T-006", "ORG-05", "completada", "U-I1")

    with pytest.raises(McpSecurityError) as exc_info:
        marcar_tarea(
            tarea_id="T-006",
            nuevo_estado="completada",
            token_confirmacion=valid_token,
        )
    assert exc_info.value.code == "UNAUTHENTICATED_SESSION"


def test_argumento_usuario_id_discrepante_de_sesion_es_rechazado():
    """
    El argumento usuario_id actúa como assertion: si discrepa de la identidad efectiva
    de la sesión confiable, la operación es rechazada de inmediato.
    """
    set_current_user_id("U-I1")
    token = _generate_test_token("T-006", "ORG-05", "completada", "U-I1")

    with pytest.raises(McpSecurityError) as exc_info:
        marcar_tarea(
            tarea_id="T-006",
            nuevo_estado="completada",
            token_confirmacion=token,
            usuario_id="U-I2",  # Discrepa de la sesión activa U-I1
        )
    assert exc_info.value.code == "USER_IDENTITY_MISMATCH"


def test_token_emitido_para_otro_usuario_es_rechazado():
    """
    Si el token firmado contiene un claim usuario_id que no corresponde a la sesión activa,
    se rechaza por violación de identidad (PR-7).
    """
    set_current_user_id("U-I1")
    # Token emitido para U-I2
    token_ui2 = _generate_test_token("T-006", "ORG-05", "completada", "U-I2")

    with pytest.raises(McpSecurityError) as exc_info:
        marcar_tarea(
            tarea_id="T-006",
            nuevo_estado="completada",
            token_confirmacion=token_ui2,
        )
    assert exc_info.value.code == "TOKEN_USER_MISMATCH"


# =========================================================================
# Revalidación transaccional dentro de BEGIN IMMEDIATE (PR-6 / Concurrencia)
# =========================================================================

def test_estado_efectivo_distinto_a_estado_anterior_del_token_es_rechazado():
    """
    Si dentro de BEGIN IMMEDIATE el estado actual de la tarea en SQLite no coincide
    con el estado_anterior certificado en el token, se aborta por conflicto de concurrencia.
    """
    set_current_user_id("U-I1")
    # T-006 está actualmente en 'en_curso'. El token afirma que estaba 'pendiente'.
    conflict_token = _generate_test_token(
        "T-006", "ORG-05", "completada", "U-I1", estado_anterior="pendiente"
    )

    with pytest.raises(McpSecurityError) as exc_info:
        marcar_tarea(
            tarea_id="T-006",
            nuevo_estado="completada",
            token_confirmacion=conflict_token,
        )
    assert exc_info.value.code == "OPTIMISTIC_CONCURRENCY_CONFLICT"

    conn = create_connection()
    assert conn.execute("SELECT COUNT(*) FROM tarea_eventos_cambio").fetchone()[0] == 0
    conn.close()


def test_token_organizacion_mismatch():
    """
    Si el token indica una organización distinta a la de la tarea en SQLite, se rechaza.
    """
    set_current_user_id("U-I1")
    mismatch_org_token = _generate_test_token(
        "T-006", "ORG-07", "completada", "U-I1", estado_anterior="en_curso"
    )

    with pytest.raises(McpSecurityError) as exc_info:
        marcar_tarea(
            tarea_id="T-006",
            nuevo_estado="completada",
            token_confirmacion=mismatch_org_token,
        )
    assert exc_info.value.code == "TOKEN_ORG_MISMATCH"


# =========================================================================
# Pruebas existentes preservadas (Mutación exitosa, anti-replay, expiración)
# =========================================================================

def test_mutacion_exitosa_conserva_tabla_base_y_actualiza_estado_efectivo():
    """
    US4 / T034 / D5: U-I1 marca T-006 como completada.
    - La tabla base 'tareas' conserva su estado original ('en_curso') inmutable (PR-1, PR-6).
    - Se registra el evento en 'tarea_eventos_cambio'.
    - La vista 'v_tareas_estado_efectivo' refleja 'completada'.
    """
    set_current_user_id("U-I1")
    token = _generate_test_token("T-006", "ORG-05", "completada", "U-I1", estado_anterior="en_curso")

    res = marcar_tarea(
        tarea_id="T-006",
        nuevo_estado="completada",
        token_confirmacion=token,
        justificacion="Se habilitó carpeta SFTP y se validó recepción de archivos.",
    )

    assert res["success"] is True
    assert res["tarea_id"] == "T-006"
    assert res["org_id"] == "ORG-05"
    assert res["nuevo_estado"] == "completada"
    assert res["evento_id"] == 1

    # Verificación 1: En la tabla base 'tareas', el registro permanece en 'en_curso'
    conn = create_connection()
    c = conn.cursor()
    c.execute("SELECT estado, observacion FROM tareas WHERE tarea_id = 'T-006'")
    base_row = c.fetchone()
    assert base_row["estado"] == "en_curso"  # INMUTABILIDAD DEL KIT CONFIRMADA

    # Verificación 2: Evento registrado en tarea_eventos_cambio con hash
    c.execute("SELECT * FROM tarea_eventos_cambio WHERE evento_id = 1")
    event_row = c.fetchone()
    assert event_row["tarea_id"] == "T-006"
    assert event_row["org_id"] == "ORG-05"
    assert event_row["estado_anterior"] == "en_curso"
    assert event_row["nuevo_estado"] == "completada"
    assert event_row["usuario_id"] == "U-I1"
    assert event_row["rol_usuario"] == "ejecutivo_implementacion"
    assert len(event_row["token_hash"]) == 64  # SHA-256 hex
    conn.close()

    # Verificación 3: Vista v_tareas_estado_efectivo muestra estado 'completada'
    checklist = checklist_organizacion("ORG-05")
    t006 = next(t for t in checklist["tareas"] if t["tarea_id"] == "T-006")
    assert t006["estado"] == "completada"
    assert t006["actualizado_por"] == "U-I1"
    assert t006["fecha_ultima_actualizacion"] is not None

    # Verificación 4: Avance de la organización subió a 70.0% (7 de 10)
    assert checklist["resumen_progreso"]["completadas"] == 7
    assert checklist["resumen_progreso"]["en_curso"] == 0
    assert checklist["resumen_progreso"]["porcentaje_avance"] == 70.0


def test_anti_replay_rechaza_reutilizacion_de_token():
    """
    US4 / T034: Reutilizar un token previamente consumido es rechazado por el hash anti-replay.
    """
    set_current_user_id("U-I1")
    token = _generate_test_token("T-006", "ORG-05", "completada", "U-I1", estado_anterior="en_curso")

    # Primera ejecución exitosa
    marcar_tarea(
        tarea_id="T-006",
        nuevo_estado="completada",
        token_confirmacion=token,
    )

    # Segundo intento con el MISMO token exacto
    with pytest.raises(McpSecurityError) as exc_info:
        marcar_tarea(
            tarea_id="T-006",
            nuevo_estado="completada",
            token_confirmacion=token,
        )
    assert exc_info.value.code == "TOKEN_ALREADY_USED"


def test_token_expirado_es_rechazado():
    """
    US4 / T034: Un token con exp vencido es rechazado antes de tocar la base de datos.
    """
    set_current_user_id("U-I1")
    expired_token = _generate_test_token("T-006", "ORG-05", "completada", "U-I1", estado_anterior="en_curso", expired=True)

    with pytest.raises(McpSecurityError) as exc_info:
        marcar_tarea(
            tarea_id="T-006",
            nuevo_estado="completada",
            token_confirmacion=expired_token,
        )
    assert exc_info.value.code == "TOKEN_EXPIRED"


def test_token_mismatch_tarea_id():
    """
    US4: Un token emitido para T-006 no puede utilizarse sobre T-007.
    """
    set_current_user_id("U-I1")
    token = _generate_test_token("T-006", "ORG-05", "completada", "U-I1", estado_anterior="en_curso")

    with pytest.raises(McpSecurityError) as exc_info:
        marcar_tarea(
            tarea_id="T-007",
            nuevo_estado="completada",
            token_confirmacion=token,
        )
    assert exc_info.value.code == "TOKEN_TASK_MISMATCH"


def test_token_mismatch_nuevo_estado():
    """
    Un token emitido para nuevo_estado='completada' no puede usarse para 'pendiente'.
    """
    set_current_user_id("U-I1")
    token = _generate_test_token("T-006", "ORG-05", "completada", "U-I1", estado_anterior="en_curso")

    with pytest.raises(McpSecurityError) as exc_info:
        marcar_tarea(
            tarea_id="T-006",
            nuevo_estado="pendiente",
            token_confirmacion=token,
        )
    assert exc_info.value.code == "TOKEN_STATE_MISMATCH"


def test_concurrencia_optimista_rechaza_transicion_redundante():
    """
    US4: Si una tarea ya se encuentra en el nuevo estado, la mutación se rechaza.
    """
    set_current_user_id("U-I1")
    # T-001 ya está completada en el kit
    token = _generate_test_token("T-001", "ORG-05", "completada", "U-I1", estado_anterior="completada")

    with pytest.raises(McpSecurityError) as exc_info:
        marcar_tarea(
            tarea_id="T-001",
            nuevo_estado="completada",
            token_confirmacion=token,
        )
    assert exc_info.value.code == "INVALID_STATE_TRANSITION"
