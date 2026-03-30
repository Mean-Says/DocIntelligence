"""
Upload/download de arquivos.
- Produção: Cloudflare R2 (S3-compatible)
- Dev/testes: sistema de arquivos local (quando R2 não configurado)
"""
import asyncio
import shutil
from pathlib import Path

import boto3
from botocore.config import Config

from app.config import settings

_client = None
_LOCAL_STORE = Path("./local_storage")  # usado quando R2 não está configurado


def _is_r2_configured() -> bool:
    url = settings.r2_endpoint_url
    return bool(url) and "<account_id>" not in url and url.startswith("http")


def _get_client():
    global _client
    if _client is None:
        _client = boto3.client(
            "s3",
            endpoint_url=settings.r2_endpoint_url,
            aws_access_key_id=settings.r2_access_key_id,
            aws_secret_access_key=settings.r2_secret_access_key,
            config=Config(signature_version="s3v4"),
        )
    return _client


async def upload(local_path: str, storage_key: str) -> str:
    if not _is_r2_configured():
        dest = _LOCAL_STORE / storage_key
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(local_path, dest)
        return storage_key

    await asyncio.to_thread(
        _get_client().upload_file,
        local_path,
        settings.r2_bucket_name,
        storage_key,
    )
    return storage_key


async def download(storage_key: str, local_path: str) -> None:
    if not _is_r2_configured():
        src = _LOCAL_STORE / storage_key
        shutil.copy2(src, local_path)
        return

    await asyncio.to_thread(
        _get_client().download_file,
        settings.r2_bucket_name,
        storage_key,
        local_path,
    )


async def delete(storage_key: str) -> None:
    if not _is_r2_configured():
        path = _LOCAL_STORE / storage_key
        path.unlink(missing_ok=True)
        return

    await asyncio.to_thread(
        _get_client().delete_object,
        Bucket=settings.r2_bucket_name,
        Key=storage_key,
    )
