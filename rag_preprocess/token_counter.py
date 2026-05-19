from __future__ import annotations

import logging
import re
from typing import Any

from rag_preprocess.config import EMBEDDING_MODEL_NAME

logger = logging.getLogger(__name__)


class TokenCounter:
    def __init__(
        self,
        embedding_model: Any | None = None,
        model_name: str = EMBEDDING_MODEL_NAME,
    ) -> None:
        self.tokenizer = self._resolve_tokenizer(embedding_model, model_name)
        self.uses_transformer_tokenizer = self.tokenizer is not None

    def _resolve_tokenizer(self, embedding_model: Any | None, model_name: str) -> Any | None:
        tokenizer = getattr(embedding_model, "tokenizer", None)
        if tokenizer is not None:
            logger.info("Token sayımı BGEM3FlagModel tokenizer ile yapılacak.")
            return tokenizer

        nested_model = getattr(embedding_model, "model", None)
        tokenizer = getattr(nested_model, "tokenizer", None)
        if tokenizer is not None:
            logger.info("Token sayımı embedding modelinin tokenizer alanı ile yapılacak.")
            return tokenizer

        try:
            from transformers import AutoTokenizer  # type: ignore

            logger.info("Token sayımı AutoTokenizer ile yapılacak: %s", model_name)
            return AutoTokenizer.from_pretrained(model_name)
        except Exception as exc:  # pragma: no cover - only used in minimal envs
            logger.warning(
                "Tokenizer yüklenemedi, regex tabanlı yaklaşık token sayımı kullanılacak: %s",
                exc,
            )
            return None

    def count_tokens(self, text: str) -> int:
        if not text:
            return 0
        if self.tokenizer is None:
            return len(re.findall(r"\w+|[^\w\s]", text, flags=re.UNICODE))
        return len(self.tokenizer.encode(text, add_special_tokens=False))

    def head_text(self, text: str, max_tokens: int) -> str:
        if max_tokens <= 0 or not text:
            return ""
        if self.tokenizer is None:
            tokens = re.findall(r"\w+|[^\w\s]", text, flags=re.UNICODE)
            return " ".join(tokens[:max_tokens])
        token_ids = self.tokenizer.encode(text, add_special_tokens=False)
        return self.tokenizer.decode(token_ids[:max_tokens], skip_special_tokens=True)

    def tail_text(self, text: str, token_count: int) -> str:
        if token_count <= 0 or not text:
            return ""
        if self.tokenizer is None:
            tokens = re.findall(r"\w+|[^\w\s]", text, flags=re.UNICODE)
            return " ".join(tokens[-token_count:])
        token_ids = self.tokenizer.encode(text, add_special_tokens=False)
        return self.tokenizer.decode(token_ids[-token_count:], skip_special_tokens=True)

    def split_text_by_tokens(
        self,
        text: str,
        *,
        max_tokens: int,
        overlap_tokens: int = 0,
    ) -> list[str]:
        if max_tokens <= 0:
            return [text] if text else []
        if self.count_tokens(text) <= max_tokens:
            return [text]

        if self.tokenizer is None:
            rough_tokens = re.findall(r"\w+|[^\w\s]", text, flags=re.UNICODE)
            step = max(1, max_tokens - overlap_tokens)
            return [
                " ".join(rough_tokens[index : index + max_tokens]).strip()
                for index in range(0, len(rough_tokens), step)
            ]

        token_ids = self.tokenizer.encode(text, add_special_tokens=False)
        step = max(1, max_tokens - overlap_tokens)
        pieces: list[str] = []
        for index in range(0, len(token_ids), step):
            chunk_ids = token_ids[index : index + max_tokens]
            if not chunk_ids:
                continue
            pieces.append(self.tokenizer.decode(chunk_ids, skip_special_tokens=True).strip())
        return [piece for piece in pieces if piece]
