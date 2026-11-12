
from pathlib import Path
import csv
from datetime import date
from decimal import Decimal, InvalidOperation
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

CSV_SCHEMAS = {
    "customers.csv": {
        "id": "customer_id",
        "required": {"customer_id", "name", "source_system", "source_record_id"},
        "amounts": set(),
        "dates": {},
        "references": {},
    },
    "orders.csv": {
        "id": "order_id",
        "required": {
            "order_id", "customer_id", "status", "amount", "source_system",
            "source_record_id", "description",
        },
        "amounts": {"amount"},
        "dates": {},
        "references": {"customer_id": "customers.csv"},
    },
    "deliveries.csv": {
        "id": "delivery_id",
        "required": {
            "delivery_id", "order_id", "status", "planned_date", "actual_date",
            "source_system", "source_record_id",
        },
        "amounts": set(),
        "dates": {"planned_date": False, "actual_date": True},
        "references": {"order_id": "orders.csv"},
    },
    "invoices.csv": {
        "id": "invoice_id",
        "required": {
            "invoice_id", "order_id", "status", "amount", "due_date",
            "source_system", "source_record_id",
        },
        "amounts": {"amount"},
        "dates": {"due_date": False},
        "references": {"order_id": "orders.csv"},
    },
    "payments.csv": {
        "id": "payment_id",
        "required": {
            "payment_id", "invoice_id", "status", "amount", "paid_date",
            "source_system", "source_record_id",
        },
        "amounts": {"amount"},
        "dates": {"paid_date": True},
        "references": {"invoice_id": "invoices.csv"},
    },
}


class O2CDataError(ValueError):
    """Raised when source CSV data cannot safely be mapped into the O2C graph."""


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


def load_source_data(data_dir=DATA_DIR):
    """Read and validate the complete CSV dataset before graph construction."""
    data_dir = Path(data_dir)
    tables = {}
    source_record_ids = {}

    for filename, schema in CSV_SCHEMAS.items():
        path = data_dir / filename
        try:
            with path.open(newline="", encoding="utf-8-sig") as source_file:
                header = next(csv.reader(source_file, strict=True), [])
            if len(header) != len(set(header)):
                raise O2CDataError(f"{filename}: duplicate column names in CSV header")
            frame = pd.read_csv(path, keep_default_na=False, dtype=str)
        except O2CDataError:
            raise
        except (
            OSError,
            UnicodeError,
            csv.Error,
            pd.errors.ParserError,
            pd.errors.EmptyDataError,
        ) as exc:
            raise O2CDataError(f"{filename}: could not read CSV: {exc}") from exc

        missing_columns = sorted(schema["required"] - set(frame.columns))
        if missing_columns:
            raise O2CDataError(
                f"{filename}: missing required column(s): {', '.join(missing_columns)}"
            )
        if frame.empty:
            raise O2CDataError(f"{filename}: expected at least one data row")

        for column in schema["required"]:
            frame[column] = frame[column].fillna("").astype(str)

        id_column = schema["id"]
        seen_ids = set()
        for index, row in frame.iterrows():
            row_number = index + 2
            for column in schema["required"]:
                value = row[column]
                optional_value = (
                    column in schema["dates"] and schema["dates"][column]
                )
                if optional_value and not value.strip():
                    continue
                if not value.strip():
                    raise O2CDataError(
                        f"{filename}:{row_number}: '{column}' must not be empty"
                    )

            entity_id = row[id_column]
            if entity_id != entity_id.strip():
                raise O2CDataError(
                    f"{filename}:{row_number}: '{id_column}' must not have surrounding whitespace"
                )
            if entity_id in seen_ids:
                raise O2CDataError(
                    f"{filename}:{row_number}: duplicate {id_column} '{entity_id}'"
                )
            seen_ids.add(entity_id)

            source_id = row["source_record_id"]
            if source_id != source_id.strip():
                raise O2CDataError(
                    f"{filename}:{row_number}: 'source_record_id' must not have surrounding whitespace"
                )
            if source_id in source_record_ids:
                previous_file, previous_row = source_record_ids[source_id]
                raise O2CDataError(
                    f"{filename}:{row_number}: duplicate source_record_id '{source_id}' "
                    f"(also in {previous_file}:{previous_row})"
                )
            source_record_ids[source_id] = (filename, row_number)

            for column in schema["amounts"]:
                try:
                    amount = Decimal(row[column])
                except InvalidOperation as exc:
                    raise O2CDataError(
                        f"{filename}:{row_number}: '{column}' must be a valid decimal"
                    ) from exc
                if not amount.is_finite() or amount < 0:
                    raise O2CDataError(
                        f"{filename}:{row_number}: '{column}' must be a finite, non-negative decimal"
                    )

            for column, optional in schema["dates"].items():
                value = row[column]
                if optional and not value:
                    continue
                try:
                    parsed_date = date.fromisoformat(value)
                except ValueError as exc:
                    raise O2CDataError(
                        f"{filename}:{row_number}: '{column}' must be an ISO date (YYYY-MM-DD)"
                    ) from exc
                if parsed_date.isoformat() != value:
                    raise O2CDataError(
                        f"{filename}:{row_number}: '{column}' must use YYYY-MM-DD format"
                    )

        tables[filename] = frame

    for filename, schema in CSV_SCHEMAS.items():
        for reference_column, target_filename in schema["references"].items():
            target_id_column = CSV_SCHEMAS[target_filename]["id"]
            target_ids = set(tables[target_filename][target_id_column])
            for index, value in tables[filename][reference_column].items():
                if value not in target_ids:
                    raise O2CDataError(
                        f"{filename}:{index + 2}: '{reference_column}' references "
                        f"unknown {target_id_column} '{value}'"
                    )

    return tables


def build_graph(data_dir=DATA_DIR):
    """Build the Order-to-Cash RDF graph from source CSV files."""
    tables = load_source_data(data_dir)
    g = Graph()
    g.bind("o2c", O2C)
    g.bind("ex", EX)

    g.parse(ONTOLOGY_DIR / "o2c.ttl", format="turtle")

    customers = tables["customers.csv"]
    orders = tables["orders.csv"]
    deliveries = tables["deliveries.csv"]
    invoices = tables["invoices.csv"]
    payments = tables["payments.csv"]

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
