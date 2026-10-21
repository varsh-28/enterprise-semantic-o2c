# Enterprise Semantic Layer for Order-to-Cash (O2C)

A runnable portfolio project that unifies synthetic SAP-, Salesforce-, and ServiceNow-style order-to-cash records in an RDF knowledge graph, validates the graph with SHACL, retrieves evidence with sentence embeddings + FAISS, answers questions with constrained SPARQL, and compares the grounded agent with a plain-RAG baseline. An optional Neo4j backend loads the same records into a property graph and answers supported questions with safe, template-based Cypher.

## What is included

- **Ontology:** OWL/RDF + SKOS vocabulary in `ontology/o2c.ttl`
- **Validation:** SHACL shapes in `ontology/shapes.ttl`
- **Synthetic data:** CSV source records in `data/`
- **ETL + graph:** source mapping and RDF graph construction in `src/o2c/graph.py`
- **Semantic retrieval:** sentence-transformers embeddings and FAISS in `src/o2c/retrieval.py`
- **Question answering:** safe, template-constrained SPARQL agent with traceable evidence in `src/o2c/agent.py`
- **Optional property graph:** Neo4j loader, read-only Cypher templates, and query safety checks in `src/o2c/neo4j_store.py`, `src/o2c/cypher_agent.py`, and `src/o2c/cypher_safety.py`
- **Baseline:** embedding-based plain-RAG answerer for comparison in `src/o2c/baseline.py`
- **API:** FastAPI endpoints in `src/o2c/api.py`
- **Evaluation:** labeled questions and simple groundedness/answer-match metrics in `evaluation/`
- **Tests:** pytest regression suite in `tests/`

> The default agent uses deterministic intent-to-SPARQL templates so the project works without an API key. The `LLM` extension point is deliberately isolated: you can later add an LLM to propose a query, but the app must validate it against an allowlist before execution. Do not execute arbitrary model-generated SPARQL against a production graph.

## Requirements

- Python 3.10–3.12 recommended
- Windows, macOS, or Linux
- 2 GB+ free disk space recommended for the embedding model on first run

## Setup (Windows PowerShell)

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m pip install -e .
python -m pytest -q
```

If PowerShell blocks activation, run:
```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\.venv\Scripts\Activate.ps1
```

## Setup (macOS/Linux)

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m pip install -e .
python -m pytest -q
```

## Run

```bash
python scripts/build_graph.py
uvicorn o2c.api:app --reload
```

Open `http://127.0.0.1:8000/docs`.

### Optional Neo4j backend

The RDF/SPARQL backend works without Neo4j. To enable the additional Cypher endpoint, install and start Docker, then run the Neo4j service from the project root. Set a strong Neo4j password in your shell first; it must be at least 8 characters. Do not commit passwords or other secrets.

Windows PowerShell:

```powershell
$env:NEO4J_PASSWORD = "replace-with-a-strong-password"
docker compose up -d neo4j
python scripts/load_neo4j.py
$env:O2C_ENABLE_NEO4J = "1"
uvicorn o2c.api:app --reload
```

macOS/Linux:

```bash
export NEO4J_PASSWORD="replace-with-a-strong-password"
docker compose up -d neo4j
python scripts/load_neo4j.py
export O2C_ENABLE_NEO4J=1
uvicorn o2c.api:app --reload
```

The defaults connect to `bolt://localhost:7687` with user `neo4j` and database `neo4j`. To use a different connection, set `NEO4J_URI`, `NEO4J_USER`, and `NEO4J_DATABASE` in the same shell before running the loader and API. The `NEO4J_PASSWORD` variable must also be set for both commands. `docker compose up` uses that password to configure the Neo4j container.

> **Warning:** `python scripts/load_neo4j.py` clears all existing nodes and relationships in the configured Neo4j database before loading the project data. Use a dedicated development database; do not point it at data you need to preserve.

With Neo4j enabled and loaded, send questions to `POST /ask/cypher`. For example:

```bash
curl -X POST http://127.0.0.1:8000/ask/cypher \
  -H "Content-Type: application/json" \
  -d "{\"question\":\"Which invoices are overdue?\"}"
```

The endpoint supports the same intent templates as the SPARQL agent, including overdue invoices, delayed deliveries, and customer overdue exposure. It returns the query under `cypher` and includes traceable evidence. Cypher execution is read-only, limited to the known graph labels and relationships, capped at 200 rows, and uses a 5-second transaction timeout. Without `O2C_ENABLE_NEO4J=1`, the endpoint responds with HTTP 503.

### Example API calls

```bash
curl http://127.0.0.1:8000/health
curl -X POST http://127.0.0.1:8000/ask \
  -H "Content-Type: application/json" \
  -d "{\"question\":\"Which invoices are overdue?\"}"
curl -X POST http://127.0.0.1:8000/ask \
  -H "Content-Type: application/json" \
  -d "{\"question\":\"Which deliveries are delayed?\"}"
curl -X POST http://127.0.0.1:8000/evaluate
```

## Architecture

```text
CSV records (SAP / Salesforce / ServiceNow style)
                |
                v
       Source normalization
                |
                v
       RDF graph + OWL ontology
                |
          SHACL validation
                |
       +--------+---------+-----------------------+
       |                  |                       |
       v                  v                       v
 SPARQL business     Text evidence chunks    Optional Neo4j
 queries             sentence embeddings    property graph
       |                  |                       |
       v                  v                       v
 RDF answer          FAISS retrieval         Safe Cypher
       |                  |                  templates
       +--------+---------+-----------------------+
                         |
                         v
                FastAPI /ask, /ask/cypher
                         |
                 evaluation vs plain RAG
```

## Important design choices

1. **Synthetic data only.** The source files are fictional examples, not actual SAP/Salesforce/ServiceNow exports.
2. **Explainability.** Answers include source entity IDs and evidence records.
3. **SPARQL safety.** User text maps to a small set of supported query intents. The API does not run arbitrary SPARQL from user input.
4. **Offline fallback.** If `sentence-transformers` or FAISS cannot be installed on a platform, use `retrieval_mode="lexical"` when creating `O2CService`, or run tests that don't require the optional retrieval stack. The main requirements include both libraries for the intended full experience.
5. **Evaluation honesty.** `evaluation/run_eval.py` reports exact expected-ID match and answer coverage for a small illustrative dataset; it is a smoke-test benchmark, not a statistically significant research result.
6. **Cypher safety.** The optional Neo4j agent executes fixed query templates, validates labels and relationships, enforces a result limit, and uses a read-only database session. It does not execute arbitrary Cypher from user input.

## Extend to real LLM-generated SPARQL

Add a provider in `src/o2c/llm.py` that accepts the user question plus the ontology schema and returns a candidate query. Before execution:
- allow only `SELECT` queries,
- reject `SERVICE`, `LOAD`, `CLEAR`, `DROP`, `INSERT`, `DELETE`, `MOVE`, `COPY`, `ADD`, `WITH`, `USING`,
- enforce query timeout and result limit,
- parse/validate variables and predicates against an allowlist,
- execute only against a read-only graph,
- keep a deterministic fallback and return the generated query in the audit record.

## Project layout

```text
enterprise_semantic_o2c/
├── data/
├── evaluation/
├── ontology/
├── scripts/
├── src/o2c/
├── tests/
├── pyproject.toml
└── requirements.txt
```
