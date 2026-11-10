"""Text extraction from PDF / TXT / MD files."""
from __future__ import annotations

import io
from dataclasses import dataclass

from app.core.errors import AppError


@dataclass
class ExtractedPage:
    page: int | None   # 1-based page number for PDFs, None for text files
    text: str


def extract_pages(data: bytes, ext: str) -> list[ExtractedPage]:
    if ext == ".pdf":
        from pypdf import PdfReader
        from pypdf.errors import PdfReadError

        try:
            reader = PdfReader(io.BytesIO(data))
            if reader.is_encrypted:
                raise AppError("Encrypted PDFs are not supported. Remove the password and upload again.",
                               415, "encrypted_pdf")
            pages = [ExtractedPage(i + 1, (p.extract_text() or "")) for i, p in enumerate(reader.pages)]
        except AppError:
            raise
        except (PdfReadError, ValueError, KeyError, TypeError) as exc:
            raise AppError(f"Could not read this PDF ({type(exc).__name__}).", 422, "unreadable_pdf") from exc
        if not any(p.text.strip() for p in pages):
            raise AppError("No text found in this PDF. Scanned (image-only) PDFs need OCR, which is not supported.",
                           422, "no_text")
        return pages

    for enc in ("utf-8-sig", "utf-16", "cp1252"):
        try:
            text = data.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    else:  # pragma: no cover
        raise AppError("Could not decode the text file (use UTF-8).", 422, "bad_encoding")
    if not text.strip():
        raise AppError("The text file is empty.", 400, "empty_file")
    return [ExtractedPage(None, text)]
