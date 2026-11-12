import builtins
import logging

import pytest

from o2c.retrieval import EvidenceRetriever


def test_retrieval_rejects_unknown_mode():
    with pytest.raises(ValueError, match="retrieval mode"):
        EvidenceRetriever(["an evidence chunk"], mode="unknown")


def test_semantic_initialization_failure_is_reported(monkeypatch, caplog):
    original_import = builtins.__import__

    def fail_sentence_transformers(name, *args, **kwargs):
        if name == "sentence_transformers":
            raise ImportError("model dependency unavailable")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fail_sentence_transformers)

    with caplog.at_level(logging.WARNING, logger="o2c.retrieval"):
        retriever = EvidenceRetriever(["invoice INV-9002"], mode="semantic")

    assert retriever.mode == "lexical"
    assert retriever.fallback_reason == "ImportError: model dependency unavailable"
    assert "using lexical retrieval" in caplog.text
