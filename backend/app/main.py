"""Punto de entrada principal de la aplicación FastAPI para MIRA CU-3.

Monta los ruteadores oficiales según contracts/api-rest.yaml y configura
los controles de seguridad, CORS restrictivo y manejadores de error estandarizados.
"""

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from backend.app.config import get_settings
from backend.app.routers.session import router as session_router
from backend.app.routers.chat import router as chat_router
from backend.app.routers.actions import router as actions_router


def create_app() -> FastAPI:
    """Crea y configura la aplicación FastAPI de MIRA CU-3."""
    settings = get_settings()

    app = FastAPI(
        title="MIRA CU-3 - API Asistente de Incorporación de Organizaciones",
        description=(
            "API REST del orquestador backend de MIRA para el Caso de Uso CU-3 "
            "(Incorporación de Organizaciones)."
        ),
        version="1.2.0",
        docs_url="/docs",
        redoc_url="/redoc",
    )

    # Configuración de CORS restrictivo basado en config.py
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["*"],
    )

    # Manejador estandarizado de excepciones HTTP para respetar el esquema ApiError
    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request: Request, exc: StarletteHTTPException):
        if isinstance(exc.detail, dict) and "code" in exc.detail and "message" in exc.detail:
            return JSONResponse(
                status_code=exc.status_code,
                content=exc.detail,
            )
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "code": "HTTP_ERROR",
                "message": str(exc.detail),
                "principle_violated": None,
                "details": None,
            },
        )

    # Manejador de validación de esquemas de petición (HTTP 400 con ApiError)
    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "code": "INVALID_REQUEST_BODY",
                "message": "Solicitud malformada o parámetros requeridos ausentes.",
                "principle_violated": "PR-7",
                "details": {"errors": exc.errors()},
            },
        )

    # Inclusión de ruteadores implementados
    app.include_router(session_router)
    app.include_router(chat_router)
    app.include_router(actions_router)

    return app


app = create_app()
