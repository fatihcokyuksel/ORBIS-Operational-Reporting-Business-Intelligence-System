from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(slots=True)
class PageLine:
    page: int
    line_no: int
    text: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class PageText:
    page: int
    text: str
    lines: list[PageLine]

    def to_dict(self) -> dict[str, Any]:
        return {
            "page": self.page,
            "text": self.text,
            "lines": [line.to_dict() for line in self.lines],
        }


@dataclass(slots=True)
class LawMetadata:
    document_id: str
    document_type: str
    law_no: str | None
    law_name: str
    official_name: str
    source_file: str
    source_url: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class Article:
    document_id: str
    document_type: str
    law_no: str | None
    law_name: str
    official_name: str
    article_no: str
    article_prefix: str
    article_title: str | None
    chapter_name: str | None
    section_name: str | None
    page_start: int
    page_end: int
    source_file: str
    source_url: str | None
    text: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class Chunk:
    id: str
    text: str
    metadata: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "text": self.text,
            "metadata": self.metadata,
        }
