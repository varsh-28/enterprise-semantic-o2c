class PlainRAGBaseline:
    """Baseline: retrieve text chunks and summarize their content without structured graph queries."""
    def __init__(self, retriever):
        self.retriever = retriever

    def ask(self, question, k=4):
        evidence = self.retriever.search(question, k=k)
        return {
            "question": question,
            "answer": "Retrieved the most similar source snippets; no structured SPARQL reasoning was applied.",
            "evidence": evidence,
            "method": "plain_rag_retrieval_only"
        }
