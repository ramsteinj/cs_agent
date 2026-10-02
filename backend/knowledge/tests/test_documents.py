import zipfile
from io import BytesIO

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile

from common.exceptions import ApiError
from knowledge import documents
from knowledge.documents import clean_file_name, extract_text

from .files import make_docx, make_encrypted_pdf, make_pdf


def _extract(name, data):
    return extract_text(SimpleUploadedFile(name, data))


def _error(name, data):
    with pytest.raises(ApiError) as excinfo:
        _extract(name, data)
    return excinfo.value.error_code, excinfo.value.status_code


class TestText:
    def test_utf8_with_bom(self):
        name, kind, size, text = _extract(
            "가격표.txt", "\ufeff가격: 월 5,000원\r\n\r\n\r\n끝".encode()
        )

        assert (name, kind) == ("가격표.txt", "txt")
        assert size > 0
        assert text == "가격: 월 5,000원\n\n끝"

    def test_cp949_fallback(self):
        assert _extract("a.txt", "한글 안내".encode("cp949"))[3] == "한글 안내"

    def test_binary_rejected(self):
        assert _error("a.txt", b"abc\x00def") == ("UNSUPPORTED_FILE", 400)

    def test_empty_rejected(self):
        assert _error("a.txt", b"   \n  ") == ("DOCUMENT_PARSE_ERROR", 400)


class TestDocx:
    def test_paragraphs_and_tables_in_order(self):
        data = make_docx(
            ["제품 소개 문단", "두 번째 문단"],
            table=[["요금제", "가격"], ["기본", "월 5,000원"]],
        )

        text = _extract("소개.docx", data)[3]

        assert text == "제품 소개 문단\n\n두 번째 문단\n\n요금제 | 가격\n기본 | 월 5,000원"

    def test_not_a_zip(self):
        assert _error("a.docx", b"plain text") == ("UNSUPPORTED_FILE", 400)

    def test_zip_without_document_xml(self):
        buffer = BytesIO()
        with zipfile.ZipFile(buffer, "w") as archive:
            archive.writestr("hello.txt", "x")
        assert _error("a.docx", buffer.getvalue()) == ("UNSUPPORTED_FILE", 400)

    def test_corrupt_docx(self):
        buffer = BytesIO()
        with zipfile.ZipFile(buffer, "w") as archive:
            archive.writestr("word/document.xml", "<not-xml")
        assert _error("a.docx", buffer.getvalue()) == ("DOCUMENT_PARSE_ERROR", 400)

    def test_zip_bomb_guard(self, monkeypatch):
        monkeypatch.setattr(documents, "MAX_DOCX_UNCOMPRESSED_BYTES", 100)
        assert _error("a.docx", make_docx(["x" * 500])) == ("FILE_TOO_LARGE", 413)


class TestPdf:
    def test_text_pdf(self):
        name, kind, _, text = _extract("spec.pdf", make_pdf("OK Drive costs 5000 KRW per month"))

        assert (name, kind) == ("spec.pdf", "pdf")
        assert "OK Drive costs 5000 KRW per month" in text

    def test_scanned_or_blank_pdf_has_no_text(self):
        assert _error("scan.pdf", make_pdf()) == ("DOCUMENT_PARSE_ERROR", 400)

    def test_encrypted_pdf(self):
        assert _error("locked.pdf", make_encrypted_pdf()) == ("UNSUPPORTED_FILE", 400)

    def test_wrong_signature(self):
        assert _error("fake.pdf", b"not a pdf") == ("UNSUPPORTED_FILE", 400)

    def test_page_limit(self, monkeypatch):
        monkeypatch.setattr(documents, "MAX_PDF_PAGES", 0)
        assert _error("a.pdf", make_pdf("hello")) == ("FILE_TOO_LARGE", 413)


class TestCommon:
    @pytest.mark.parametrize("name", ["old.doc", "image.png", "noext", "a.exe"])
    def test_unsupported_types(self, name):
        assert _error(name, b"data") == ("UNSUPPORTED_FILE", 400)

    def test_old_word_message(self):
        with pytest.raises(ApiError) as excinfo:
            _extract("old.doc", b"data")
        assert ".docx로 저장" in str(excinfo.value.detail)

    def test_file_size_limit(self, monkeypatch):
        monkeypatch.setattr(documents, "MAX_FILE_BYTES", 10)
        assert _error("a.txt", b"x" * 11) == ("FILE_TOO_LARGE", 413)

    def test_text_length_limit(self, monkeypatch):
        monkeypatch.setattr(documents, "MAX_TEXT_CHARS", 5)
        assert _error("a.txt", b"123456") == ("FILE_TOO_LARGE", 413)

    def test_uppercase_extension(self):
        assert _extract("README.TXT", b"hello")[1] == "txt"

    @pytest.mark.parametrize(
        ("raw", "clean"),
        [
            ("../../etc/passwd.txt", "passwd.txt"),
            ("C:\\Users\\me\\가격.pdf", "가격.pdf"),
            ("", "document"),
        ],
    )
    def test_clean_file_name(self, raw, clean):
        assert clean_file_name(raw) == clean


def test_one_million_characters_are_accepted():
    text = ("가" * 99 + "\n") * 10_000  # exactly 1,000,000 characters

    assert len(_extract("big.txt", text.encode())[3]) == 1_000_000 - 1  # trailing newline trimmed


def test_more_than_one_million_characters_are_rejected():
    assert _error("big.txt", ("가" * 1_000_001).encode()) == ("FILE_TOO_LARGE", 413)


def test_pdf_page_limit_is_2000():
    assert documents.MAX_PDF_PAGES == 2000
