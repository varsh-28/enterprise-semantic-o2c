from o2c.graph import build_graph, validate_graph

from o2c.graph import find_customer_matches


def test_find_customer_matches_normalizes_names():
    customers = [
        {
            "customer_id": "C101",
            "name": "Northwind Components",
            "source_system": "SAP",
        },
        {
            "customer_id": "SF101",
            "name": " NORTHWIND   COMPONENTS ",
            "source_system": "Salesforce",
        },
        {
            "customer_id": "C200",
            "name": "Blue Yonder Retail",
            "source_system": "SAP",
        },
    ]

    matches = find_customer_matches(customers)

    assert len(matches) == 1
    assert {
        customer["customer_id"] for customer in matches[0]
    } == {"C101", "SF101"}

def test_graph_contains_core_entity_types():
    graph = build_graph()
    assert len(graph) > 50
    assert validate_graph(graph)["conforms"] is True

def test_graph_has_invoice_and_delivery_instances():
    graph = build_graph()
    assert any("invoice/INV-9002" in str(s) for s in graph.subjects())
    assert any("delivery/D-502" in str(s) for s in graph.subjects())
