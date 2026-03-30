"""
Valida mime type real inspecionando os magic bytes do arquivo.
Não confia no Content-Type declarado pelo cliente.
"""

# Magic bytes de cada formato suportado
_SIGNATURES: list[tuple[bytes, str]] = [
    (b"%PDF", "application/pdf"),
    (b"\xff\xd8\xff", "image/jpeg"),
    (b"\x89PNG\r\n\x1a\n", "image/png"),
    (b"II\x2a\x00", "image/tiff"),   # TIFF little-endian
    (b"MM\x00\x2a", "image/tiff"),   # TIFF big-endian
    (b"RIFF", "image/webp"),         # WebP começa com RIFF....WEBP
]

ALLOWED_MIME_TYPES = {sig[1] for sig in _SIGNATURES}


def detect_mime(content: bytes) -> str | None:
    """
    Retorna o mime type real baseado nos magic bytes.
    Retorna None se não reconhecido.
    """
    for magic, mime in _SIGNATURES:
        if content[:len(magic)] == magic:
            # WebP precisa de validação extra
            if mime == "image/webp" and content[8:12] != b"WEBP":
                continue
            return mime
    return None


def is_allowed(content: bytes) -> tuple[bool, str]:
    """
    Retorna (permitido, mime_type_detectado).
    """
    mime = detect_mime(content)
    if mime is None:
        return False, "application/octet-stream"
    return mime in ALLOWED_MIME_TYPES, mime
