import pytest

from o2c.cypher_safety import UnsafeCypherError, enforce_read_only


def test_accepts_read_query_and_appends_limit():
    q = "MATCH (i:Invoice)-[:FOR_ORDER]->(o:SalesOrder) RETURN i.id, o.id"
    assert enforce_read_only(q).endswith("LIMIT 200")


def test_keeps_existing_limit():
    q = "MATCH (i:Invoice) RETURN i.id LIMIT 5"
    assert enforce_read_only(q) == q


@pytest.mark.parametrize("q", [
    "MATCH (i:Invoice) DETACH DELETE i",
    "MATCH (i:Invoice) SET i.status = 'paid' RETURN i",
    "MATCH (i:Invoice) RETURN i; MATCH (c:Customer) RETURN c",
    "CREATE (i:Invoice {id: 'x'}) RETURN i",
    "MATCH (i:Invoice) CALL db.labels() YIELD label RETURN label",
    "LOAD CSV FROM 'http://x' AS r MATCH (i:Invoice) RETURN i",
])
def test_rejects_writes_and_multi_statement(q):
    with pytest.raises(UnsafeCypherError):
        enforce_read_only(q)


def test_rejects_label_outside_allowlist():
    with pytest.raises(UnsafeCypherError):
        enforce_read_only("MATCH (u:User) RETURN u")


def test_keyword_inside_string_literal_is_ignored():
    enforce_read_only("MATCH (i:Invoice {status: 'SET DELETE'}) RETURN i.id")