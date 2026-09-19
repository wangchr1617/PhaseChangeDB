"""Crossref REST API 客户端。

面向学术文献 DOI 提供权威元数据检索服务，包括论文标题、收录期刊、出版年份、
第一作者与通讯作者、结构化摘要等。
严格遵循 Crossref 官方礼貌池（Polite Request Pool）规范。
"""

from __future__ import annotations

import logging
import re
from typing import Any

import httpx

from app.core.config import get_settings

logger = logging.getLogger(__name__)

# 用于剥离 JATS XML / HTML 标签的正则
HTML_TAG_REGEX = re.compile(r"<[^>]+>")
CLEAN_SPACE_REGEX = re.compile(r"\s+")


class CrossrefClient:
    """基于 httpx 的 Crossref REST API 异步客户端。"""

    BASE_URL = "https://api.crossref.org/works"

    def __init__(self, mailto: str | None = None, timeout: float = 8.0) -> None:
        self.settings = get_settings()
        self.mailto = mailto or self.settings.crossref_mailto
        self.timeout = timeout

    @property
    def headers(self) -> dict[str, str]:
        """按 Crossref 官方要求组装 Polite User-Agent 请求头。"""
        app_name = self.settings.app_name
        return {
            "User-Agent": f"{app_name}/1.0 (mailto:{self.mailto})",
            "Accept": "application/json",
        }

    @staticmethod
    def _strip_tags(text: str | None) -> str | None:
        """清除 XML/HTML 标签并规范化空白。"""
        if not text:
            return None
        cleaned = HTML_TAG_REGEX.sub(" ", text)
        cleaned = CLEAN_SPACE_REGEX.sub(" ", cleaned).strip()
        return cleaned or None

    @classmethod
    def parse_crossref_message(cls, message: dict[str, Any]) -> dict[str, Any]:
        """将 Crossref 返回的 message 原生字典解析映射为统一文献元数据字典。"""
        # 1. 论文标题
        title_list = message.get("title") or []
        title = title_list[0] if title_list else None
        if title:
            title = cls._strip_tags(title)

        # 2. 收录期刊 / 会议集
        container_list = message.get("container-title") or message.get("short-container-title") or []
        journal = container_list[0] if container_list else None
        if journal:
            journal = cls._strip_tags(journal)

        # 3. 出版年份
        publication_year: int | None = None
        date_sources = [
            message.get("published-print"),
            message.get("published-online"),
            message.get("issued"),
            message.get("created"),
        ]
        for src in date_sources:
            if src and isinstance(src, dict) and "date-parts" in src:
                date_parts = src["date-parts"]
                if date_parts and isinstance(date_parts, list) and date_parts[0]:
                    try:
                        publication_year = int(date_parts[0][0])
                        break
                    except (ValueError, TypeError, IndexError):
                        pass

        # 4. 作者解析
        raw_authors = message.get("author") or []
        formatted_authors: list[str] = []
        first_author: str | None = None
        corr_author: str | None = None

        if isinstance(raw_authors, list):
            for a in raw_authors:
                if not isinstance(a, dict):
                    continue
                given = a.get("given", "").strip()
                family = a.get("family", "").strip()
                name = f"{given} {family}".strip() or family or given
                if name:
                    formatted_authors.append(name)
                    if a.get("sequence") == "first" and not first_author:
                        first_author = name

            if formatted_authors:
                if not first_author:
                    first_author = formatted_authors[0]
                corr_author = formatted_authors[-1] if len(formatted_authors) > 1 else first_author

        # 5. 摘要
        raw_abstract = message.get("abstract")
        abstract = cls._strip_tags(raw_abstract)

        # 6. DOI 规范化
        doi = message.get("DOI") or message.get("doi")
        if doi:
            doi = doi.strip()

        return {
            "doi": doi,
            "title": title or "Untitled Document",
            "journal": journal,
            "publication_year": publication_year,
            "first_author": first_author,
            "corresponding_author": corr_author,
            "authors": formatted_authors,
            "abstract": abstract,
            "source": "crossref_polite_api",
        }

    async def lookup_doi(self, doi: str) -> dict[str, Any] | None:
        """异步查询指定 DOI 的权威文献元数据。若网络错误或未找到则安全返回 None。"""
        clean_doi = doi.strip()
        # 去除可能携带的 https://doi.org/ 前缀
        if clean_doi.startswith("http://"):
            clean_doi = clean_doi.removeprefix("http://").removeprefix("doi.org/").removeprefix("dx.doi.org/")
        elif clean_doi.startswith("https://"):
            clean_doi = clean_doi.removeprefix("https://").removeprefix("doi.org/").removeprefix("dx.doi.org/")

        url = f"{self.BASE_URL}/{clean_doi}"

        try:
            async with httpx.AsyncClient(headers=self.headers, timeout=self.timeout) as client:
                resp = await client.get(url)
                if resp.status_code == 404:
                    logger.info("Crossref 查询 DOI 未找到: %s", clean_doi)
                    return None
                resp.raise_for_status()
                data = resp.json()

            message = data.get("message")
            if not message or not isinstance(message, dict):
                return None

            parsed = self.parse_crossref_message(message)
            # 保证解析出的 doi 填充回 clean_doi
            if not parsed.get("doi"):
                parsed["doi"] = clean_doi
            return parsed

        except httpx.TimeoutException:
            logger.warning("Crossref 查询 DOI 超时 (%s 秒): %s", self.timeout, clean_doi)
            return None
        except httpx.HTTPStatusError as exc:
            logger.warning("Crossref 请求异常 [%s]: %s", exc.response.status_code, clean_doi)
            return None
        except Exception as exc:
            logger.error("Crossref 解析失败: %s - %s", clean_doi, str(exc))
            return None
