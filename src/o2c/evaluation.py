from pathlib import Path
import json

ROOT = Path(__file__).resolve().parents[2]

def run_evaluation(service):
    dataset_path = ROOT / "evaluation" / "questions.json"
    dataset = json.loads(dataset_path.read_text(encoding="utf-8"))
    agent_correct = baseline_coverage = 0
    rows = []
    for item in dataset:
        result = service.agent.ask(item["question"])
        expected = set(item.get("expected_ids", []))
        found = set()
        for row in result["results"]:
            found.update(row.values())
        correct = expected.issubset(found) if expected else bool(result["results"])
        agent_correct += int(correct)
        base = service.baseline.ask(item["question"])
        baseline_coverage += int(bool(base["evidence"]))
        rows.append({
            "question": item["question"],
            "expected_ids": sorted(expected),
            "agent_result_ids_found": sorted(expected & found),
            "agent_correct": correct,
            "baseline_has_evidence": bool(base["evidence"])
        })
    n = max(1, len(dataset))
    return {
        "dataset_size": len(dataset),
        "agent_expected_id_accuracy": round(agent_correct / n, 3),
        "plain_rag_evidence_coverage": round(baseline_coverage / n, 3),
        "results": rows,
        "note": "Small synthetic smoke-test set; metrics are illustrative and not a statistically significant benchmark."
    }
