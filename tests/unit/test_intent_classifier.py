"""Ensure QuantChat intent classifier loads (Python 3.11+ f-string rules)."""


def test_intent_classifier_imports():
    from apps.quantchat.core.intent_classifier import IntentClassifier, Intent

    assert IntentClassifier is not None
    assert Intent.RAG_QA.value == "RAG_QA"
