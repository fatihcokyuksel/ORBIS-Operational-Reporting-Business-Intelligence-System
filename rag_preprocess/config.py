from __future__ import annotations

from pathlib import Path

from law_rag.config import get_rag_settings


TARGET_CHUNK_TOKENS = 1024
_RAG_SETTINGS = get_rag_settings(Path(__file__).resolve().parents[1])
MAX_MODEL_TOKENS = _RAG_SETTINGS.max_model_tokens
SPLIT_OVERLAP_TOKENS = 200
FALLBACK_OVERLAP_TOKENS = 150

EMBEDDING_MODEL_NAME = _RAG_SETTINGS.embedding_model_name
EMBEDDING_BATCH_SIZE = _RAG_SETTINGS.embedding_batch_size
CHROMA_ADD_BATCH_SIZE = _RAG_SETTINGS.chroma_add_batch_size
COLLECTION_NAME = _RAG_SETTINGS.chroma_collection_name

MIN_ARTICLES_FOR_ARTICLE_AWARE = 2

OUTPUT_DIR_NAME = "output"
CHROMA_DIR_NAME = "chroma_db"
PARSED_JSON_DIR_NAME = "parsed_json"
CHUNKS_JSONL_DIR_NAME = "chunks_jsonl"
QUALITY_REPORTS_DIR_NAME = "quality_reports"
LOGS_DIR_NAME = "logs"

ARTICLE_PATTERN = r"""(?imx)
^
\s*
(?P<prefix>
    (?:Mükerrer\s+Madde)|
    (?:Geçici\s+Madde)|
    (?:Ek\s+Madde)|
    (?:GEÇİCİ\s+MADDE)|
    (?:MÜKERRER\s+MADDE)|
    (?:EK\s+MADDE)|
    (?:MADDE)|
    (?:Madde)
)
\s+
(?P<article_no>\d+[\/A-ZÇĞİÖŞÜa-zçğıöşü]*)
\s*
[-–—:]?
"""

CHAPTER_PATTERN = r"""(?imx)
^
\s*
(?P<chapter>
    (?:BİRİNCİ|İKİNCİ|ÜÇÜNCÜ|DÖRDÜNCÜ|BEŞİNCİ|ALTINCI|YEDİNCİ|SEKİZİNCİ|DOKUZUNCU|ONUNCU)
    \s+
    KISIM
)
\s*$
"""

SECTION_PATTERN = r"""(?imx)
^
\s*
(?P<section>
    (?:BİRİNCİ|İKİNCİ|ÜÇÜNCÜ|DÖRDÜNCÜ|BEŞİNCİ|ALTINCI|YEDİNCİ|SEKİZİNCİ|DOKUZUNCU|ONUNCU)
    \s+
    BÖLÜM
)
\s*$
"""

LAW_NO_PATTERN = r"(?im)Kanun\s+Numarası\s*:\s*(?P<law_no>\d+)"

INTRO_PATTERN = r"(?im)^\s*(?P<intro>BAŞLANGIÇ|GİRİŞ)\s*$"

PARAGRAPH_MARKER_PATTERN = r"(?m)^\s*(?:\(\d+\)|\d+\.)\s+"

FILENAME_LAW_NAME_MAPPING = {
    "193": "Gelir Vergisi Kanunu",
    "213": "Vergi Usul Kanunu",
    "3065": "Katma Değer Vergisi Kanunu",
    "5237": "Türk Ceza Kanunu",
    "5510": "Sosyal Sigortalar ve Genel Sağlık Sigortası Kanunu",
    "6102": "Türk Ticaret Kanunu",
}

KNOWN_LAW_TITLES = [
    "GELİR VERGİSİ KANUNU",
    "VERGİ USUL KANUNU",
    "KATMA DEĞER VERGİSİ KANUNU",
    "TÜRK TİCARET KANUNU",
    "SOSYAL SİGORTALAR VE GENEL SAĞLIK SİGORTASI KANUNU",
    "TÜRK CEZA KANUNU",
]


def build_output_paths(selected_dir: Path) -> dict[str, Path]:
    output_dir = selected_dir / OUTPUT_DIR_NAME
    return {
        "output": output_dir,
        "chroma": _RAG_SETTINGS.chroma_db_path,
        "parsed_json": output_dir / PARSED_JSON_DIR_NAME,
        "chunks_jsonl": output_dir / CHUNKS_JSONL_DIR_NAME,
        "quality_reports": output_dir / QUALITY_REPORTS_DIR_NAME,
        "logs": output_dir / LOGS_DIR_NAME,
    }
