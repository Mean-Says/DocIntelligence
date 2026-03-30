"""
OCR via pytesseract para PDFs escaneados e imagens.
"""
import asyncio
from pathlib import Path

import pytesseract
from PIL import Image
import fitz  # pymupdf


async def extract_text_from_file(file_path: str) -> str:
    """Executa OCR em thread separada para não bloquear o event loop."""
    return await asyncio.to_thread(_run_ocr, file_path)


def _run_ocr(file_path: str) -> str:
    suffix = Path(file_path).suffix.lower()

    if suffix == ".pdf":
        return _ocr_pdf(file_path)
    else:
        return _ocr_image(file_path)


def _ocr_pdf(file_path: str) -> str:
    """Converte cada página do PDF em imagem e aplica OCR."""
    doc = fitz.open(file_path)
    texts: list[str] = []

    for page in doc:
        # Renderiza em 300 DPI para melhor precisão
        mat = fitz.Matrix(300 / 72, 300 / 72)
        pix = page.get_pixmap(matrix=mat)
        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
        text = pytesseract.image_to_string(img, lang="por+eng")
        texts.append(text)

    doc.close()
    return "\n\n".join(texts)


def _ocr_image(file_path: str) -> str:
    img = Image.open(file_path)
    return pytesseract.image_to_string(img, lang="por+eng")
