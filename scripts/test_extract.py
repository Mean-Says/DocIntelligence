"""
Teste end-to-end: envia um documento e acompanha o resultado.
Uso: python scripts/test_extract.py --api-key di_sk_... --file /path/to/doc.pdf [--doc-type nfe]

Requer API rodando em localhost:8000.
"""
import asyncio
import sys
import argparse
import time
from pathlib import Path

import httpx


BASE_URL = "http://localhost:8000"
POLL_INTERVAL = 1.0   # segundos
MAX_WAIT = 60         # timeout


async def run(api_key: str, file_path: str, doc_type: str | None):
    headers = {"Authorization": f"Bearer {api_key}"}
    path = Path(file_path)

    if not path.exists():
        print(f"❌ Arquivo não encontrado: {file_path}")
        sys.exit(1)

    async with httpx.AsyncClient(base_url=BASE_URL, timeout=30) as client:
        # ── Health check ─────────────────────────────────────────────────────
        health = await client.get("/health")
        if health.status_code != 200:
            print(f"❌ API não está rodando em {BASE_URL}")
            sys.exit(1)
        print(f"✓ API OK ({BASE_URL})")

        # ── Upload ───────────────────────────────────────────────────────────
        print(f"\n→ Enviando: {path.name} ({path.stat().st_size / 1024:.1f} KB)")

        files = {"file": (path.name, path.read_bytes(), _mime(path))}
        data = {}
        if doc_type:
            data["doc_type"] = doc_type

        t0 = time.monotonic()
        resp = await client.post("/v1/extract", headers=headers, files=files, data=data)

        if resp.status_code != 202:
            print(f"❌ Erro no upload: {resp.status_code}")
            print(resp.text)
            sys.exit(1)

        job = resp.json()
        print(f"✓ Job criado: {job['job_id']}")
        print(f"  document_id: {job['document_id']}")

        # ── Polling ──────────────────────────────────────────────────────────
        print("\n⏳ Aguardando resultado", end="", flush=True)
        status_url = f"/v1/extract/jobs/{job['job_id']}"
        elapsed = 0.0

        while elapsed < MAX_WAIT:
            await asyncio.sleep(POLL_INTERVAL)
            elapsed += POLL_INTERVAL
            print(".", end="", flush=True)

            poll = await client.get(status_url, headers=headers)
            result = poll.json()

            if result["status"] == "done":
                total_ms = int((time.monotonic() - t0) * 1000)
                print(f" pronto! ({total_ms}ms total)\n")
                _print_result(result)
                return

            if result["status"] == "failed":
                print(f"\n❌ Job falhou: {result.get('error')}")
                sys.exit(1)

        print(f"\n⚠️  Timeout após {MAX_WAIT}s — job ainda em processamento")
        sys.exit(1)


def _print_result(result: dict):
    print("=" * 60)
    print(f"  Tipo de documento: {result.get('doc_type')} "
          f"(confiança: {result.get('doc_type_confidence', 0):.0%})")
    print(f"  Nível de processamento: {result.get('processing_level')} "
          f"({'local - sem custo de AI' if result.get('processing_level', 5) <= 2 else 'AI utilizada'})")
    print(f"  Confiança geral: {result.get('overall_confidence', 0):.0%}")
    print(f"  Tempo de processamento: {result.get('processing_ms')}ms")
    print()
    print("  Campos extraídos:")
    for field, value in (result.get("data") or {}).items():
        conf = (result.get("confidence") or {}).get(field, 0)
        print(f"    {field:<25} {value:<30} ({conf:.0%})")
    print("=" * 60)


def _mime(path: Path) -> str:
    ext = path.suffix.lower()
    return {
        ".pdf": "application/pdf",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".tiff": "image/tiff",
    }.get(ext, "application/octet-stream")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Testa extração de documento")
    parser.add_argument("--api-key", required=True)
    parser.add_argument("--file", required=True)
    parser.add_argument("--doc-type", default=None)
    args = parser.parse_args()

    asyncio.run(run(args.api_key, args.file, args.doc_type))
