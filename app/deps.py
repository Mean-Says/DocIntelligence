from typing import AsyncGenerator, Annotated
from fastapi import Depends, HTTPException, Request, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlmodel import select
import bcrypt
import hashlib

from app.db import AsyncSessionLocal
from app.models import Client

bearer_scheme = HTTPBearer()


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session


SessionDep = Annotated[AsyncSession, Depends(get_session)]


def _token_lookup_hash(token: str) -> str:
    """SHA-256 do token — usado como índice de lookup, não como hash de segurança.
    Permite busca O(1) por api_key sem iterar todos os clientes.
    A verificação bcrypt final garante a segurança.
    """
    return hashlib.sha256(token.encode()).hexdigest()


async def get_current_client(
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials, Security(bearer_scheme)],
    session: SessionDep,
) -> Client:
    token = credentials.credentials
    lookup = _token_lookup_hash(token)

    # Busca por lookup_hash — O(1) com índice único
    result = await session.exec(
        select(Client).where(
            Client.api_key_lookup == lookup,
            Client.is_active == True,
        )
    )
    client = result.first()

    if not client or not bcrypt.checkpw(token.encode(), client.api_key_hash.encode()):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API key inválida",
        )

    # Disponibiliza client_id para o middleware de auditoria
    request.state.client_id = client.id
    return client


ClientDep = Annotated[Client, Depends(get_current_client)]
