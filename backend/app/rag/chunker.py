"""Split documents into overlapping chunks.

Why chunk? Retrieval works best on passages of a few paragraphs: small enough
to be about one thing, large enough to carry context. Overlap keeps a sentence
that straddles a boundary present in both neighbouring chunks.

Strategy: split on paragraphs, then sentences, then words, packing pieces
greedily up to `size` characters, carrying `overlap` characters forward.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from app.rag.extract import ExtractedPage

_SENTENCE_RE = re.compile(r"(?<=[.!?])\s+")


@dataclass
class Chunk:
    index: int
    text: str
    page: int | None
    char_start: int
    char_end: int


def _clean(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n").replace("\x00", "")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _pieces(text: str, size: int) -> list[str]:
    out: list[str] = []
    for para in re.split(r"\n\s*\n", text):
        para = para.strip()
        if not para:
            continue
        if len(para) <= size:
            out.append(para)
            continue
        for sent in _SENTENCE_RE.split(para):
            if len(sent) <= size:
                out.append(sent)
            else:  # very long sentence: hard-wrap on words
                words, buf = sent.split(), ""
                for w in words:
                    if len(buf) + len(w) + 1 > size and buf:
                        out.append(buf)
                        buf = w
                    else:
                        buf = f"{buf} {w}".strip()
                if buf:
                    out.append(buf)
    return out


def chunk_pages(pages: list[ExtractedPage], size: int = 900, overlap: int = 150) -> list[Chunk]:
    chunks: list[Chunk] = []
    offset = 0
    for page in pages:
        text = _clean(page.text)
        if not text:
            continue
        buf = ""
        for piece in _pieces(text, size):
            candidate = f"{buf}\n\n{piece}" if buf else piece
            if len(candidate) <= size:
                buf = candidate
                continue
            if buf:
                chunks.append(Chunk(len(chunks), buf, page.page, offset, offset + len(buf)))
                offset += len(buf)
                tail = buf[-overlap:] if overlap else ""
                # start the overlap at a word boundary
                tail = tail[tail.find(" ") + 1:] if " " in tail else tail
                buf = f"{tail} {piece}".strip() if tail else piece
            else:
                buf = piece
        if buf:
            chunks.append(Chunk(len(chunks), buf, page.page, offset, offset + len(buf)))
            offset += len(buf)
    return chunks
