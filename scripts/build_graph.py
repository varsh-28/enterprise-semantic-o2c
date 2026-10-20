from o2c.graph import build_graph, validate_graph

if __name__ == "__main__":
    graph = build_graph()
    report = validate_graph(graph)
    print(f"Triples: {len(graph)}")
    print(f"SHACL conforms: {report['conforms']}")
    print(report["report"])
    if not report["conforms"]:
        raise SystemExit(1)
    graph.serialize("o2c_graph.ttl", format="turtle")
    print("Wrote o2c_graph.ttl")
