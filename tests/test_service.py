from o2c.service import O2CService


def test_service_closes_optional_neo4j_store(service):
    class Store:
        closed = False

        def close(self):
            self.closed = True

    store = Store()
    service.neo4j = store

    service.close()

    assert store.closed is True
    service.neo4j = None
