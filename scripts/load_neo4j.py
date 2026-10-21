from o2c.neo4j_store import Neo4jStore


def main():
    store = Neo4jStore.from_env()
    try:
        store.create_constraints()
        store.load(reset=True)
        print(store.counts())
    finally:
        store.close()


if __name__ == "__main__":
    main()