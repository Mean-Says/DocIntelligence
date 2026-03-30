"""
Middleware de auditoria: loga toda requisição no banco.
"""
import time
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.db import AsyncSessionLocal
from app.models.audit_log import AuditLog


class AuditMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        start = time.monotonic()
        response = await call_next(request)
        latency_ms = int((time.monotonic() - start) * 1000)

        # Não loga health check para não poluir
        if request.url.path == "/health":
            return response

        client_id = getattr(request.state, "client_id", None)
        document_id = getattr(request.state, "document_id", None)
        ip = request.headers.get("x-forwarded-for", request.client.host if request.client else "unknown")
        ip = ip.split(",")[0].strip()  # pega o IP real se tiver proxy

        try:
            async with AsyncSessionLocal() as session:
                log = AuditLog(
                    client_id=client_id,
                    ip_address=ip,
                    method=request.method,
                    path=request.url.path,
                    status_code=response.status_code,
                    latency_ms=latency_ms,
                    user_agent=request.headers.get("user-agent"),
                    document_id=document_id,
                )
                session.add(log)
                await session.commit()
        except Exception:
            pass  # nunca deixa o log quebrar a resposta

        return response
