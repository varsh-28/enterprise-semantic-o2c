import pytest
from fastapi.testclient import TestClient

from o2c.api import app


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("RETRIEVAL_MODE", "lexical")
    with TestClient(app) as test_client:
        yield test_client


def test_health_reports_readiness_and_configured_backends(client):
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.json()["ready"] is True
    assert response.json()["retrieval_mode"] == "lexical"
    assert response.json()["neo4j_enabled"] is False


def test_health_marks_invalid_graph_not_ready(client):
    service = app.state.service
    original_validation = service.validation
    service.validation = {"conforms": False, "report": "Invalid graph"}
    try:
        response = client.get("/health")
    finally:
        service.validation = original_validation

    assert response.status_code == 503
    assert response.json()["ready"] is False


def test_ask_endpoint(client):
    response = client.post(
        "/ask", json={"question": "Which invoices are overdue?"}
    )

    assert response.status_code == 200
    assert response.json()["intent"] == "overdue_invoices"
    assert len(response.json()["results"]) == 2


@pytest.mark.parametrize("question", ["x", "   ", "a" * 1001])
def test_invalid_question_rejected(client, question):
    response = client.post("/ask", json={"question": question})

    assert response.status_code == 422


def test_cypher_endpoint_reports_disabled_backend(client):
    response = client.post(
        "/ask/cypher", json={"question": "Which invoices are overdue?"}
    )

    assert response.status_code == 503


def test_service_is_removed_from_app_state_on_shutdown():
    with TestClient(app):
        assert app.state.service is not None

    assert app.state.service is None
