from __future__ import annotations

import re
from dataclasses import dataclass

from law_rag.metadata import normalize_law_name


ARTICLE_QUERY_PATTERNS = [
    re.compile(
        r"(?i)\b(?P<law_no>\d{3,5})\s+sayili\s+kanunun\s+(?P<article>\d+[\/A-Za-zÇĞİÖŞÜçğıöşü]*)\.?\s*maddesi\b"
    ),
    re.compile(
        r"(?i)\b(?P<law>[A-Za-zÇĞİÖŞÜçğıöşü0-9 ]+?)\s+(?P<article>\d+[\/A-Za-zÇĞİÖŞÜçğıöşü]*)\.?\s*madde(?:si|yi)?\b"
    ),
    re.compile(
        r"(?i)\b(?P<law>[A-Za-zÇĞİÖŞÜçğıöşü0-9 ]+?)\s+madde\s+(?P<article>\d+[\/A-Za-zÇĞİÖŞÜçğıöşü]*)\b"
    ),
]


@dataclass(slots=True)
class LawArticleQuery:
    raw_law_name: str
    normalized_law_name: str
    law_no: str
    article_no: str


def parse_law_article_query(question: str, aliases: dict[str, str]) -> LawArticleQuery | None:
    compact_question = " ".join(question.replace("’", "'").replace("'", " ").split())
    for pattern in ARTICLE_QUERY_PATTERNS:
        match = pattern.search(compact_question)
        if not match:
            continue

        law_no = str(match.groupdict().get("law_no") or "").strip()
        raw_law_name = " ".join(str(match.groupdict().get("law") or law_no).split())
        article_no = match.group("article").strip()
        if not law_no:
            law_no_match = re.search(r"\b(\d{3,5})\b", raw_law_name)
            law_no = law_no_match.group(1) if law_no_match else ""

        return LawArticleQuery(
            raw_law_name=raw_law_name,
            normalized_law_name=normalize_law_name(raw_law_name, aliases),
            law_no=law_no,
            article_no=article_no,
        )
    return None
