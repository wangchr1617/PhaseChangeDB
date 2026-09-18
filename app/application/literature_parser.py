"""PhaseChangeDB 文献解析工具函数。

支持对上传的 PDF、XML、JSON、BibTeX 及文本文件进行启发式元数据抽取，
生成用于批量上传前人工核验与修正的预览对象。
"""

from __future__ import annotations

import json
import re
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

from uuid6 import uuid7

from app.models.batch_upload import ParsedPaperPreview

DOI_REGEX = re.compile(r"\b10\.\d{4,9}/[-._;()/:A-Za-z0-9]+\b")
ARXIV_ID_REGEX = re.compile(r"\b(\d{4}\.\d{4,5}(?:v\d+)?)\b")


def _clean_text(s: str | None) -> str | None:
    if not s:
        return None
    cleaned = re.sub(r"\s+", " ", s).strip()
    return cleaned if cleaned else None


def _clean_filename_title(filename: str) -> str:
    p = Path(filename)
    stem = p.stem
    # 移除常见前缀如 arxiv_ 或类似标记
    stem = re.sub(r"^(?:arxiv[_-]?)?(\d{4}\.\d{4,5}(?:v\d+)?)[_-]?", "", stem, flags=re.IGNORECASE)
    stem = stem.replace("_", " ").replace("-", " ")
    stem = re.sub(r"\s+", " ", stem).strip()
    return stem if stem else p.stem


def _extract_from_pdf_bytes(data: bytes, filename: str) -> dict[str, Any]:
    """从 PDF 二进制流中抽取元数据、DOI 及文本线索。"""
    res: dict[str, Any] = {}

    # 1. 尝试搜索 XMP Metadata 包 (xml 格式)
    xmp_start = data.find(b"<x:xmpmeta")
    xmp_end = data.find(b"</x:xmpmeta>")
    if xmp_start != -1 and xmp_end != -1:
        xmp_chunk = data[xmp_start : xmp_end + len(b"</x:xmpmeta>")]
        try:
            xmp_str = xmp_chunk.decode("utf-8", errors="ignore")
            # 提取 dc:title
            m_title = re.search(r"<dc:title[^>]*>.*?<rdf:li[^>]*>(.*?)</rdf:li>", xmp_str, re.DOTALL | re.IGNORECASE)
            if m_title:
                res["title"] = _clean_text(m_title.group(1))

            # 提取 dc:creator
            m_creator_block = re.search(
                r"<dc:creator[^>]*>(.*?)</dc:creator>",
                xmp_str,
                re.DOTALL | re.IGNORECASE,
            )
            if m_creator_block:
                m_creators = re.findall(
                    r"<rdf:li[^>]*>(.*?)</rdf:li>",
                    m_creator_block.group(1),
                    re.DOTALL | re.IGNORECASE,
                )
                creators = [_clean_text(c) for c in m_creators if _clean_text(c)]
                if creators:
                    res["authors"] = creators
                    res["first_author"] = creators[0]
                    res["corresponding_author"] = creators[-1]



            # 提取 prism:doi
            m_doi = re.search(r"<prism:doi>(.*?)</prism:doi>", xmp_str, re.IGNORECASE)
            if m_doi:
                res["doi"] = _clean_text(m_doi.group(1))
        except Exception:
            pass

    # 2. 搜索标准 PDF Trailer 字典 /Info
    if not res.get("title"):
        m_pdf_title = re.search(rb"/Title\s*\(([^)]+)\)", data[:100000])
        if m_pdf_title:
            try:
                raw_t = m_pdf_title.group(1).decode("latin-1", errors="ignore")
                cleaned = _clean_text(raw_t)
                if cleaned and not cleaned.lower().endswith(".pdf") and len(cleaned) > 5:
                    res["title"] = cleaned
            except Exception:
                pass

    if not res.get("first_author"):
        m_pdf_author = re.search(rb"/Author\s*\(([^)]+)\)", data[:100000])
        if m_pdf_author:
            try:
                raw_a = m_pdf_author.group(1).decode("latin-1", errors="ignore")
                cleaned_a = _clean_text(raw_a)
                if cleaned_a:
                    res["first_author"] = cleaned_a
            except Exception:
                pass

    # 3. 搜索 DOI 模式
    if not res.get("doi"):
        # 扫描前 200KB 内容的文本匹配
        sample_text = data[:200000].decode("latin-1", errors="ignore")
        doi_match = DOI_REGEX.search(sample_text)
        if doi_match:
            doi_candidate = doi_match.group(0).rstrip(".)")
            if not doi_candidate.startswith("10.1000/"):  # 排除测试用假 DOI
                res["doi"] = doi_candidate

    # 4. 搜索 arXiv 编号
    m_arxiv = ARXIV_ID_REGEX.search(filename)
    if not m_arxiv:
        sample_text = data[:50000].decode("latin-1", errors="ignore")
        m_arxiv = re.search(r"arXiv:\s*(\d{4}\.\d{4,5})", sample_text, re.IGNORECASE)

    if m_arxiv and not res.get("doi"):
        res["doi"] = f"10.48550/arXiv.{m_arxiv.group(1)}"
        if not res.get("journal"):
            res["journal"] = "arXiv preprint"

    # 5. 回退生成标题
    if not res.get("title"):
        res["title"] = _clean_filename_title(filename)

    return res


def _extract_from_xml_bytes(data: bytes, filename: str) -> dict[str, Any]:
    """从 XML (如 arXiv Atom / PubMed / CrossRef) 中抽取元数据。"""
    try:
        root = ET.fromstring(data)
    except Exception as e:
        return {"title": _clean_filename_title(filename), "error": f"XML 解析失败: {e}"}

    # 检查是否为 Atom feed
    ns = {"atom": "http://www.w3.org/2005/Atom", "arxiv": "http://arxiv.org/schemas/atom"}
    entry_candidate = root.find("atom:entry", ns)
    entry = entry_candidate if entry_candidate is not None else root

    title_elem = entry.find("atom:title", ns)
    if title_elem is None:
        title_elem = entry.find(".//title")
    title = (
        _clean_text(title_elem.text)
        if title_elem is not None and title_elem.text
        else _clean_filename_title(filename)
    )

    summary_elem = entry.find("atom:summary", ns)
    if summary_elem is None:
        summary_elem = entry.find(".//abstract")
    abstract = _clean_text(summary_elem.text) if summary_elem is not None and summary_elem.text else None

    published_elem = entry.find("atom:published", ns)
    if published_elem is None:
        published_elem = entry.find(".//pub-date//year")
    if published_elem is None:
        published_elem = entry.find(".//year")
    year = None
    if published_elem is not None and published_elem.text:
        m_y = re.search(r"\b(19\d\d|20\d\d)\b", published_elem.text)
        if m_y:
            year = int(m_y.group(1))

    authors: list[str] = []
    author_elems = entry.findall("atom:author", ns)
    if not author_elems:
        author_elems = entry.findall(".//author")
    for a in author_elems:
        name_elem = a.find("atom:name", ns)
        if name_elem is None:
            name_elem = a.find(".//name")
        if name_elem is None:
            name_elem = a.find(".//surname")
        if name_elem is not None and name_elem.text:
            name_val = _clean_text(name_elem.text)
            if name_val:
                authors.append(name_val)

    first_author = authors[0] if authors else None
    corr_author = authors[-1] if len(authors) > 1 else first_author

    doi_elem = entry.find("arxiv:doi", ns)
    if doi_elem is None:
        doi_elem = entry.find(".//doi")
    doi = _clean_text(doi_elem.text) if doi_elem is not None and doi_elem.text else None


    # arXiv id
    if not doi:
        id_elem = entry.find("atom:id", ns)
        if id_elem is not None and id_elem.text:
            m = re.search(r"abs/([0-9]+\.[0-9]+(?:v[0-9]+)?)", id_elem.text)
            if m:
                doi = f"10.48550/arXiv.{m.group(1)}"

    journal = "arXiv preprint" if (doi and "arXiv" in doi) else None

    return {
        "title": title,
        "abstract": abstract,
        "publication_year": year,
        "first_author": first_author,
        "corresponding_author": corr_author,
        "doi": doi,
        "journal": journal,
    }


def _extract_from_json_bytes(data: bytes, filename: str) -> dict[str, Any]:
    """从 JSON 中抽取元数据。"""
    try:
        obj = json.loads(data.decode("utf-8", errors="ignore"))
    except Exception as e:
        return {"title": _clean_filename_title(filename), "error": f"JSON 解析失败: {e}"}

    if isinstance(obj, list) and obj:
        obj = obj[0]
    if not isinstance(obj, dict):
        return {"title": _clean_filename_title(filename)}

    title = _clean_text(obj.get("title")) or _clean_filename_title(filename)
    journal = _clean_text(obj.get("journal"))
    doi = _clean_text(obj.get("doi"))
    abstract = _clean_text(obj.get("abstract"))
    year = obj.get("publication_year") or obj.get("year")
    if year and isinstance(year, str):
        m_y = re.search(r"\b(19\d\d|20\d\d)\b", year)
        year = int(m_y.group(1)) if m_y else None

    authors = obj.get("authors") or []
    first_author = _clean_text(obj.get("first_author")) or (authors[0] if authors else None)
    corr_author = _clean_text(obj.get("corresponding_author")) or (authors[-1] if len(authors) > 1 else first_author)

    return {
        "title": title,
        "journal": journal,
        "doi": doi,
        "abstract": abstract,
        "publication_year": year,
        "first_author": first_author,
        "corresponding_author": corr_author,
    }


def _extract_from_bibtex_bytes(data: bytes, filename: str) -> dict[str, Any]:
    """从 BibTeX 文件抽取元数据。"""
    text_content = data.decode("utf-8", errors="ignore")

    def _get_field(field_name: str) -> str | None:
        pattern = rf"{field_name}\s*=\s*[\"{{]([^\"}}]+)[\"}},]"
        m = re.search(pattern, text_content, re.IGNORECASE)
        return _clean_text(m.group(1)) if m else None

    title = _get_field("title") or _clean_filename_title(filename)
    journal = _get_field("journal") or _get_field("booktitle")
    doi = _get_field("doi")
    year_str = _get_field("year")
    year = int(year_str) if year_str and year_str.isdigit() else None
    abstract = _get_field("abstract")

    author_str = _get_field("author")
    first_author = None
    corr_author = None
    if author_str:
        authors = [a.strip() for a in author_str.split(" and ") if a.strip()]
        if authors:
            first_author = authors[0]
            corr_author = authors[-1] if len(authors) > 1 else first_author

    return {
        "title": title,
        "journal": journal,
        "doi": doi,
        "abstract": abstract,
        "publication_year": year,
        "first_author": first_author,
        "corresponding_author": corr_author,
    }


def parse_uploaded_paper(filename: str, content: bytes) -> ParsedPaperPreview:
    """对单个上传的文献文件进行智能启发式解析并返回预览模型。"""
    file_id = str(uuid7())
    file_size = len(content)

    if not content or file_size == 0:
        return ParsedPaperPreview(
            file_id=file_id,
            filename=filename,
            file_size=0,
            title=_clean_filename_title(filename),
            status="failed",
            error_message="上传的文件内容为空 (0 字节)",
        )

    fn_lower = filename.lower()
    res: dict[str, Any]

    try:
        if fn_lower.endswith(".xml"):
            res = _extract_from_xml_bytes(content, filename)
        elif fn_lower.endswith(".json"):
            res = _extract_from_json_bytes(content, filename)
        elif fn_lower.endswith(".bib"):
            res = _extract_from_bibtex_bytes(content, filename)
        elif fn_lower.endswith(".pdf"):
            res = _extract_from_pdf_bytes(content, filename)
        else:
            # 文本或其他文件
            text_str = content.decode("utf-8", errors="ignore")
            lines = [line.strip() for line in text_str.splitlines() if line.strip()]
            title = lines[0] if lines else _clean_filename_title(filename)
            doi_m = DOI_REGEX.search(text_str)
            res = {
                "title": title,
                "doi": doi_m.group(0) if doi_m else None,
            }
    except Exception as e:
        return ParsedPaperPreview(
            file_id=file_id,
            filename=filename,
            file_size=file_size,
            title=_clean_filename_title(filename),
            status="failed",
            error_message=f"解析过程发生异常: {str(e)}",
        )

    err = res.get("error")
    status = "failed" if err else "parsed"

    return ParsedPaperPreview(
        file_id=file_id,
        filename=filename,
        file_size=file_size,
        title=res.get("title") or _clean_filename_title(filename),
        journal=res.get("journal"),
        publication_year=res.get("publication_year"),
        first_author=res.get("first_author"),
        corresponding_author=res.get("corresponding_author"),
        doi=res.get("doi"),
        abstract=res.get("abstract"),
        status=status,
        error_message=err,
    )
