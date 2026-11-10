"""Builds a tiny, valid, multi-page text PDF without extra dependencies (used by tests)."""


def make_pdf(pages: list[str]) -> bytes:
    objs: list[bytes] = []
    kids = []
    n_pages = len(pages)
    # object numbers: 1 catalog, 2 pages, 3 font, then (page, content) pairs
    for i, text in enumerate(pages):
        page_no, content_no = 4 + 2 * i, 5 + 2 * i
        kids.append(f"{page_no} 0 R")
        lines = [ln.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)") for ln in text.split("\n")]
        stream = "BT /F1 11 Tf 50 780 Td 14 TL " + " ".join(f"({ln}) Tj T*" for ln in lines) + " ET"
        objs.append((page_no, f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 842] "
                              f"/Resources << /Font << /F1 3 0 R >> >> /Contents {content_no} 0 R >>".encode()))
        objs.append((content_no, f"<< /Length {len(stream)} >>\nstream\n{stream}\nendstream".encode()))
    objs = [(1, b"<< /Type /Catalog /Pages 2 0 R >>"),
            (2, f"<< /Type /Pages /Kids [{' '.join(kids)}] /Count {n_pages} >>".encode()),
            (3, b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")] + objs
    objs.sort()
    out = bytearray(b"%PDF-1.4\n")
    offsets = {}
    for num, body in objs:
        offsets[num] = len(out)
        out += f"{num} 0 obj\n".encode() + body + b"\nendobj\n"
    xref = len(out)
    out += f"xref\n0 {len(objs) + 1}\n0000000000 65535 f \n".encode()
    for num, _ in objs:
        out += f"{offsets[num]:010d} 00000 n \n".encode()
    out += f"trailer\n<< /Size {len(objs) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    return bytes(out)
