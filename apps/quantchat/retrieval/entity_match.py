"""Shared entity-name scoring for Milvus and pgvector full-document retrieval."""

from __future__ import annotations


def name_match_score(target_name: str, stored_name: str) -> float:
    """Score how well *stored_name* matches *target_name* (higher is better)."""
    target_name = (target_name or "").lower().strip()
    stored_name = (stored_name or "").lower().strip()
    if not target_name or not stored_name:
        return 0.0

    target_normalized = target_name.replace("/", " ").replace("-", " ")
    stored_normalized = stored_name.replace("/", " ").replace("-", " ")
    target_words = {w for w in target_normalized.split() if w}
    stored_words = {w for w in stored_normalized.split() if w}

    if stored_name == target_name or stored_normalized == target_normalized:
        return 100.0

    matching_words = len(target_words.intersection(stored_words))
    if target_words and target_words.issubset(stored_words):
        return 90.0 + matching_words

    if matching_words > 0 and target_words:
        match_ratio = matching_words / len(target_words)
        return 50.0 + (match_ratio * 30.0)

    return 0.0
