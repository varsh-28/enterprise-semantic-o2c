from fastapi.testclient import TestClient
from o2c.api import app

client = TestClient(app)

def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"

def test_ask_endpoint():
    response = client.post("/ask", json={"question": "Which invoices are overdue?"})
    assert response.status_code == 200
    assert response.json()["intent"] == "overdue_invoices"
    assert len(response.json()["results"]) == 2

def test_invalid_question_rejected():
    response = client.post("/ask", json={"question": "x"})
    assert response.status_code == 422
