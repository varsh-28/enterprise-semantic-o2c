
from pathlib import Path
from decimal import Decimal
import re

import pandas as pd
from rdflib import Graph, Namespace, URIRef, Literal
from rdflib.namespace import RDF, XSD
from pyshacl import validate


BASE_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = BASE_DIR / "data"
ONTOLOGY_DIR = BASE_DIR / "ontology"

O2C = Namespace("https://example.org/o2c#")
EX = Namespace("https://example.org/entity/")


def normalize_customer_name(name):
    """Normalize whitespace and capitalization for name matching."""
    return re.sub(r"\s+", " ", name).strip().casefold()


def find_customer_matches(customers):
    """
    Group customer records with identical normalized names.

    These are candidate matches, not confirmed identities.
    Original customer IDs and source-system records are preserved.
    """
    groups = {}

    for customer in customers:
        normalized = normalize_customer_name(customer.get("name", ""))

        if not normalized:
            continue

        groups.setdefault(normalized, []).append(customer)

    return [
        group
        for group in groups.values()
        if len(group) > 1
    ]


def _read(name):
    return pd.read_csv(
        DATA_DIR / name,
        keep_default_na=False,
        dtype=str,
    ).fillna("")


def build_graph():
    """Build the Order-to-Cash RDF graph from source CSV files."""
    g = Graph()
    g.bind("o2c", O2C)
    g.bind("ex", EX)

    g.parse(ONTOLOGY_DIR / "o2c.ttl", format="turtle")

    customers = _read("customers.csv")
    orders = _read("orders.csv")
    deliveries = _read("deliveries.csv")
    invoices = _read("invoices.csv")
    payments = _read("payments.csv")

    def node(kind, ident):
        return URIRef(
            f"https://example.org/entity/{kind}/{ident}"
        )

    def common(n, ident, source, source_id):
        g.add((
            n,
            O2C.externalId,
            Literal(str(ident), datatype=XSD.string),
        ))
        g.add((
            n,
            O2C.sourceSystem,
            Literal(str(source), datatype=XSD.string),
        ))
        g.add((
            n,
            O2C.sourceRecordId,
            Literal(str(source_id), datatype=XSD.string),
        ))

        source_record = node("source", source_id)

        g.add((source_record, RDF.type, O2C.SourceRecord))
        g.add((
            source_record,
            O2C.sourceSystem,
            Literal(str(source), datatype=XSD.string),
        ))
        g.add((
            source_record,
            O2C.sourceRecordId,
            Literal(str(source_id), datatype=XSD.string),
        ))
        g.add((n, O2C.hasSourceRecord, source_record))

    # ---------------------------------------------------------
    # Customers
    # ---------------------------------------------------------
    customer_nodes = {}

    for r in customers.to_dict("records"):
        n = node("customer", r["customer_id"])
        customer_nodes[r["customer_id"]] = n

        g.add((n, RDF.type, O2C.Customer))
        common(
            n,
            r["customer_id"],
            r["source_system"],
            r["source_record_id"],
        )
        g.add((
            n,
            O2C.name,
            Literal(r["name"], datatype=XSD.string),
        ))

    # Link possible duplicate customers without merging records.
    customer_records = customers.to_dict("records")

    for match_group in find_customer_matches(customer_records):
        for i, customer_a in enumerate(match_group):
            for customer_b in match_group[i + 1:]:
                node_a = customer_nodes[customer_a["customer_id"]]
                node_b = customer_nodes[customer_b["customer_id"]]

                g.add((node_a, O2C.possibleMatch, node_b))
                g.add((node_b, O2C.possibleMatch, node_a))

    # ---------------------------------------------------------
    # Sales orders
    # ---------------------------------------------------------
    order_nodes = {}

    for r in orders.to_dict("records"):
        n = node("order", r["order_id"])
        order_nodes[r["order_id"]] = n

        g.add((n, RDF.type, O2C.SalesOrder))
        common(
            n,
            r["order_id"],
            r["source_system"],
            r["source_record_id"],
        )
        g.add((
            n,
            O2C.status,
            Literal(r["status"], datatype=XSD.string),
        ))
        g.add((
            n,
            O2C.amount,
            Literal(Decimal(r["amount"]), datatype=XSD.decimal),
        ))
        g.add((
            n,
            O2C.description,
            Literal(r["description"], datatype=XSD.string),
        ))
        g.add((
            n,
            O2C.hasCustomer,
            customer_nodes[r["customer_id"]],
        ))

    # ---------------------------------------------------------
    # Deliveries
    # ---------------------------------------------------------
    for r in deliveries.to_dict("records"):
        n = node("delivery", r["delivery_id"])

        g.add((n, RDF.type, O2C.Delivery))
        common(
            n,
            r["delivery_id"],
            r["source_system"],
            r["source_record_id"],
        )
        g.add((
            n,
            O2C.status,
            Literal(r["status"], datatype=XSD.string),
        ))
        g.add((n, O2C.hasOrder, order_nodes[r["order_id"]]))
        g.add((
            n,
            O2C.plannedDate,
            Literal(r["planned_date"], datatype=XSD.date),
        ))

        if r["actual_date"]:
            g.add((
                n,
                O2C.actualDate,
                Literal(r["actual_date"], datatype=XSD.date),
            ))

    # ---------------------------------------------------------
    # Invoices
    # ---------------------------------------------------------
    invoice_nodes = {}

    for r in invoices.to_dict("records"):
        n = node("invoice", r["invoice_id"])
        invoice_nodes[r["invoice_id"]] = n

        g.add((n, RDF.type, O2C.Invoice))
        common(
            n,
            r["invoice_id"],
            r["source_system"],
            r["source_record_id"],
        )
        g.add((
            n,
            O2C.status,
            Literal(r["status"], datatype=XSD.string),
        ))
        g.add((
            n,
            O2C.amount,
            Literal(Decimal(r["amount"]), datatype=XSD.decimal),
        ))
        g.add((
            n,
            O2C.dueDate,
            Literal(r["due_date"], datatype=XSD.date),
        ))
        g.add((n, O2C.forOrder, order_nodes[r["order_id"]]))

    # ---------------------------------------------------------
    # Payments
    # ---------------------------------------------------------
    for r in payments.to_dict("records"):
        n = node("payment", r["payment_id"])

        g.add((n, RDF.type, O2C.Payment))
        common(
            n,
            r["payment_id"],
            r["source_system"],
            r["source_record_id"],
        )
        g.add((
            n,
            O2C.status,
            Literal(r["status"], datatype=XSD.string),
        ))
        g.add((
            n,
            O2C.amount,
            Literal(Decimal(r["amount"]), datatype=XSD.decimal),
        ))

        if r["paid_date"]:
            g.add((
                n,
                O2C.paidDate,
                Literal(r["paid_date"], datatype=XSD.date),
            ))

        g.add((n, O2C.forInvoice, invoice_nodes[r["invoice_id"]]))

    return g


def validate_graph(g):
    """Validate the RDF graph against the project's SHACL shapes."""
    shapes = Graph()
    shapes.parse(ONTOLOGY_DIR / "shapes.ttl", format="turtle")

    conforms, report_graph, report_text = validate(
        data_graph=g,
        shacl_graph=shapes,
        inference="rdfs",
        abort_on_first=False,
        allow_warnings=False,
        meta_shacl=False,
    )

    return {
        "conforms": bool(conforms),
        "report": report_text,
    }
