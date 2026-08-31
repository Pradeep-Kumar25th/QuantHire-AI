"""Ensure pronoun resolution uses the most recent tracked entity."""

from quantchat.core.query_normalizer import QueryNormalizer


def test_enhance_with_context_uses_most_recent_entity():
    normalizer = QueryNormalizer()
    enhanced = normalizer.enhance_with_context(
        "What are her skills?",
        tracked_entities=["Older Candidate", "Priya Singh"],
    )
    assert "Priya Singh's" in enhanced
