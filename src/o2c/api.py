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
