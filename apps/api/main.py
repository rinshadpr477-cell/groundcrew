from contextlib import asynccontextmanager
import os

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy import select

from agent_pipeline import run_triage
from db import SessionLocal
from models import TriageResult

load_dotenv()
ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "http://localhost:3000").split(",")


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield


app = FastAPI(title="Groundcrew API", version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class RunTriageRequest(BaseModel):
    issue_number: int


class DecisionRequest(BaseModel):
    decision: str  # "approved" | "rejected"


def _serialize(result: TriageResult) -> dict:
    return {
        "id": result.id,
        "repo": result.repo,
        "issue_number": result.issue_number,
        "issue_title": result.issue_title,
        "category": result.category,
        "router_confidence": result.router_confidence,
        "similar_issue_numbers": result.similar_issue_numbers,
        "attempts": result.attempts,
        "suggested_reply": result.suggested_reply,
        "cited_issue_numbers": result.cited_issue_numbers,
        "critic_approved": result.critic_approved,
        "critic_problems": result.critic_problems,
        "critic_confidence": result.critic_confidence,
        "status": result.status,
        "human_decision": result.human_decision,
        "timings": result.timings,
        "created_at": result.created_at.isoformat() if result.created_at else None,
    }


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/triage/run", status_code=201)
def run_triage_endpoint(payload: RunTriageRequest) -> dict:
    try:
        return run_triage(payload.issue_number, verbose=False)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/triage/queue")
def get_triage_queue() -> list[dict]:
    with SessionLocal() as session:
        results = session.execute(
            select(TriageResult).order_by(TriageResult.created_at.desc())
        ).scalars().all()
        return [_serialize(r) for r in results]


@app.get("/triage/{result_id}")
def get_triage_result(result_id: int) -> dict:
    with SessionLocal() as session:
        result = session.get(TriageResult, result_id)
        if result is None:
            raise HTTPException(status_code=404, detail="Triage result not found")
        return _serialize(result)


@app.post("/triage/{result_id}/decision")
def record_decision(result_id: int, payload: DecisionRequest) -> dict:
    if payload.decision not in ("approved", "rejected"):
        raise HTTPException(status_code=400, detail="decision must be 'approved' or 'rejected'")
    with SessionLocal() as session:
        result = session.get(TriageResult, result_id)
        if result is None:
            raise HTTPException(status_code=404, detail="Triage result not found")
        result.human_decision = payload.decision
        session.commit()
        session.refresh(result)
        return _serialize(result)