"""
Script CLI y módulo de inicialización/hidratación de la base de datos relacional SQLite
a partir del archivo oficial CU-3_datos.xlsx en modo sólo lectura (PR-1, PR-5, PR-6).
MIRA CU-3 - Asistente de Incorporación de Organizaciones.
"""

from __future__ import annotations

import argparse
import datetime
import os
from pathlib import Path
from typing import Any

import openpyxl

from backend.data.db import create_connection, get_db_path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DEFAULT_EXCEL_PATH = (
    PROJECT_ROOT
    / "archivos-base"
    / "Kit_Entrega_3_MIRA"
    / "CU-3_incorporacion_organizaciones"
    / "datos"
    / "CU-3_datos.xlsx"
)


def get_excel_path() -> Path:
    """
    Retorna la ruta absoluta al archivo Excel del kit oficial resolviendo desde
    la variable de entorno EXCEL_DATA_PATH o la ruta predeterminada.
    """
    env_path = os.getenv("EXCEL_DATA_PATH")
    if env_path:
        p = Path(env_path)
        if not p.is_absolute():
            p = PROJECT_ROOT / p
        return p
    return DEFAULT_EXCEL_PATH


def _format_cell_value(val: Any) -> Any:
    """Normaliza valores de celdas de Excel a tipos de SQLite."""
    if val is None:
        return None
    if isinstance(val, (datetime.datetime, datetime.date)):
        return val.strftime("%Y-%m-%d")
    if isinstance(val, str):
        val_strip = val.strip()
        return val_strip if val_strip else None
    return val


def create_schema(conn, reset_events: bool = False) -> None:
    """
    Crea las tablas relacionales base, la tabla de eventos de mutación y la vista de estado efectivo.
    """
    cursor = conn.cursor()

    # Desactivar temporalmente foreign keys durante reconstrucción de esquema
    cursor.execute("PRAGMA foreign_keys = OFF;")

    # 1. Tablas base del kit
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS usuarios (
        usuario_id TEXT PRIMARY KEY,
        nombre TEXT NOT NULL,
        rol TEXT NOT NULL CHECK (rol IN ('ejecutivo_implementacion', 'jefe_implementacion', 'comercial'))
    );
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS plantillas (
        plantilla_id TEXT PRIMARY KEY,
        nombre TEXT NOT NULL,
        industria TEXT NOT NULL,
        modulos TEXT NOT NULL,
        umbral_aprobacion_sugerido INTEGER NOT NULL,
        umbral_revision_sugerido INTEGER NOT NULL,
        dias_adaptacion_estimados INTEGER NOT NULL,
        requiere_autorizacion_biometrica TEXT CHECK (requiere_autorizacion_biometrica IN ('sí', 'no'))
    );
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS organizaciones (
        org_id TEXT PRIMARY KEY,
        nombre TEXT NOT NULL,
        industria TEXT NOT NULL,
        pais TEXT NOT NULL,
        fecha_firma DATE NOT NULL,
        estado_incorporacion TEXT NOT NULL,
        plantilla_id TEXT NOT NULL,
        ejecutivo_id TEXT NOT NULL,
        proveedor_modelos_fuera_del_pais TEXT CHECK (proveedor_modelos_fuera_del_pais IN ('sí', 'no')),
        fecha_objetivo_produccion DATE NOT NULL,
        FOREIGN KEY (plantilla_id) REFERENCES plantillas(plantilla_id),
        FOREIGN KEY (ejecutivo_id) REFERENCES usuarios(usuario_id)
    );
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS tareas (
        tarea_id TEXT PRIMARY KEY,
        org_id TEXT NOT NULL,
        etapa TEXT NOT NULL CHECK (etapa IN ('E0', 'E1', 'E2', 'E3', 'E4', 'E5')),
        descripcion TEXT NOT NULL,
        obligatoria TEXT CHECK (obligatoria IN ('sí', 'no')),
        estado TEXT NOT NULL CHECK (estado IN ('pendiente', 'en_curso', 'completada')),
        responsable TEXT NOT NULL,
        fecha_limite DATE NOT NULL,
        observacion TEXT,
        FOREIGN KEY (org_id) REFERENCES organizaciones(org_id),
        FOREIGN KEY (responsable) REFERENCES usuarios(usuario_id)
    );
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS integraciones (
        integracion_id TEXT PRIMARY KEY,
        org_id TEXT NOT NULL,
        modo TEXT NOT NULL CHECK (modo IN ('api_asincronica', 'archivos')),
        ambiente TEXT NOT NULL CHECK (ambiente IN ('integracion', 'produccion')),
        estado TEXT NOT NULL CHECK (estado IN ('en_configuracion', 'en_prueba', 'probada', 'operativa')),
        casos_ejemplo_enviados INTEGER NOT NULL,
        llamadas_vuelta_exitosas INTEGER NOT NULL,
        max_llamadas_por_minuto_observado INTEGER NOT NULL,
        FOREIGN KEY (org_id) REFERENCES organizaciones(org_id)
    );
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS formularios_propios (
        formulario_id TEXT PRIMARY KEY,
        org_id TEXT NOT NULL,
        nombre TEXT NOT NULL,
        ejemplos_recibidos INTEGER NOT NULL,
        fecha_ejemplos_completos DATE,
        estado TEXT NOT NULL CHECK (estado IN ('recibido', 'en_ajuste', 'operativo')),
        FOREIGN KEY (org_id) REFERENCES organizaciones(org_id)
    );
    """)

    # 2. Almacén de eventos de mutación (tarea_eventos_cambio)
    if reset_events:
        cursor.execute("DROP TABLE IF EXISTS tarea_eventos_cambio;")

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS tarea_eventos_cambio (
        evento_id INTEGER PRIMARY KEY AUTOINCREMENT,
        tarea_id TEXT NOT NULL,
        org_id TEXT NOT NULL,
        estado_anterior TEXT NOT NULL CHECK (estado_anterior IN ('pendiente', 'en_curso', 'completada')),
        nuevo_estado TEXT NOT NULL CHECK (nuevo_estado IN ('pendiente', 'en_curso', 'completada')),
        usuario_id TEXT NOT NULL,
        rol_usuario TEXT NOT NULL CHECK (rol_usuario IN ('ejecutivo_implementacion', 'jefe_implementacion', 'comercial')),
        justificacion TEXT,
        token_hash TEXT NOT NULL UNIQUE,
        fecha_cambio DATETIME NOT NULL,
        FOREIGN KEY (tarea_id) REFERENCES tareas(tarea_id),
        FOREIGN KEY (org_id) REFERENCES organizaciones(org_id),
        FOREIGN KEY (usuario_id) REFERENCES usuarios(usuario_id)
    );
    """)

    cursor.execute("""
    CREATE INDEX IF NOT EXISTS idx_eventos_tarea ON tarea_eventos_cambio(tarea_id, evento_id DESC);
    """)

    # 3. Vista de estado efectivo (v_tareas_estado_efectivo)
    cursor.execute("DROP VIEW IF EXISTS v_tareas_estado_efectivo;")
    cursor.execute("""
    CREATE VIEW v_tareas_estado_efectivo AS
    SELECT
        t.tarea_id,
        t.org_id,
        t.etapa,
        t.descripcion,
        t.obligatoria,
        COALESCE(ult_ev.nuevo_estado, t.estado) AS estado,
        t.responsable,
        t.fecha_limite,
        t.observacion,
        ult_ev.fecha_cambio AS fecha_ultima_actualizacion,
        ult_ev.usuario_id AS actualizado_por
    FROM tareas t
    LEFT JOIN (
        SELECT e1.tarea_id, e1.nuevo_estado, e1.fecha_cambio, e1.usuario_id
        FROM tarea_eventos_cambio e1
        INNER JOIN (
            SELECT tarea_id, MAX(evento_id) AS max_id
            FROM tarea_eventos_cambio
            GROUP BY tarea_id
        ) e2 ON e1.evento_id = e2.max_id
    ) ult_ev ON t.tarea_id = ult_ev.tarea_id;
    """)

    cursor.execute("PRAGMA foreign_keys = ON;")
    cursor.close()


def import_excel_data(conn, excel_path: Path) -> dict[str, int]:
    """
    Importa de forma reproducible e idempotente las 6 tablas base del kit desde el archivo Excel.
    Abre el libro en modo read_only=True garantizando la inmutabilidad de la fuente original.
    """
    if not excel_path.exists():
        raise FileNotFoundError(f"Archivo de datos Excel no encontrado en: {excel_path}")

    wb = openpyxl.load_workbook(str(excel_path), read_only=True, data_only=True)
    counts: dict[str, int] = {}
    cursor = conn.cursor()

    # Orden de importación respetando integridad referencial
    tables_to_import = [
        "usuarios",
        "plantillas",
        "organizaciones",
        "tareas",
        "integraciones",
        "formularios_propios",
    ]

    try:
        cursor.execute("BEGIN TRANSACTION;")
        # Limpiar datos previos de tablas base para asegurar idempotencia estricta
        for tbl in reversed(tables_to_import):
            cursor.execute(f"DELETE FROM {tbl};")

        for table_name in tables_to_import:
            if table_name not in wb.sheetnames:
                raise ValueError(f"Falta la hoja '{table_name}' en {excel_path}")

            ws = wb[table_name]
            rows_iter = ws.iter_rows(values_only=True)
            try:
                header = next(rows_iter)
            except StopIteration:
                continue

            # Filtrar columnas no vacías del encabezado
            clean_headers = [str(col).strip() for col in header if col is not None]
            placeholders = ", ".join(["?"] * len(clean_headers))
            cols_sql = ", ".join(clean_headers)
            sql = f"INSERT INTO {table_name} ({cols_sql}) VALUES ({placeholders})"

            row_count = 0
            for row in rows_iter:
                # Comprobar si la fila está vacía
                if not any(row):
                    continue
                clean_row = [_format_cell_value(val) for val in row[: len(clean_headers)]]
                cursor.execute(sql, clean_row)
                row_count += 1

            counts[table_name] = row_count

        cursor.execute("COMMIT;")
    except Exception:
        cursor.execute("ROLLBACK;")
        raise
    finally:
        wb.close()
        cursor.close()

    return counts


def init_database(
    db_path: Path | str | None = None,
    excel_path: Path | str | None = None,
    reset_events: bool = False,
    quiet: bool = False,
) -> None:
    """
    Punto de entrada de inicialización de la base de datos relacional.
    """
    target_db = Path(db_path) if db_path else get_db_path()
    target_excel = Path(excel_path) if excel_path else get_excel_path()

    conn = create_connection(target_db)
    try:
        create_schema(conn, reset_events=reset_events)
        counts = import_excel_data(conn, target_excel)

        if not quiet:
            print(f"[OK] Base de datos SQLite inicializada en {target_db.relative_to(PROJECT_ROOT) if target_db.is_relative_to(PROJECT_ROOT) else target_db}")
            print(f"[OK] Tabla 'organizaciones' importada: {counts.get('organizaciones', 0)} registros (ORG-05 a ORG-08)")
            print(f"[OK] Tabla 'usuarios' importada: {counts.get('usuarios', 0)} registros (U-I1 a U-I4)")
            print(f"[OK] Tabla 'plantillas' importada: {counts.get('plantillas', 0)} registros (PLA-REM, PLA-SIN, PLA-CTA, PLA-ADM)")
            print(f"[OK] Tabla 'tareas' importada: {counts.get('tareas', 0)} registros (T-001 a T-037 en etapas E0 a E5)")
            print(f"[OK] Tabla 'integraciones' importada: {counts.get('integraciones', 0)} registros (I-01 a I-04)")
            print(f"[OK] Tabla 'formularios_propios' importada: {counts.get('formularios_propios', 0)} registros (F-01 a F-03)")
            print("[OK] Tabla de eventos 'tarea_eventos_cambio' creada con soporte de hash anti-replay")
            print("[OK] Vista 'v_tareas_estado_efectivo' creada para resolución en tiempo real")
    finally:
        conn.close()


def main():
    parser = argparse.ArgumentParser(
        description="Inicializa e hidrata la base de datos SQLite de MIRA CU-3 desde el Excel oficial del kit."
    )
    parser.add_argument("--db", type=str, default=None, help="Ruta al archivo SQLite destino")
    parser.add_argument("--excel", type=str, default=None, help="Ruta al archivo Excel del kit CU-3")
    parser.add_argument(
        "--reset-events",
        action="store_true",
        help="Si se especifica, vacía y reinicia también la tabla tarea_eventos_cambio.",
    )
    args = parser.parse_args()

    init_database(db_path=args.db, excel_path=args.excel, reset_events=args.reset_events)


if __name__ == "__main__":
    main()

