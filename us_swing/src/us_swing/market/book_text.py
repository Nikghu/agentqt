"""
Module: MD-MKT-018.002.M02 — market/book_text.py
Parent SRD: SRD-MKT-018.002
Also: SRD-MKT-018.003 (books folder and Project Gutenberg only), SRD-MKT-018.004 (text,
Markdown, HTML and PDF readers), SRD-MKT-018.005 (chapter split)

Book text for a book ticket. The topic names the source and chapter; the text comes only
from the owner's books folder or from the Project Gutenberg plain-text file of that number,
downloaded once and kept. Chapters are split at chapter headings, or into equal parts.
"""
from __future__ import annotations

import os
import re
import tempfile
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path

import httpx

from us_swing.core.desk_books import BOOK_TYPES
from us_swing.market.news import Getter

PART_WORDS = 5_000
MIN_CHAPTER_WORDS = 100
MAX_CHARS = 24_000
MAX_BYTES = 20_000_000
MAX_PAGES = 500
TIMEOUT_S = 20.0
GUTENBERG_URL = "https://www.gutenberg.org/cache/epub/{n}/pg{n}.txt"
_UPLOAD = re.compile(r"^upload:([^/\\:]+\.(?:txt|md|html?|pdf)) ch (\d{1,3})$", re.IGNORECASE)
_GUTENBERG = re.compile(r"^gutenberg:(\d{1,6}) ch (\d{1,3})$", re.IGNORECASE)
_HEADING = re.compile(r"^[ \t]*(?:chapter|chap\.)[ \t]+(?:\d+|[ivxlcdm]+)\b.*$",
                      re.IGNORECASE | re.MULTILINE)
TOPIC_HELP = ("Book tickets need the topic form upload:<file> ch <n> or "
              "gutenberg:<number> ch <n>")


class BookError(Exception):
    """A book problem the ticket reports in plain words."""


@dataclass(frozen=True)
class BookRef:
    """Where a book comes from and which chapter to read."""

    kind: str
    name: str
    chapter: int

    @property
    def source(self) -> str:
        """The source as written in the topic, for example ``upload:my_book.txt``."""
        return f"{self.kind}:{self.name}"

    @property
    def key(self) -> str:
        """The source in lower case, so one file is one book whatever its case."""
        return self.source.lower()


def parse_topic(topic: str) -> BookRef | None:
    """Read the source and chapter from a book ticket topic, or ``None`` when not valid."""
    text = topic.strip()
    found = _UPLOAD.match(text)
    if found and found.group(1) not in (".", "..") and not found.group(1).startswith("."):
        return BookRef("upload", found.group(1), int(found.group(2)))
    found = _GUTENBERG.match(text)
    if found:
        return BookRef("gutenberg", str(int(found.group(1))), int(found.group(2)))
    return None


class _Text(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []
        self._skip = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in ("script", "style"):
            self._skip += 1
        elif tag in ("p", "br", "div", "h1", "h2", "h3", "li"):
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in ("script", "style") and self._skip:
            self._skip -= 1

    def handle_data(self, data: str) -> None:
        if not self._skip:
            self.parts.append(data)


def _html(text: str) -> str:
    parser = _Text()
    parser.feed(text)
    return "".join(parser.parts)


def _pdf(path: Path) -> str:
    from pypdf import PdfReader  # noqa: PLC0415 — only book tickets need it
    from pypdf.errors import PdfReadError  # noqa: PLC0415

    try:
        reader = PdfReader(str(path))
        if len(reader.pages) > MAX_PAGES:
            raise BookError(f"{path.name} has more than {MAX_PAGES} pages")
        return "\n".join(page.extract_text() or "" for page in reader.pages)
    except BookError:
        raise
    except (PdfReadError, Exception) as exc:  # noqa: BLE001 — any PDF fault ends the ticket
        raise BookError(f"{path.name} could not be read as a PDF") from exc


def read_file(path: Path) -> str:
    """Plain text of a ``.txt``, ``.md``, ``.html``/``.htm`` or ``.pdf`` file."""
    suffix = path.suffix.lower()
    if suffix not in BOOK_TYPES:
        raise BookError(f"{path.name} is not a text, Markdown, HTML or PDF file")
    if path.stat().st_size > MAX_BYTES:
        raise BookError(f"{path.name} is larger than 20 MB")
    if suffix == ".pdf":
        return _pdf(path)
    text = path.read_text(encoding="utf-8", errors="replace")
    return _html(text) if suffix in (".html", ".htm") else text


def _strip_gutenberg(text: str) -> str:
    start = re.search(r"^\*\*\* ?START OF.*$", text, re.MULTILINE)
    end = re.search(r"^\*\*\* ?END OF.*$", text, re.MULTILINE)
    return text[start.end() if start else 0:end.start() if end else len(text)]


def gutenberg_get(url: str) -> str:
    """Download ``url``; refuse a reply from any host but gutenberg.org or above 20 MB."""
    with httpx.stream("GET", url, timeout=TIMEOUT_S, follow_redirects=True,
                      headers={"User-Agent": "USSwing/1.0"}) as reply:
        reply.raise_for_status()
        host = reply.url.host or ""
        if host != "gutenberg.org" and not host.endswith(".gutenberg.org"):
            raise BookError("The download left gutenberg.org")
        body = bytearray()
        for chunk in reply.iter_bytes():
            body += chunk
            if len(body) > MAX_BYTES:
                raise BookError("The Gutenberg file is larger than 20 MB")
    return body.decode("utf-8", errors="replace")


def _save(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, suffix=".part")
    with os.fdopen(fd, "w", encoding="utf-8") as out:
        out.write(text)
    os.replace(tmp, path)


def load_text(ref: BookRef, folder: Path, get: Getter = gutenberg_get) -> str:
    """The whole book text; a Gutenberg book is downloaded once into ``folder``."""
    if ref.kind == "upload":
        path = folder / ref.name
        if not path.is_file():
            raise BookError(f"{ref.name} is not in the books folder")
        return read_file(path)
    cache = folder / f"gutenberg-{ref.name}.txt"
    if not cache.is_file():
        try:
            raw = get(GUTENBERG_URL.format(n=ref.name))
        except Exception as exc:  # noqa: BLE001 — any download failure ends the ticket plainly
            raise BookError(f"Project Gutenberg book {ref.name} could not be downloaded") from exc
        body = _strip_gutenberg(raw).strip()
        if not body:
            raise BookError(f"Project Gutenberg book {ref.name} came back empty")
        _save(cache, body)
    return cache.read_text(encoding="utf-8", errors="replace")


def chapters(text: str) -> list[str]:
    """Split at chapter headings, else into 5,000-word parts.

    Heading sections under 100 words (a table of contents) are left out.
    """
    marks = [m.start() for m in _HEADING.finditer(text)]
    ends = [*marks[1:], len(text)] if marks else []
    parts = [text[a:b].strip() for a, b in zip(marks, ends, strict=True)]
    parts = [p for p in parts if len(p.split()) >= MIN_CHAPTER_WORDS]
    if len(parts) >= 2:
        return parts
    words = text.split()
    return [" ".join(words[i:i + PART_WORDS]) for i in range(0, len(words), PART_WORDS)]


def chapter(text: str, number: int) -> str:
    """Chapter ``number`` (from 1), cut to 24,000 characters."""
    parts = chapters(text)
    if not 1 <= number <= len(parts):
        raise BookError(f"The book has only {len(parts)} chapter(s)")
    return parts[number - 1][:MAX_CHARS]
