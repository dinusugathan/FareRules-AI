import os
import json
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from engine.agent import FareRulesAgent
from engine.models import FareRulesAgentResponse
from evals.run_evals import run_farerules_benchmark

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
RULES_PATH = os.path.join(BASE_DIR, "data", "fare_rules_catalog.json")
FEES_PATH = os.path.join(BASE_DIR, "data", "agency_fees.json")
EVAL_PATH = os.path.join(BASE_DIR, "evals", "benchmark_report.json")
STATIC_DIR = os.path.join(BASE_DIR, "web")

app = FastAPI(
    title="FareRules AI — GDS Tariff & Voluntary Refund RAG Engine",
    version="1.0.0",
    description="Akbar Travels Production RAG engine for multi-carrier fare rules, GDS voluntary cancellation slabs, and deterministic refund calculation."
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize Agent
agent = FareRulesAgent(RULES_PATH, FEES_PATH)

class FareQueryRequest(BaseModel):
    query: str

@app.get("/api/health")
def health_check():
    return {
        "status": "healthy",
        "service": "FareRules AI",
        "agency": "Akbar Travels India Pvt Ltd",
        "indexed_rules": len(agent.rules),
        "total_tariff_chunks": len(agent.chunks)
    }

@app.post("/api/chat", response_model=FareRulesAgentResponse)
def handle_fare_query(payload: FareQueryRequest):
    if not payload.query or not payload.query.strip():
        raise HTTPException(status_code=400, detail="Query cannot be empty.")
    return agent.process_query(payload.query.strip())

@app.get("/api/rules")
def get_rules():
    with open(RULES_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

@app.get("/api/agency-fees")
def get_agency_fees():
    with open(FEES_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

@app.get("/api/evals")
def get_evals():
    if not os.path.exists(EVAL_PATH):
        return run_farerules_benchmark(RULES_PATH, FEES_PATH, output_report_path=EVAL_PATH)
    with open(EVAL_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

@app.post("/api/evals/run")
def trigger_evals():
    return run_farerules_benchmark(RULES_PATH, FEES_PATH, output_report_path=EVAL_PATH)

# Serve Web Frontend
os.makedirs(STATIC_DIR, exist_ok=True)
app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")

if __name__ == "__main__":
    import uvicorn
    # Project 3 runs on port 8002
    uvicorn.run("main:app", host="127.0.0.1", port=8002, reload=True)
