from contextlib import asynccontextmanager
import logging

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, field_validator

from .evaluation import run_evaluation
from .service import O2CService

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting O2C service")
    try:
        service = O2CService()
    except Exception:
        logger.exception("O2C service initialization failed")
        raise
    app.state.service = service
    logger.info(
        "O2C service initialized: triples=%d shacl_conforms=%s retrieval_mode=%s",
        len(service.graph),
        service.validation["conforms"],
        service.retriever.mode,
    )
    try:
        yield
    finally:
        app.state.service = None
        service.close()
        logger.info("O2C service stopped")


app = FastAPI(
    title="Enterprise Semantic Layer for Order-to-Cash",
    version="1.0.0",
    description="Synthetic O2C data mapped into RDF, SHACL validation, safe SPARQL, evidence retrieval and baseline evaluation.",
    lifespan=lifespan,
)


class AskRequest(BaseModel):
    question: str = Field(min_length=3, max_length=1000)

    @field_validator("question")
    @classmethod
    def question_must_not_be_blank(cls, value):
        question = value.strip()
        if not question:
            raise ValueError("question must not be blank")
        return question


def get_service(request: Request) -> O2CService:
    service = getattr(request.app.state, "service", None)
    if service is None:
        raise HTTPException(status_code=503, detail="O2C service is not initialized")
    return service


@app.get("/health")
def health(service: O2CService = Depends(get_service)):
    ready = bool(service.validation["conforms"])
    response = {
        "status": "ok" if ready else "not_ready",
        "ready": ready,
        "graph_triples": len(service.graph),
        "shacl_conforms": ready,
        "retrieval_mode": service.retriever.mode,
        "retrieval_fallback_reason": service.retriever.fallback_reason,
        "neo4j_enabled": service.cypher_agent is not None,
    }
    if not ready:
        return JSONResponse(status_code=503, content=response)
    return response


@app.get("/validation")
def validation(service: O2CService = Depends(get_service)):
    return service.validation


@app.post("/ask")
def ask(request: AskRequest, service: O2CService = Depends(get_service)):
    try:
        return service.agent.ask(request.question)
    except Exception as exc:
        logger.exception("Question processing failed in /ask")
        raise HTTPException(
            status_code=500,
            detail=f"Question processing failed: {type(exc).__name__}",
        ) from exc


@app.post("/ask/cypher")
def ask_cypher(request: AskRequest, service: O2CService = Depends(get_service)):
    agent = service.cypher_agent
    if agent is None:
        raise HTTPException(
            status_code=503,
            detail="Neo4j backend disabled. Set O2C_ENABLE_NEO4J=1 and run scripts/load_neo4j.py.",
        )
    try:
        return agent.ask(request.question)
    except Exception as exc:
        logger.exception("Question processing failed in /ask/cypher")
        raise HTTPException(
            status_code=500,
            detail=f"Question processing failed: {type(exc).__name__}",
        ) from exc


@app.post("/baseline")
def baseline(request: AskRequest, service: O2CService = Depends(get_service)):
    return service.baseline.ask(request.question)


@app.post("/evaluate")
def evaluate(service: O2CService = Depends(get_service)):
    return run_evaluation(service)
