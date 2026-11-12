import os

import pytest

pytestmark = pytest.mark.skipif(
    os.getenv("O2C_ENABLE_NEO4J") != "1", reason="requires a running, loaded Neo4j"
)


@pytest.fixture(scope="module")
def service():
    from o2c.service import O2CService

    instance = O2CService(retrieval_mode="lexical")
    try:
        yield instance
    finally:
        instance.close()


@pytest.mark.parametrize(
    ("question", "result_keys"),
    [
        ("Which invoices are overdue?", ("invoiceId",)),
        ("Which deliveries are delayed?", ("deliveryId",)),
        ("Show invoices and their orders", ("invoiceId", "orderId")),
        ("Show customer orders", ("customerId", "orderId")),
        ("List payment records", ("paymentId", "invoiceId")),
    ],
)
def test_sparql_and_cypher_agree_on_supported_intents(
    service, question, result_keys
):
    sparql_rows = service.agent.ask(question)["results"]
    cypher_rows = service.cypher_agent.ask(question)["results"]

    assert sparql_rows
    assert {
        tuple(row[key] for key in result_keys) for row in sparql_rows
    } == {
        tuple(row[key] for key in result_keys) for row in cypher_rows
    }


def test_cypher_supports_customer_overdue_exposure(service):
    result = service.cypher_agent.ask("Which customers have overdue exposure?")

    assert result["intent"] == "customer_overdue_exposure"
    assert {row["invoiceId"] for row in result["results"]} == {
        "INV-9002",
        "INV-9004",
    }
