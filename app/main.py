from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import router as v1_router
from app.config import settings
from app.middleware.audit import AuditMiddleware
from app.middleware.rate_limit import RateLimitMiddleware


@asynccontextmanager
async def lifespan(app: FastAPI):
    if settings.is_production and settings.secret_key == "change-me-in-production":
        raise RuntimeError("SECRET_KEY não pode ser o valor padrão em produção.")
    yield


app = FastAPI(
    title="DocIntelligence API",
    version="0.1.0",
    docs_url="/docs" if not settings.is_production else None,
    redoc_url=None,
    lifespan=lifespan,
)

# Middlewares — ordem importa: rate limit antes de auditoria
app.add_middleware(RateLimitMiddleware)
app.add_middleware(AuditMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if not settings.is_production else [],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(v1_router)


@app.get("/health")
async def health():
    return {"status": "ok", "env": settings.env}
