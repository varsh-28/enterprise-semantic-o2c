import os

from .graph import build_graph, validate_graph, O2C
from .retrieval import EvidenceRetriever
from .agent import O2CAgent
from .baseline import PlainRAGBaseline


def graph_chunks(g):
    chunks = []
    for s, p, o in g:
        # Skip ontology schema triples and retain instance facts.
        if str(s).startswith("https://example.org/entity/"):
            chunks.append(f"{s.split('/')[-2]} {s.split('/')[-1]} {str(p).split('#')[-1]} {o}")
    return sorted(set(chunks))


class O2CService:
    def __init__(self, retrieval_mode=None):
        self.graph = build_graph()
        self.validation = validate_graph(self.graph)
        self.chunks = graph_chunks(self.graph)
        self.retriever = EvidenceRetriever(self.chunks, mode=retrieval_mode)
        self.agent = O2CAgent(self.graph, self.retriever)
        self.baseline = PlainRAGBaseline(self.retriever)

        self.neo4j = None
        self.cypher_agent = None
        if os.getenv("O2C_ENABLE_NEO4J") == "1":
            from .neo4j_store import Neo4jStore
            from .cypher_agent import CypherAgent

            self.neo4j = Neo4jStore.from_env()
            self.cypher_agent = CypherAgent(
                self.neo4j.driver, self.retriever, self.neo4j.database
            )