"""测试文献智能解析工具函数。"""

from __future__ import annotations

import json

from app.application.literature_parser import parse_uploaded_paper


def test_parse_empty_file():
    preview = parse_uploaded_paper("empty.pdf", b"")
    assert preview.status == "failed"
    assert "为空" in (preview.error_message or "")


def test_parse_json_paper():
    data = {
        "title": "Phase change memory using Ge2Sb2Te5",
        "doi": "10.1038/nmat2009",
        "journal": "Nature Materials",
        "publication_year": 2021,
        "first_author": "Matthias Wuttig",
        "corresponding_author": "Noboru Yamada",
        "abstract": "A review of phase change materials for rewriteable data storage.",
    }
    raw_bytes = json.dumps(data).encode("utf-8")
    preview = parse_uploaded_paper("paper_test.json", raw_bytes)

    assert preview.status == "parsed"
    assert preview.title == "Phase change memory using Ge2Sb2Te5"
    assert preview.doi == "10.1038/nmat2009"
    assert preview.journal == "Nature Materials"
    assert preview.publication_year == 2021
    assert preview.first_author == "Matthias Wuttig"
    assert preview.corresponding_author == "Noboru Yamada"
    assert preview.abstract == "A review of phase change materials for rewriteable data storage."


def test_parse_bibtex_paper():
    bibtex = """
    @article{wuttig2007phase,
      title={Phase-change materials for rewriteable data storage},
      author={Wuttig, Matthias and Yamada, Noboru},
      journal={Nature materials},
      volume={6},
      number={11},
      pages={824--832},
      year={2007},
      publisher={Nature Publishing Group},
      doi={10.1038/nmat2009}
    }
    """
    preview = parse_uploaded_paper("wuttig2007.bib", bibtex.encode("utf-8"))
    assert preview.status == "parsed"
    assert preview.title == "Phase-change materials for rewriteable data storage"
    assert preview.doi == "10.1038/nmat2009"
    assert preview.journal == "Nature materials"
    assert preview.publication_year == 2007
    assert preview.first_author == "Wuttig, Matthias"
    assert preview.corresponding_author == "Yamada, Noboru"


def test_parse_xml_atom_feed():
    xml = """<?xml version="1.0" encoding="UTF-8"?>
    <feed xmlns="http://www.w3.org/2005/Atom" xmlns:arxiv="http://arxiv.org/schemas/atom">
      <entry>
        <id>http://arxiv.org/abs/2001.08100v1</id>
        <title>Structural relaxation and crystallization in Ge-Sb-Te</title>
        <summary>Detailed study on crystallization kinetics.</summary>
        <published>2020-01-22T14:32:00Z</published>
        <author>
          <name>Alice Wang</name>
        </author>
        <author>
          <name>Bob Zhang</name>
        </author>
        <arxiv:doi>10.1063/1.5144883</arxiv:doi>
      </entry>
    </feed>
    """
    preview = parse_uploaded_paper("arxiv_feed.xml", xml.encode("utf-8"))
    assert preview.status == "parsed"
    assert preview.title == "Structural relaxation and crystallization in Ge-Sb-Te"
    assert preview.doi == "10.1063/1.5144883"
    assert preview.first_author == "Alice Wang"
    assert preview.corresponding_author == "Bob Zhang"
    assert preview.publication_year == 2020


def test_parse_pdf_fallback_and_xmp():
    # 模拟包含 XMP 信息的 PDF 二进制片段
    xmp = (
        b"%PDF-1.5\n"
        b"<x:xmpmeta xmlns:x='adobe:ns:meta/'>"
        b"<dc:title><rdf:Alt><rdf:li>Crystallization of Sc0.2Sb2Te3 Phase Change Films</rdf:li></rdf:Alt></dc:title>"
        b"<dc:creator><rdf:Seq><rdf:li>John Doe</rdf:li><rdf:li>Jane Smith</rdf:li></rdf:Seq></dc:creator>"
        b"<prism:doi>10.1126/science.123456</prism:doi>"
        b"</x:xmpmeta>\n"
        b"%%EOF"
    )
    preview = parse_uploaded_paper("Sc_Sb_Te_2024.pdf", xmp)
    assert preview.status == "parsed"
    assert preview.title == "Crystallization of Sc0.2Sb2Te3 Phase Change Films"
    assert preview.doi == "10.1126/science.123456"
    assert preview.first_author == "John Doe"
    assert preview.corresponding_author == "Jane Smith"
