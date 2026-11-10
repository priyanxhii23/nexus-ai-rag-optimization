"""Security helpers: tenant IDs, rate limiting, prompt-injection screening, upload checks."""
import re
import threading
import time
from collections import defaultdict, deque

from fastapi import Header

from app.core.errors import AppError

DEFAULT_TENANT = "local"
_TENANT_RE = re.compile(r"^[a-zA-Z0-9_-]{1,64}$")


def tenant_id(x_tenant_id: str | None = Header(default=None)) -> str:
    """Tenant boundary. Single-user installs use 'local'; the header lets tests
    (and a future multi-user version) prove that data never crosses tenants."""
    t = (x_tenant_id or DEFAULT_TENANT).strip()
    if not _TENANT_RE.match(t):
        raise AppError("Invalid X-Tenant-ID header.", 400, "invalid_tenant")
    return t


class RateLimiter:
    """Sliding-window limiter per client key (in memory; fine for one local process)."""

    def __init__(self, per_minute: int):
        self.per_minute = per_minute
        self._hits: dict[str, deque] = defaultdict(deque)
        self._lock = threading.Lock()

    def check(self, key: str) -> bool:
        now = time.monotonic()
        with self._lock:
            q = self._hits[key]
            while q and now - q[0] > 60:
                q.popleft()
            if len(q) >= self.per_minute:
                return False
            q.append(now)
            return True


# ---------------------------------------------------------------- prompt injection
# Uploaded documents are UNTRUSTED. These patterns are a heuristic tripwire:
# matching chunks are still usable as facts, but are flagged, logged (without
# content) and wrapped so the model treats them as data, never instructions.
_INJECTION_PATTERNS = [
    r"ignore (all |any )?(the )?(previous|prior|above) (instructions|prompts?)",
    r"disregard (all |any )?(the )?(previous|prior|above)",
    r"you are now (a|an|in) ",
    r"\bsystem prompt\b",
    r"reveal (your|the) (instructions|prompt|api key|secrets?)",
    r"</?(system|assistant|instructions?)>",
    r"\bdo anything now\b",
    r"act as (an? )?(unrestricted|jailbroken)",
]
_INJECTION_RE = re.compile("|".join(_INJECTION_PATTERNS), re.IGNORECASE)


def looks_like_injection(text: str) -> bool:
    return bool(_INJECTION_RE.search(text))


def neutralise_markup(text: str) -> str:
    """Stop document text from closing our <document> wrapper or faking tags."""
    return text.replace("<", "‹").replace(">", "›")


# ---------------------------------------------------------------- uploads
ALLOWED_EXTENSIONS = {".pdf": "application/pdf", ".txt": "text/plain", ".md": "text/markdown"}
_SAFE_NAME_RE = re.compile(r"[^A-Za-z0-9._ -]+")


def safe_filename(name: str) -> str:
    base = (name or "document").replace("\\", "/").split("/")[-1]
    base = _SAFE_NAME_RE.sub("_", base).strip(" .") or "document"
    return base[:200]


def validate_upload(filename: str, data: bytes, max_bytes: int) -> str:
    """Return the normalised extension or raise AppError."""
    ext = ("." + filename.rsplit(".", 1)[-1].lower()) if "." in filename else ""
    if ext not in ALLOWED_EXTENSIONS:
        raise AppError(f"Unsupported file type '{ext or 'none'}'. Upload PDF, TXT or MD files.", 415, "unsupported_type")
    if not data:
        raise AppError("The file is empty.", 400, "empty_file")
    if len(data) > max_bytes:
        raise AppError(f"File is larger than the {max_bytes // 1_000_000} MB limit.", 413, "file_too_large")
    if ext == ".pdf" and not data[:1024].lstrip().startswith(b"%PDF-"):
        raise AppError("This file has a .pdf name but is not a PDF.", 415, "invalid_pdf")
    if ext in {".txt", ".md"}:
        if b"\x00" in data[:4096]:
            raise AppError("This does not look like a text file.", 415, "invalid_text")
    return ext
