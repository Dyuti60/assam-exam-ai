from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import dataclass
from hashlib import sha256
from html.parser import HTMLParser
from io import BytesIO
from typing import ClassVar
from xml.etree import ElementTree

from pypdf import PdfReader

EXTRACTOR_KEY = "deterministic-text-v1"
MAX_CHUNK_CHARACTERS = 1_000
CHUNK_OVERLAP_CHARACTERS = 100

SUPPORTED_CONTENT_TYPES = {
    "application/pdf",
    "text/plain",
    "text/html",
    "application/json",
    "application/xml",
    "text/xml",
}


class SourceExtractionError(Exception):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True)
class ExtractedChunk:
    position: int
    char_start: int
    char_end: int
    text: str
    sha256: str


@dataclass(frozen=True)
class ExtractedDocument:
    text: str
    sha256: str
    chunks: tuple[ExtractedChunk, ...]


class _VisibleHtmlParser(HTMLParser):
    _hidden_tags: ClassVar[frozenset[str]] = frozenset(
        {"head", "script", "style", "template", "noscript", "svg"}
    )
    _block_tags: ClassVar[frozenset[str]] = frozenset(
        {
            "address",
            "article",
            "aside",
            "blockquote",
            "br",
            "dd",
            "div",
            "dl",
            "dt",
            "figcaption",
            "figure",
            "footer",
            "h1",
            "h2",
            "h3",
            "h4",
            "h5",
            "h6",
            "header",
            "hr",
            "li",
            "main",
            "nav",
            "ol",
            "p",
            "pre",
            "section",
            "table",
            "td",
            "th",
            "tr",
            "ul",
        }
    )

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.hidden_depth = 0

    def handle_starttag(
        self,
        tag: str,
        attrs: list[tuple[str, str | None]],
    ) -> None:
        del attrs
        tag = tag.lower()
        if tag in self._hidden_tags:
            self.hidden_depth += 1
        elif not self.hidden_depth and tag in self._block_tags:
            self.parts.append("\n")

    def handle_startendtag(
        self,
        tag: str,
        attrs: list[tuple[str, str | None]],
    ) -> None:
        del attrs
        if not self.hidden_depth and tag.lower() in self._block_tags:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag in self._hidden_tags:
            if self.hidden_depth:
                self.hidden_depth -= 1
        elif not self.hidden_depth and tag in self._block_tags:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        if not self.hidden_depth:
            self.parts.append(data)


def extract_document(
    content_bytes: bytes,
    content_type: str,
    *,
    max_input_bytes: int,
    max_characters: int,
    max_chunks: int,
) -> ExtractedDocument:
    if len(content_bytes) > max_input_bytes:
        raise SourceExtractionError("EXTRACTION_INPUT_TOO_LARGE")
    if content_type not in SUPPORTED_CONTENT_TYPES:
        raise SourceExtractionError("EXTRACTION_UNSUPPORTED_CONTENT_TYPE")

    raw_text = _extract_text(content_bytes, content_type)
    text = normalize_text(raw_text)
    if not text:
        raise SourceExtractionError("EXTRACTION_EMPTY_TEXT")
    if len(text) > max_characters:
        raise SourceExtractionError("EXTRACTION_TEXT_TOO_LARGE")

    chunks = chunk_text(text)
    if len(chunks) > max_chunks:
        raise SourceExtractionError("EXTRACTION_CHUNK_LIMIT")
    return ExtractedDocument(
        text=text,
        sha256=sha256(text.encode("utf-8")).hexdigest(),
        chunks=chunks,
    )


def normalize_text(value: str) -> str:
    value = unicodedata.normalize("NFC", value)
    value = value.replace("\r\n", "\n").replace("\r", "\n")
    value = value.replace("\u00a0", " ")
    normalized_characters: list[str] = []
    for character in value:
        if character == "\n":
            normalized_characters.append(character)
        elif character == "\t":
            normalized_characters.append(" ")
        elif unicodedata.category(character) not in {"Cc", "Cf"}:
            normalized_characters.append(character)
    value = "".join(normalized_characters)
    value = "\n".join(line.rstrip(" \t") for line in value.split("\n"))
    value = re.sub(r"\n{3,}", "\n\n", value)
    value = value.strip()
    return f"{value}\n" if value else ""


def chunk_text(text: str) -> tuple[ExtractedChunk, ...]:
    if not text:
        return ()
    if CHUNK_OVERLAP_CHARACTERS >= MAX_CHUNK_CHARACTERS:
        raise RuntimeError("chunk overlap must be smaller than chunk maximum")

    chunks: list[ExtractedChunk] = []
    start = 0
    while start < len(text):
        maximum_end = min(start + MAX_CHUNK_CHARACTERS, len(text))
        end = maximum_end
        if maximum_end < len(text):
            search_start = start + (MAX_CHUNK_CHARACTERS // 2)
            window = text[search_start:maximum_end]
            for separator in ("\n\n", "\n", " "):
                boundary = window.rfind(separator)
                if boundary >= 0:
                    end = search_start + boundary + len(separator)
                    break
        chunk_value = text[start:end]
        if not chunk_value.strip():
            end = maximum_end
            chunk_value = text[start:end]
        chunks.append(
            ExtractedChunk(
                position=len(chunks),
                char_start=start,
                char_end=end,
                text=chunk_value,
                sha256=sha256(chunk_value.encode("utf-8")).hexdigest(),
            )
        )
        if end == len(text):
            break
        next_start = end - CHUNK_OVERLAP_CHARACTERS
        start = next_start if next_start > start else end
    return tuple(chunks)


def _extract_text(content_bytes: bytes, content_type: str) -> str:
    if content_type == "application/pdf":
        return _extract_pdf(content_bytes)

    decoded = _decode_utf8(content_bytes)
    if content_type == "text/plain":
        return decoded
    if content_type == "text/html":
        parser = _VisibleHtmlParser()
        try:
            parser.feed(decoded)
            parser.close()
        except Exception as error:
            raise SourceExtractionError("EXTRACTION_INVALID_DOCUMENT") from error
        return "".join(parser.parts)
    if content_type == "application/json":
        return _extract_json(decoded)
    if content_type in {"application/xml", "text/xml"}:
        return _extract_xml(decoded)
    raise SourceExtractionError("EXTRACTION_UNSUPPORTED_CONTENT_TYPE")


def _decode_utf8(content_bytes: bytes) -> str:
    try:
        return content_bytes.decode("utf-8-sig")
    except UnicodeDecodeError as error:
        raise SourceExtractionError("EXTRACTION_INVALID_ENCODING") from error


def _extract_json(decoded: str) -> str:
    try:
        parsed = json.loads(
            decoded,
            parse_constant=lambda value: (_raise_invalid_json(value)),
        )
    except (json.JSONDecodeError, ValueError) as error:
        raise SourceExtractionError("EXTRACTION_INVALID_DOCUMENT") from error

    values: list[str] = []

    def visit(value: object) -> None:
        if isinstance(value, dict):
            for child in value.values():
                visit(child)
        elif isinstance(value, list):
            for child in value:
                visit(child)
        elif value is None:
            values.append("null")
        elif value is True:
            values.append("true")
        elif value is False:
            values.append("false")
        elif isinstance(value, str):
            values.append(value)
        elif isinstance(value, (int, float)):
            values.append(json.dumps(value, ensure_ascii=False, allow_nan=False))

    visit(parsed)
    return "\n".join(values)


def _raise_invalid_json(value: str) -> object:
    raise ValueError(f"invalid JSON constant: {value}")


def _extract_xml(decoded: str) -> str:
    if re.search(r"<!\s*(?:DOCTYPE|ENTITY)\b", decoded, flags=re.IGNORECASE):
        raise SourceExtractionError("EXTRACTION_INVALID_DOCUMENT")
    try:
        root = ElementTree.fromstring(decoded)
    except ElementTree.ParseError as error:
        raise SourceExtractionError("EXTRACTION_INVALID_DOCUMENT") from error
    return "".join(root.itertext())


def _extract_pdf(content_bytes: bytes) -> str:
    try:
        reader = PdfReader(BytesIO(content_bytes), strict=True)
        if reader.is_encrypted:
            raise SourceExtractionError("EXTRACTION_ENCRYPTED_PDF")
        return "\n\n".join(page.extract_text() or "" for page in reader.pages)
    except SourceExtractionError:
        raise
    except Exception as error:
        raise SourceExtractionError("EXTRACTION_INVALID_DOCUMENT") from error
