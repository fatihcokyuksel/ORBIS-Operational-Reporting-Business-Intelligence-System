from __future__ import annotations

import argparse
from pathlib import Path

from dotenv import load_dotenv

from law_rag.config import get_rag_settings
from law_rag.migration import migrate_collection_metadata, restore_chroma_backup


def main() -> int:
    parser = argparse.ArgumentParser(description="Migrate Chroma metadata to the standard law format.")
    parser.add_argument("--restore-from-backup", type=str, default="", help="Restore DB from a previous backup path.")
    args = parser.parse_args()

    load_dotenv()
    settings = get_rag_settings()

    if args.restore_from_backup:
        restore_chroma_backup(settings, Path(args.restore_from_backup).resolve())
        print(f"Chroma backup restored: {args.restore_from_backup}")
        return 0

    summary = migrate_collection_metadata(settings)
    print(summary)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
