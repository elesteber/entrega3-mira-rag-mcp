"""
Pruebas unitarias de mutación atómica, inmutabilidad de tablas base,
concurrencia optimista y control anti-replay (US4, T034, T036, PR-1, PR-6).
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


def _generate_test_token(tarea_id: str, org_id: str, nuevo_estado: str, usuario_id: str, expired: bool = False) -> str:
    """Helper para generar tokens efímeros firmados con HMAC-SHA256."""
    now = datetime.datetime.now(datetime.timezone.utc)
    exp = now - datetime.timedelta(minutes=1) if expired else now + datetime.timedelta(minutes=5)
    payload = {
        "action_type": "CAMBIO_ESTADO_TAREA",
        "tarea_id": tarea_id,
        "org_id": org_id,
        "nuevo_estado": nuevo_estado,
        "usuario_id": usuario_id,
        "exp": int(exp.timestamp()),
        "jti": f"test-jti-{os.urandom(8).hex()}",
    }
    return jwt.encode(payload, DEFAULT_JWT_SECRET, algorithm="HS256")


def test_mutacion_exitosa_conserva_tabla_base_y_actualiza_estado_efectivo():
    """
    US4 / T034 / D5: U-I1 marca T-006 como completada.
    - La tabla base 'tareas' conserva su estado original ('en_curso') inmutable (PR-1, PR-6).
    - Se registra el evento en 'tarea_eventos_cambio'.
    - La vista 'v_tareas_estado_efectivo' refleja 'completada'.
    """
    set_current_user_id("U-I1")
    token = _generate_test_token("T-006", "ORG-05", "completada", "U-I1")

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
    token = _generate_test_token("T-006", "ORG-05", "completada", "U-I1")

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
    expired_token = _generate_test_token("T-006", "ORG-05", "completada", "U-I1", expired=True)

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
    token = _generate_test_token("T-006", "ORG-05", "completada", "U-I1")

    with pytest.raises(McpSecurityError) as exc_info:
        marcar_tarea(
            tarea_id="T-007",
            nuevo_estado="completada",
            token_confirmacion=token,
        )
    assert exc_info.value.code == "TOKEN_TASK_MISMATCH"


def test_concurrencia_optimista_rechaza_transicion_redundante():
    """
    US4: Si una tarea ya se encuentra en el nuevo estado, la mutación se rechaza.
    """
    set_current_user_id("U-I1")
    # T-001 ya está completada en el kit
    token = _generate_test_token("T-001", "ORG-05", "completada", "U-I1")

    with pytest.raises(McpSecurityError) as exc_info:
        marcar_tarea(
            tarea_id="T-001",
            nuevo_estado="completada",
            token_confirmacion=token,
        )
    assert exc_info.value.code == "INVALID_STATE_TRANSITION"

