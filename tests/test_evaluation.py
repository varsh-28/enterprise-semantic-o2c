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
