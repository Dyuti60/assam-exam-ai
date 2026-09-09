from dataclasses import dataclass
from textwrap import wrap

PDF_RENDERER_VERSION = "deterministic-pdf-v1"

_PAGE_WIDTH = 595
_PAGE_HEIGHT = 842
_MARGIN_X = 54
_TOP_Y = 788
_BOTTOM_Y = 54


class UnsupportedPdfCharacterError(ValueError):
    """Raised when the deterministic built-in font cannot represent input."""


@dataclass(frozen=True)
class _RenderedLine:
    text: str
    font: str
    size: int
    line_height: int
    gap_before: int = 0


def render_content_document_pdf(title: str, markdown: str) -> bytes:
    """Render stable A4 PDF bytes from one exact stored document payload."""

    _validate_supported_text(title, markdown)
    lines = _layout_markdown(title, markdown)
    page_streams = _paginate(lines)
    return _build_pdf(page_streams)


def _validate_supported_text(title: str, markdown: str) -> None:
    if any(
        ord(character) < 32 and character not in "\t\r\n"
        for character in title + markdown
    ):
        raise UnsupportedPdfCharacterError(
            "deterministic-pdf-v1 does not support control characters"
        )
    try:
        title.encode("cp1252")
        markdown.encode("cp1252")
    except UnicodeEncodeError as error:
        raise UnsupportedPdfCharacterError(
            "deterministic-pdf-v1 supports only Windows-1252 characters"
        ) from error


def _layout_markdown(title: str, markdown: str) -> list[_RenderedLine]:
    rendered = _wrapped_lines(title, "F2", 18, 22, 54)
    markdown_lines = markdown.expandtabs(4).splitlines()
    if markdown_lines and markdown_lines[0].strip() == f"# {title}":
        markdown_lines = markdown_lines[1:]

    pending_blank = False
    for raw_line in markdown_lines:
        stripped = raw_line.strip()
        if not stripped:
            pending_blank = True
            continue

        gap = 9 if pending_blank else 0
        pending_blank = False
        if stripped.startswith("### "):
            rendered.extend(
                _wrapped_lines(stripped[4:], "F2", 12, 16, 76, gap)
            )
        elif stripped.startswith("## "):
            rendered.extend(
                _wrapped_lines(stripped[3:], "F2", 14, 18, 68, gap)
            )
        elif stripped.startswith("# "):
            rendered.extend(
                _wrapped_lines(stripped[2:], "F2", 16, 20, 60, gap)
            )
        elif stripped.startswith(("- ", "* ")):
            rendered.extend(
                _wrapped_lines(f"- {stripped[2:]}", "F1", 10, 14, 86, gap)
            )
        else:
            rendered.extend(_wrapped_lines(stripped, "F1", 10, 14, 90, gap))
    return rendered


def _wrapped_lines(
    text: str,
    font: str,
    size: int,
    line_height: int,
    width: int,
    gap_before: int = 0,
) -> list[_RenderedLine]:
    parts = wrap(
        text.replace("**", ""),
        width=width,
        replace_whitespace=False,
        drop_whitespace=True,
        break_long_words=True,
        break_on_hyphens=False,
    ) or [""]
    return [
        _RenderedLine(
            text=part,
            font=font,
            size=size,
            line_height=line_height,
            gap_before=gap_before if index == 0 else 0,
        )
        for index, part in enumerate(parts)
    ]


def _paginate(lines: list[_RenderedLine]) -> list[bytes]:
    pages: list[list[bytes]] = [[]]
    y = _TOP_Y
    for line in lines:
        required = line.gap_before + line.line_height
        if y - required < _BOTTOM_Y and pages[-1]:
            pages.append([])
            y = _TOP_Y
        y -= line.gap_before
        pages[-1].append(
            b"BT /"
            + line.font.encode("ascii")
            + f" {line.size} Tf 1 0 0 1 {_MARGIN_X} {y} Tm ".encode("ascii")
            + _pdf_literal(line.text)
            + b" Tj ET\n"
        )
        y -= line.line_height
    return [b"".join(page) for page in pages]


def _pdf_literal(text: str) -> bytes:
    encoded = text.encode("cp1252")
    escaped = encoded.replace(b"\\", b"\\\\")
    escaped = escaped.replace(b"(", b"\\(").replace(b")", b"\\)")
    return b"(" + escaped + b")"


def _build_pdf(page_streams: list[bytes]) -> bytes:
    page_count = len(page_streams)
    page_object_ids = [5 + index * 2 for index in range(page_count)]
    objects: dict[int, bytes] = {
        1: b"<< /Type /Catalog /Pages 2 0 R >>",
        2: (
            b"<< /Type /Pages /Count "
            + str(page_count).encode("ascii")
            + b" /Kids ["
            + b" ".join(f"{object_id} 0 R".encode("ascii") for object_id in page_object_ids)
            + b"] >>"
        ),
        3: b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>",
        4: b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold /Encoding /WinAnsiEncoding >>",
    }
    for index, stream in enumerate(page_streams):
        page_id = page_object_ids[index]
        content_id = page_id + 1
        objects[page_id] = (
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {_PAGE_WIDTH} {_PAGE_HEIGHT}] ".encode(
                "ascii"
            )
            + b"/Resources << /Font << /F1 3 0 R /F2 4 0 R >> >> "
            + f"/Contents {content_id} 0 R >>".encode("ascii")
        )
        objects[content_id] = (
            f"<< /Length {len(stream)} >>\nstream\n".encode("ascii")
            + stream
            + b"endstream"
        )

    info_id = 5 + page_count * 2
    objects[info_id] = (
        b"<< /Creator (Assam Exam AI deterministic-pdf-v1) "
        b"/Producer (Assam Exam AI deterministic-pdf-v1) "
        b"/CreationDate (D:20000101000000Z) /ModDate (D:20000101000000Z) >>"
    )
    header = b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n"
    body = bytearray(header)
    offsets = [0]
    for object_id in range(1, info_id + 1):
        offsets.append(len(body))
        body.extend(f"{object_id} 0 obj\n".encode("ascii"))
        body.extend(objects[object_id])
        body.extend(b"\nendobj\n")

    xref_offset = len(body)
    body.extend(f"xref\n0 {info_id + 1}\n".encode("ascii"))
    body.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        body.extend(f"{offset:010d} 00000 n \n".encode("ascii"))
    body.extend(
        f"trailer\n<< /Size {info_id + 1} /Root 1 0 R /Info {info_id} 0 R >>\n".encode(
            "ascii"
        )
    )
    body.extend(f"startxref\n{xref_offset}\n%%EOF\n".encode("ascii"))
    return bytes(body)
