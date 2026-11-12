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


def test_lexical_retrieval_normalizes_question_words_and_prioritizes_status():
    retriever = EvidenceRetriever(
        [
            "invoice INV-9001 status paid",
            "invoice INV-9002 status overdue",
            "invoice INV-9004 status overdue",
            "invoice INV-9002 amount 8400.00",
        ],
        mode="lexical",
    )

    results = retriever.search("Which invoice is overdue?")

    assert [item["text"] for item in results[:2]] == [
        "invoice INV-9002 status overdue",
        "invoice INV-9004 status overdue",
    ]
    assert len(results) == 2
    assert all(item["score"] == 1 for item in results)


def test_lexical_retrieval_omits_zero_score_unrelated_chunks():
    retriever = EvidenceRetriever(
        ["invoice INV-9001 status paid", "customer C100 name Northwind"],
        mode="lexical",
    )

    assert retriever.search("What is the weather today?") == []


def test_unpaid_invoice_query_retrieves_overdue_invoice_evidence(service):
    results = service.retriever.search("List unpaid invoices")

    assert results
    assert all("overdue" in item["text"].lower() for item in results)
    assert {item["text"].split()[1] for item in results} == {
        "INV-9002",
        "INV-9004",
    }


def test_payment_records_query_retrieves_payment_evidence(service):
    results = service.retriever.search("List payment records")

    assert results
    assert all(item["text"].lower().startswith("payment ") for item in results)
    assert {
        item["text"].split()[1] for item in results
    } == {"PAY-7001", "PAY-7002", "PAY-7003"}
