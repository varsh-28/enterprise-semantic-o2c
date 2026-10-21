from neo4j import READ_ACCESS, unit_of_work

from .agent import O2CAgent
from .cypher_safety import enforce_read_only

QUERY_TIMEOUT_S = 5

TEMPLATES = {
    "overdue_invoices": """
MATCH (i:Invoice)-[:FOR_ORDER]->(o:SalesOrder)
WHERE toLower(i.status) = 'overdue'
RETURN i.id AS invoiceId, i.status AS status, toString(i.amount) AS amount,
       toString(i.dueDate) AS dueDate, o.id AS orderId
ORDER BY i.dueDate""",
    "delayed_deliveries": """
MATCH (d:Delivery)-[:HAS_ORDER]->(o:SalesOrder)
WHERE toLower(d.status) IN ['delayed', 'in_transit']
RETURN d.id AS deliveryId, d.status AS status, toString(d.plannedDate) AS plannedDate,
       o.id AS orderId
ORDER BY d.plannedDate""",
    "customer_orders": """
MATCH (o:SalesOrder)-[:HAS_CUSTOMER]->(c:Customer)
RETURN c.name AS customerName, o.id AS orderId, o.status AS status,
       toString(o.amount) AS amount
ORDER BY c.name""",
    "invoice_orders": """
MATCH (i:Invoice)-[:FOR_ORDER]->(o:SalesOrder)
RETURN i.id AS invoiceId, o.id AS orderId, i.status AS status, toString(i.amount) AS amount
ORDER BY i.id""",
    "payments": """
MATCH (p:Payment)-[:FOR_INVOICE]->(i:Invoice)
RETURN p.id AS paymentId, i.id AS invoiceId, p.status AS status, toString(p.amount) AS amount
ORDER BY p.id""",
    # Three-hop traversal: the case that motivates the property-graph backend.
    "customer_overdue_exposure": """
MATCH (c:Customer)<-[:HAS_CUSTOMER]-(o:SalesOrder)<-[:FOR_ORDER]-(i:Invoice)
WHERE toLower(i.status) = 'overdue'
RETURN c.id AS customerId, c.name AS customerName, i.id AS invoiceId,
       o.id AS orderId, toString(i.amount) AS amount
ORDER BY c.name, i.amount DESC""",
}


class CypherAgent(O2CAgent):
    """Same intent routing and answer shape as O2CAgent; executes parameter-free Cypher templates."""

    def __init__(self, driver, retriever, database="neo4j"):
        super().__init__(graph=None, retriever=retriever)
        self.driver = driver
        self.database = database

    def _intent(self, question):
        q = question.lower()
        if "customer" in q and any(w in q for w in ("overdue", "exposure", "unpaid", "late")):
            return "customer_overdue_exposure"
        return super()._intent(question)

    def _query(self, intent):
        return TEMPLATES.get(intent)

    def _rows(self, query):
        if not query:
            return []
        safe = enforce_read_only(query)

        @unit_of_work(timeout=QUERY_TIMEOUT_S)
        def work(tx):
            return [
                {k: str(v) for k, v in record.items()}
                for record in tx.run(safe)
            ]

        with self.driver.session(
            database=self.database, default_access_mode=READ_ACCESS
        ) as session:
            return session.execute_read(work)

    def ask(self, question):
        result = super().ask(question)
        result["cypher"] = result.pop("sparql")
        result["method"] = "safe_template_cypher_plus_faiss_or_lexical_retrieval"
        return result