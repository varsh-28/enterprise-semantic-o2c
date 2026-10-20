def test_overdue_invoice_answer(service):
    result = service.agent.ask("Which invoices are overdue?")
    ids = {row["invoiceId"] for row in result["results"]}
    assert ids == {"INV-9002", "INV-9004"}
    assert result["sparql"].startswith("PREFIX")

def test_delayed_delivery_answer(service):
    result = service.agent.ask("Which deliveries are delayed?")
    ids = {row["deliveryId"] for row in result["results"]}
    assert ids == {"D-502", "D-503"}

def test_answer_has_traceable_evidence(service):
    result = service.agent.ask("Which invoices are overdue?")
    assert "evidence" in result
    assert "method" in result
