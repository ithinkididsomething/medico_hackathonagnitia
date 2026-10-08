"""FastAPI application entry point.

Start with:
    uvicorn app.main:app --reload --port 8000
"""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .api.routes import API_VERSION, router as api_router
from .config import get_settings
from .db.connection import init_db
from .maps.errors import MapsServiceError
from .rules.engine import RuleError


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.database_url = init_db()
    yield


app = FastAPI(
    title="medico API",
    version=API_VERSION,
    description=(
        "Clinical referral decision-support prototype API: health, patient "
        "assessment (urgency + initial clinic decision), demonstration rule "
        "engine, maps config. Decision support only — not a medical device."
    ),
    lifespan=lifespan,
)

settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_origin],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix="/api")


@app.exception_handler(MapsServiceError)
async def maps_service_error_handler(request: Request, exc: MapsServiceError) -> JSONResponse:
    return JSONResponse(status_code=502, content={"detail": str(exc)})


@app.exception_handler(RuleError)
async def rule_error_handler(request: Request, exc: RuleError) -> JSONResponse:
    return JSONResponse(status_code=422, content={"detail": str(exc)})


@app.exception_handler(Exception)
async def unhandled_error_handler(request: Request, exc: Exception) -> JSONResponse:
    # Never leak stack traces or secrets to the client.
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})
