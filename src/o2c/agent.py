PREFIXES = """PREFIX o2c: <https://example.org/o2c#>
PREFIX ex: <https://example.org/entity/>
"""


class O2CAgent:
    """Route questions to known SPARQL templates and return evidence."""

    def __init__(self, graph, retriever):
        self.graph = graph
        self.retriever = retriever

    def _intent(self, question):
        q = question.lower()

        if "invoice" in q and any(
            word in q for word in ("overdue", "unpaid", "late")
        ):
            return "overdue_invoices"

        if any(word in q for word in ("delivery", "deliveries")) and any(
            word in q for word in ("delayed", "delay", "late", "transit")
        ):
            return "delayed_deliveries"

        if "customer" in q and "order" in q:
            return "customer_orders"

        if "invoice" in q and "order" in q:
            return "invoice_orders"

        if "payment" in q:
            return "payments"

        return "evidence_search"

    def _query(self, intent):
        if intent == "overdue_invoices":
            return PREFIXES + """
SELECT ?invoiceId ?status ?amount ?dueDate ?orderId WHERE {
 ?i a o2c:Invoice ;
    o2c:externalId ?invoiceId ;
    o2c:status ?status ;
    o2c:amount ?amount ;
    o2c:dueDate ?dueDate ;
    o2c:forOrder ?o .
 ?o o2c:externalId ?orderId .
 FILTER(LCASE(STR(?status)) = "overdue")
} ORDER BY ?dueDate"""

        if intent == "delayed_deliveries":
            return PREFIXES + """
SELECT ?deliveryId ?status ?plannedDate ?orderId WHERE {
 ?d a o2c:Delivery ;
    o2c:externalId ?deliveryId ;
    o2c:status ?status ;
    o2c:plannedDate ?plannedDate ;
    o2c:hasOrder ?o .
 ?o o2c:externalId ?orderId .
 FILTER(
   LCASE(STR(?status)) = "delayed" ||
   LCASE(STR(?status)) = "in_transit"
 )
} ORDER BY ?plannedDate"""

        if intent == "customer_orders":
            return PREFIXES + """
SELECT ?customerName ?orderId ?status ?amount WHERE {
 ?o a o2c:SalesOrder ;
    o2c:externalId ?orderId ;
    o2c:status ?status ;
    o2c:amount ?amount ;
    o2c:hasCustomer ?c .
 ?c o2c:name ?customerName .
} ORDER BY ?customerName"""

        if intent == "invoice_orders":
            return PREFIXES + """
SELECT ?invoiceId ?orderId ?status ?amount WHERE {
 ?i a o2c:Invoice ;
    o2c:externalId ?invoiceId ;
    o2c:status ?status ;
    o2c:amount ?amount ;
    o2c:forOrder ?o .
 ?o o2c:externalId ?orderId .
} ORDER BY ?invoiceId"""

        if intent == "payments":
            return PREFIXES + """
SELECT ?paymentId ?invoiceId ?status ?amount WHERE {
 ?p a o2c:Payment ;
    o2c:externalId ?paymentId ;
    o2c:status ?status ;
    o2c:amount ?amount ;
    o2c:forInvoice ?i .
 ?i o2c:externalId ?invoiceId .
} ORDER BY ?paymentId"""

        return None

    def _rows(self, query):
        if not query:
            return []

        results = self.graph.query(query)
        return [
            {
                str(variable): str(value)
                for variable, value in row.asdict().items()
            }
            for row in results
        ]

    def ask(self, question):
        intent = self._intent(question)
        sparql = self._query(intent)
        rows = self._rows(sparql)
        evidence = self.retriever.search(question, k=4)

        if intent == "overdue_invoices":
            answer = (
                f"Found {len(rows)} overdue invoice(s)."
                if rows
                else "No overdue invoices were found."
            )
        elif intent == "delayed_deliveries":
            answer = (
                f"Found {len(rows)} delivery record(s) marked delayed "
                "or still in transit."
                if rows
                else "No delayed or in-transit deliveries were found."
            )
        elif rows:
            answer = (
                f"Found {len(rows)} matching record(s) for "
                f"{intent.replace('_', ' ')}."
            )
        else:
            answer = (
                "No supported structured query matched. "
                "Retrieved evidence is provided for context."
            )

        return {
            "question": question,
            "intent": intent,
            "answer": answer,
            "results": rows,
            "sparql": sparql,
            "evidence": evidence,
            "method": "safe_template_sparql_plus_faiss_or_lexical_retrieval",
        }
