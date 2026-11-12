from o2c.evaluation import _correct, _ids, run_evaluation


def test_evaluation_only_matches_identifier_fields():
    result = {
        "results": [
            {
                "invoiceId": "INV-9002",
                "amount": "INV-9004",
                "status": "overdue",
            }
        ]
    }

    assert _ids(result) == {"INV-9002"}
    assert _correct({"INV-9002"}, result)
    assert not _correct({"INV-9004"}, result)


def test_evaluation_matches_all_labeled_ids(service):
    result = run_evaluation(service)

    assert result["agent_expected_id_accuracy"] == 1
    assert all(row["agent_correct"] for row in result["results"])


def test_evaluation_baseline_finds_synonym_cases_not_unrelated_question(service):
    result = run_evaluation(service)
    evidence_by_question = {
        row["question"]: row["baseline_has_evidence"]
        for row in result["results"]
    }

    assert evidence_by_question["List unpaid invoices"] is True
    assert evidence_by_question["List payment records"] is True
    assert evidence_by_question["What is the weather today?"] is False
