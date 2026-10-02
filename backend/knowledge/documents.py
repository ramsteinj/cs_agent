"""Text extraction for product documents: .txt, MS Word .docx, PDF (specs/05 §2.1.1).

Only the extracted text is kept; the uploaded file itself is never stored.
"""

import io
import re
import zipfile

import docx
import pypdf
from docx.table import Table
from rest_framework import status

from common.exceptions import ApiError

MAX_FILE_BYTES = 10 * 1024 * 1024
MAX_TEXT_CHARS = 1_000_000  # ~2,300 chunks, ~40s to embed on CPU
MAX_DOCX_UNCOMPRESSED_BYTES = 50 * 1024 * 1024  # zip-bomb guard
MAX_PDF_PAGES = 2000
ALLOWED_TYPES = ("txt", "docx", "pdf")


def _unsupported(message):
    return ApiError("UNSUPPORTED_FILE", message, status.HTTP_400_BAD_REQUEST)


def _parse_error(
    message="파일에서 텍스트를 추출할 수 없습니다. 파일이 손상되지 않았는지 확인해 주세요.",
):
    return ApiError("DOCUMENT_PARSE_ERROR", message, status.HTTP_400_BAD_REQUEST)


def _too_large(message):
    return ApiError("FILE_TOO_LARGE", message, status.HTTP_413_REQUEST_ENTITY_TOO_LARGE)


def clean_file_name(name):
    """Drop any client-supplied path (both / and \\ separators)."""
    return (name or "").replace("\\", "/").rsplit("/", 1)[-1].strip()[:255] or "document"


def _normalize(text):
    lines = [line.rstrip() for line in text.replace("\r\n", "\n").replace("\r", "\n").split("\n")]
    return re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip()


def _txt(data):
    if b"\x00" in data:
        raise _unsupported("텍스트 파일이 아닙니다.")
    for encoding in ("utf-8-sig", "cp949"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise _parse_error("텍스트 인코딩을 알 수 없습니다. UTF-8로 저장해 업로드해 주세요.")


def _table_text(table):
    rows = []
    for row in table.rows:
        cells = []
        for cell in row.cells:
            value = cell.text.strip()
            if not cells or cells[-1] != value:  # merged cells repeat their text
                cells.append(value)
        if any(cells):
            rows.append(" | ".join(cells))
    return "\n".join(rows)


def _docx(data):
    if not data.startswith(b"PK\x03\x04"):
        raise _unsupported("올바른 Word(.docx) 파일이 아닙니다.")
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            if "word/document.xml" not in archive.namelist():
                raise _unsupported("올바른 Word(.docx) 파일이 아닙니다.")
            if sum(info.file_size for info in archive.infolist()) > MAX_DOCX_UNCOMPRESSED_BYTES:
                raise _too_large("Word 파일의 압축을 푼 크기가 너무 큽니다.")
        document = docx.Document(io.BytesIO(data))
    except ApiError:
        raise
    except Exception:  # zipfile / lxml / python-docx errors on corrupt files
        raise _parse_error() from None
    blocks = []
    for block in document.iter_inner_content():  # paragraphs and tables in document order
        text = _table_text(block) if isinstance(block, Table) else block.text
        if text.strip():
            blocks.append(text)
    return "\n\n".join(blocks)


def _pdf(data):
    if not data.startswith(b"%PDF-"):
        raise _unsupported("올바른 PDF 파일이 아닙니다.")
    try:
        reader = pypdf.PdfReader(io.BytesIO(data))
        if reader.is_encrypted:
            raise _unsupported(
                "암호가 걸린 PDF는 지원하지 않습니다. 암호를 해제해 업로드해 주세요."
            )
        if len(reader.pages) > MAX_PDF_PAGES:
            raise _too_large(f"PDF는 {MAX_PDF_PAGES}쪽까지 지원합니다.")
        return "\n\n".join(page.extract_text() or "" for page in reader.pages)
    except ApiError:
        raise
    except Exception:  # pypdf.errors.PyPdfError and lower-level parse errors
        raise _parse_error() from None


_EXTRACTORS = {"txt": _txt, "docx": _docx, "pdf": _pdf}


def extract_text(uploaded_file):
    """Return (file_name, file_type, file_size, text) or raise ApiError."""
    name = clean_file_name(uploaded_file.name)
    extension = name.rsplit(".", 1)[-1].lower() if "." in name else ""
    if extension == "doc":
        raise _unsupported("구형 Word(.doc)는 지원하지 않습니다. .docx로 저장해 업로드해 주세요.")
    if extension not in ALLOWED_TYPES:
        raise _unsupported("Text(.txt), MS Word(.docx), PDF(.pdf) 파일만 업로드할 수 있습니다.")
    if uploaded_file.size > MAX_FILE_BYTES:
        raise _too_large("파일은 10MB 이하만 업로드할 수 있습니다.")

    data = uploaded_file.read()
    text = _normalize(_EXTRACTORS[extension](data))
    if not text:
        raise _parse_error(
            "파일에서 텍스트를 찾을 수 없습니다. (스캔한 이미지 PDF는 지원하지 않습니다)"
        )
    if len(text) > MAX_TEXT_CHARS:
        raise _too_large(f"추출한 텍스트가 너무 깁니다. (최대 {MAX_TEXT_CHARS:,}자)")
    return name, extension, len(data), text
