import os

from neo4j import GraphDatabase

from .graph import _read, find_customer_matches

CONSTRAINTS = [
    "CREATE CONSTRAINT customer_id IF NOT EXISTS FOR (n:Customer) REQUIRE n.id IS UNIQUE",
    "CREATE CONSTRAINT order_id IF NOT EXISTS FOR (n:SalesOrder) REQUIRE n.id IS UNIQUE",
    "CREATE CONSTRAINT delivery_id IF NOT EXISTS FOR (n:Delivery) REQUIRE n.id IS UNIQUE",
    "CREATE CONSTRAINT invoice_id IF NOT EXISTS FOR (n:Invoice) REQUIRE n.id IS UNIQUE",
    "CREATE CONSTRAINT payment_id IF NOT EXISTS FOR (n:Payment) REQUIRE n.id IS UNIQUE",
    "CREATE CONSTRAINT source_record_id IF NOT EXISTS FOR (n:SourceRecord) REQUIRE n.id IS UNIQUE",
]

_SOURCE = """
MERGE (s:SourceRecord {id: r.source_record_id})
SET s.sourceSystem = r.source_system
MERGE (n)-[:HAS_SOURCE_RECORD]->(s)
"""

LOAD_CUSTOMERS = """
UNWIND $rows AS r
MERGE (n:Customer {id: r.customer_id})
SET n.name = r.name, n.sourceSystem = r.source_system, n.sourceRecordId = r.source_record_id
""" + _SOURCE

LOAD_ORDERS = """
UNWIND $rows AS r
MERGE (n:SalesOrder {id: r.order_id})
SET n.status = r.status, n.amount = toFloat(r.amount), n.description = r.description,
    n.sourceSystem = r.source_system, n.sourceRecordId = r.source_record_id
WITH n, r
MATCH (c:Customer {id: r.customer_id})
MERGE (n)-[:HAS_CUSTOMER]->(c)
""" + _SOURCE

LOAD_DELIVERIES = """
UNWIND $rows AS r
MERGE (n:Delivery {id: r.delivery_id})
SET n.status = r.status, n.plannedDate = date(r.planned_date),
    n.actualDate = CASE WHEN r.actual_date = '' THEN null ELSE date(r.actual_date) END,
    n.sourceSystem = r.source_system, n.sourceRecordId = r.source_record_id
WITH n, r
MATCH (o:SalesOrder {id: r.order_id})
MERGE (n)-[:HAS_ORDER]->(o)
""" + _SOURCE

LOAD_INVOICES = """
UNWIND $rows AS r
MERGE (n:Invoice {id: r.invoice_id})
SET n.status = r.status, n.amount = toFloat(r.amount), n.dueDate = date(r.due_date),
    n.sourceSystem = r.source_system, n.sourceRecordId = r.source_record_id
WITH n, r
MATCH (o:SalesOrder {id: r.order_id})
MERGE (n)-[:FOR_ORDER]->(o)
""" + _SOURCE

LOAD_PAYMENTS = """
UNWIND $rows AS r
MERGE (n:Payment {id: r.payment_id})
SET n.status = r.status, n.amount = toFloat(r.amount),
    n.paidDate = CASE WHEN r.paid_date = '' THEN null ELSE date(r.paid_date) END,
    n.sourceSystem = r.source_system, n.sourceRecordId = r.source_record_id
WITH n, r
MATCH (i:Invoice {id: r.invoice_id})
MERGE (n)-[:FOR_INVOICE]->(i)
""" + _SOURCE

LOAD_MATCHES = """
UNWIND $pairs AS p
MATCH (a:Customer {id: p.a}), (b:Customer {id: p.b})
MERGE (a)-[:POSSIBLE_MATCH]->(b)
MERGE (b)-[:POSSIBLE_MATCH]->(a)
"""


class Neo4jStore:
    def __init__(self, uri, user, password, database="neo4j"):
        self.driver = GraphDatabase.driver(uri, auth=(user, password))
        self.database = database

    @classmethod
    def from_env(cls):
        password = os.getenv("NEO4J_PASSWORD")
        if not password:
            raise RuntimeError("NEO4J_PASSWORD is not set")
        return cls(
            os.getenv("NEO4J_URI", "bolt://localhost:7687"),
            os.getenv("NEO4J_USER", "neo4j"),
            password,
            os.getenv("NEO4J_DATABASE", "neo4j"),
        )

    def close(self):
        self.driver.close()

    def _write(self, query, **params):
        with self.driver.session(database=self.database) as session:
            session.execute_write(lambda tx: tx.run(query, **params).consume())

    def create_constraints(self):
        for statement in CONSTRAINTS:
            self._write(statement)

    def reset(self):
        self._write("MATCH (n) DETACH DELETE n")

    def load(self, reset=True):
        if reset:
            self.reset()
        customers = _read("customers.csv")
        self._write(LOAD_CUSTOMERS, rows=customers.to_dict("records"))
        self._write(LOAD_ORDERS, rows=_read("orders.csv").to_dict("records"))
        self._write(LOAD_DELIVERIES, rows=_read("deliveries.csv").to_dict("records"))
        self._write(LOAD_INVOICES, rows=_read("invoices.csv").to_dict("records"))
        self._write(LOAD_PAYMENTS, rows=_read("payments.csv").to_dict("records"))

        pairs = []
        for group in find_customer_matches(customers.to_dict("records")):
            for i, a in enumerate(group):
                for b in group[i + 1:]:
                    pairs.append({"a": a["customer_id"], "b": b["customer_id"]})
        if pairs:
            self._write(LOAD_MATCHES, pairs=pairs)

    def counts(self):
        with self.driver.session(database=self.database) as session:
            rows = session.execute_read(
                lambda tx: tx.run(
                    "MATCH (n) RETURN labels(n)[0] AS label, count(*) AS n ORDER BY label"
                ).data()
            )
        return {r["label"]: r["n"] for r in rows}