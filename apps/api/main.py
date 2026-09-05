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
        "created_at": result.created_at.isoformat(),
    }


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/triage/run", status_code=201)
def run_triage_endpoint(payload: RunTriageRequest) -> dict:
    try:
        summary = run_triage(payload.issue_number, verbose=False)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    session = SessionLocal()
    try:
        result = session.get(TriageResult, summary["id"])
        return _serialize(result)
    finally:
        session.close()


@app.get("/triage/queue")
def get_triage_queue() -> list[dict]:
    session = SessionLocal()
    try:
        results = session.scalars(
            select(TriageResult)
            .where(TriageResult.status == "needs_review")
            .order_by(TriageResult.created_at.desc())
        ).all()
        return [_serialize(r) for r in results]
    finally:
        session.close()


@app.get("/triage/{result_id}")
def get_triage_result(result_id: int) -> dict:
    session = SessionLocal()
    try:
        result = session.get(TriageResult, result_id)
        if result is None:
            raise HTTPException(status_code=404, detail=f"Triage result {result_id} not found")
        return _serialize(result)
    finally:
        session.close()


@app.post("/triage/{result_id}/decision")
def record_decision(result_id: int, payload: DecisionRequest) -> dict:
    if payload.decision not in ("approved", "rejected"):
        raise HTTPException(status_code=400, detail="decision must be 'approved' or 'rejected'")

    session = SessionLocal()
    try:
        result = session.get(TriageResult, result_id)
        if result is None:
            raise HTTPException(status_code=404, detail=f"Triage result {result_id} not found")
        result.human_decision = payload.decision
        session.commit()
        session.refresh(result)
        return _serialize(result)
    finally:
        session.close()