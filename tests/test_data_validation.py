import shutil

import pandas as pd
import pytest

from o2c.graph import DATA_DIR, O2CDataError, load_source_data


def _copy_data(tmp_path):
    for path in DATA_DIR.glob("*.csv"):
        shutil.copy(path, tmp_path / path.name)
    return tmp_path


def _replace_cell(data_dir, filename, row, column, value):
    path = data_dir / filename
    frame = pd.read_csv(path, dtype=str, keep_default_na=False)
    frame.loc[row, column] = value
    frame.to_csv(path, index=False)


def test_load_source_data_accepts_project_dataset():
    tables = load_source_data()

    assert set(tables) == {
        "customers.csv",
        "orders.csv",
        "deliveries.csv",
        "invoices.csv",
        "payments.csv",
    }


@pytest.mark.parametrize(
    ("filename", "content", "message"),
    [
        ("orders.csv", "order_id,amount\nSO-1,12\n", "missing required column"),
        ("orders.csv", 'order_id,customer_id\n"unterminated, C100\n', "could not read CSV"),
        ("customers.csv", "customer_id,customer_id,name,source_system,source_record_id\n", "duplicate column"),
    ],
)
def test_rejects_malformed_csv_files(tmp_path, filename, content, message):
    data_dir = _copy_data(tmp_path)
    (data_dir / filename).write_text(content, encoding="utf-8")

    with pytest.raises(O2CDataError, match=message):
        load_source_data(data_dir)


@pytest.mark.parametrize(
    ("filename", "row", "column", "value", "message"),
    [
        ("customers.csv", 1, "customer_id", "C100", "duplicate customer_id"),
        ("orders.csv", 0, "customer_id", "C-NOT-FOUND", "references unknown customer_id"),
        ("deliveries.csv", 0, "planned_date", "2026-02-30", "planned_date"),
        ("invoices.csv", 0, "amount", "not-a-number", "valid decimal"),
        ("orders.csv", 0, "amount", "-0.01", "non-negative decimal"),
        ("payments.csv", 0, "paid_date", "yesterday", "ISO date"),
        ("orders.csv", 0, "description", "", "must not be empty"),
    ],
)
def test_rejects_invalid_values_and_relationships(
    tmp_path, filename, row, column, value, message
):
    data_dir = _copy_data(tmp_path)
    _replace_cell(data_dir, filename, row, column, value)

    with pytest.raises(O2CDataError, match=message):
        load_source_data(data_dir)


def test_rejects_duplicate_source_record_ids_across_tables(tmp_path):
    data_dir = _copy_data(tmp_path)
    _replace_cell(
        data_dir, "orders.csv", 0, "source_record_id", "SAP-CUST-100"
    )

    with pytest.raises(O2CDataError, match="duplicate source_record_id"):
        load_source_data(data_dir)
