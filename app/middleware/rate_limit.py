"""
Rate limiting em memória (sliding window).
Em produção com múltiplas instâncias, trocar por Redis.
"""
import time
from collections import defaultdict, deque
from threading import Lock

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse


class _SlidingWindow:
    """Conta requisições em janela deslizante thread-safe."""

    def __init__(self):
        self._windows: dict[str, deque] = defaultdict(deque)
        self._lock = Lock()

    def is_allowed(self, key: str, limit: int, window_seconds: int) -> tuple[bool, int]:
        now = time.monotonic()
        cutoff = now - window_seconds

        with self._lock:
            dq = self._windows[key]
            # Remove timestamps expirados
            while dq and dq[0] < cutoff:
                dq.popleft()

            count = len(dq)
            if count >= limit:
                retry_after = int(window_seconds - (now - dq[0])) + 1
                return False, retry_after

            dq.append(now)
            return True, 0


_store = _SlidingWindow()


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Dois limites:
    - Por IP: 60 req/min (proteção contra brute force / bots)
    - Por API key: 100 req/min (limite por cliente)
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        ip = request.headers.get("x-forwarded-for", request.client.host if request.client else "unknown")
        ip = ip.split(",")[0].strip()

        # Limite por IP
        allowed, retry_after = _store.is_allowed(f"ip:{ip}", limit=60, window_seconds=60)
        if not allowed:
            return JSONResponse(
                status_code=429,
                content={"detail": "Muitas requisições. Tente novamente em breve."},
                headers={"Retry-After": str(retry_after)},
            )

        # Limite por API key (extraída do header Authorization)
        auth = request.headers.get("authorization", "")
        if auth.startswith("Bearer "):
            token_prefix = auth[7:16]  # primeiros 9 chars do token como chave
            allowed, retry_after = _store.is_allowed(f"key:{token_prefix}", limit=100, window_seconds=60)
            if not allowed:
                return JSONResponse(
                    status_code=429,
                    content={"detail": "Limite de requisições por minuto atingido."},
                    headers={"Retry-After": str(retry_after)},
                )

        return await call_next(request)
