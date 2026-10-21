from pathlib import Path
from time import perf_counter
import json

ROOT = Path(__file__).resolve().parents[2]


def _ids(result):
    found = set()
    for row in result["results"]:
        found.update(row.values())
    return found


def _correct(expected, result):
    return expected.issubset(_ids(result)) if expected else bool(result["results"])


def _query_ms(agent, question):
    """Time structured query execution only, excluding evidence retrieval."""
    query = agent._query(agent._intent(question))
    start = perf_counter()
    agent._rows(query)
    return (perf_counter() - start) * 1000


def run_evaluation(service):
    dataset_path = ROOT / "evaluation" / "questions.json"
    dataset = json.loads(dataset_path.read_text(encoding="utf-8"))
    cypher = getattr(service, "cypher_agent", None)

    agent_correct = cypher_correct = baseline_coverage = 0
    sparql_ms = cypher_ms = 0.0
    rows = []
    for item in dataset:
        q = item["question"]
        expected = set(item.get("expected_ids", []))

        result = service.agent.ask(q)
        correct = _correct(expected, result)
        agent_correct += int(correct)
        sparql_ms += _query_ms(service.agent, q)

        row = {
            "question": q,
            "expected_ids": sorted(expected),
            "agent_result_ids_found": sorted(expected & _ids(result)),
            "agent_correct": correct,
        }

        if cypher is not None:
            c_result = cypher.ask(q)
            c_correct = _correct(expected, c_result)
            cypher_correct += int(c_correct)
            cypher_ms += _query_ms(cypher, q)
            row["cypher_correct"] = c_correct

        base = service.baseline.ask(q)
        baseline_coverage += int(bool(base["evidence"]))
        row["baseline_has_evidence"] = bool(base["evidence"])
        rows.append(row)

    n = max(1, len(dataset))
    return {
        "dataset_size": len(dataset),
        "agent_expected_id_accuracy": round(agent_correct / n, 3),
        "cypher_expected_id_accuracy": round(cypher_correct / n, 3) if cypher else None,
        "plain_rag_evidence_coverage": round(baseline_coverage / n, 3),
        "sparql_avg_query_ms": round(sparql_ms / n, 2),
        "cypher_avg_query_ms": round(cypher_ms / n, 2) if cypher else None,
        "results": rows,
        "note": "Small synthetic smoke-test set; metrics are illustrative and not a statistically significant benchmark.",
    }