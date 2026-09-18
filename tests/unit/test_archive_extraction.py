import io
import tarfile
import zipfile

import pytest

from app.application.literature_parser import (
    extract_archive_papers,
    is_archive_filename,
)


def test_is_archive_filename():
    assert is_archive_filename("papers.zip") is True
    assert is_archive_filename("papers.tar.gz") is True
    assert is_archive_filename("papers.tgz") is True
    assert is_archive_filename("papers.tar") is True
    assert is_archive_filename("paper.pdf") is False
    assert is_archive_filename("paper.xml") is False


def test_extract_zip_archive_success():
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("paper1.pdf", b"%PDF-1.4 mock content 1")
        zf.writestr("nested/paper2.pdf", b"%PDF-1.4 mock content 2")
        zf.writestr("notes.txt", b"not a pdf")
        zf.writestr("__MACOSX/._paper1.pdf", b"resource fork")

    buf.seek(0)
    files = extract_archive_papers("test.zip", buf.getvalue())
    assert len(files) == 2
    names = [f[0] for f in files]
    assert "paper1.pdf" in names
    assert "paper2.pdf" in names


def test_extract_targz_archive_success():
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tf:
        data1 = b"%PDF-1.4 tar content 1"
        ti1 = tarfile.TarInfo("doc1.pdf")
        ti1.size = len(data1)
        tf.addfile(ti1, io.BytesIO(data1))

        data2 = b"readme text"
        ti2 = tarfile.TarInfo("readme.txt")
        ti2.size = len(data2)
        tf.addfile(ti2, io.BytesIO(data2))

    buf.seek(0)
    files = extract_archive_papers("test.tar.gz", buf.getvalue())
    assert len(files) == 1
    assert files[0][0] == "doc1.pdf"
    assert files[0][1] == b"%PDF-1.4 tar content 1"


def test_zip_slip_path_traversal_prevention():
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("../../evil.pdf", b"%PDF-1.4 evil")

    buf.seek(0)
    with pytest.raises(ValueError, match="检测到潜在路径穿越风险"):
        extract_archive_papers("slip.zip", buf.getvalue())


def test_archive_without_pdf_fails():
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("image.png", b"fake png")

    buf.seek(0)
    with pytest.raises(ValueError, match="未发现有效的 .pdf 文献文件"):
        extract_archive_papers("no_pdf.zip", buf.getvalue())
