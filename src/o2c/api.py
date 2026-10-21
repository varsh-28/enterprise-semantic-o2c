from functools import lru_cache
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from .service import O2CService
from .evaluation import run_evaluation

app = FastAPI(
    title="Enterprise Semantic Layer for Order-to-Cash",
    version="1.0.0",
    description="Synthetic O2C data mapped into RDF, SHACL validation, safe SPARQL, evidence retrieval and baseline evaluation."
)

@lru_cache(maxsize=1)
def get_service():
    return O2CService()

class AskRequest(BaseModel):
    question: str = Field(min_length=3, max_length=1000)

@app.get("/health")
def health():
    service = get_service()
    return {"status": "ok", "graph_triples": len(service.graph),
            "shacl_conforms": service.validation["conforms"],
            "retrieval_mode": service.retriever.mode}

@app.post("/ask/cypher")
def ask_cypher(request: AskRequest):
    agent = get_service().cypher_agent
    if agent is None:
        raise HTTPException(
            status_code=503,
            detail="Neo4j backend disabled. Set O2C_ENABLE_NEO4J=1 and run scripts/load_neo4j.py.",
        )
    try:
        return agent.ask(request.question)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Question processing failed: {type(exc).__name__}")
@app.get("/validation")
def validation():
    return get_service().validation

@app.post("/ask")
def ask(request: AskRequest):
    try:
        return get_service().agent.ask(request.question)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Question processing failed: {type(exc).__name__}")

@app.post("/baseline")
def baseline(request: AskRequest):
    return get_service().baseline.ask(request.question)

@app.post("/evaluate")
def evaluate():
    return run_evaluation(get_service())
