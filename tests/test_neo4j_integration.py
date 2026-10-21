import os

import pytest

pytestmark = pytest.mark.skipif(
    os.getenv("O2C_ENABLE_NEO4J") != "1", reason="requires a running, loaded Neo4j"
)


def test_sparql_and_cypher_agree_on_overdue_invoices():
    from o2c.service import O2CService

    svc = O2CService()
    q = "Which invoices are overdue?"
    sparql_ids = {r["invoiceId"] for r in svc.agent.ask(q)["results"]}
    cypher_ids = {r["invoiceId"] for r in svc.cypher_agent.ask(q)["results"]}
    assert sparql_ids and sparql_ids == cypher_ids