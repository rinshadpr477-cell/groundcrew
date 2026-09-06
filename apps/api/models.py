from datetime import datetime, timezone

from sqlalchemy import BigInteger, Boolean, DateTime, Float, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from db import Base


class Issue(Base):
    __tablename__ = "issues"
    __table_args__ = (UniqueConstraint("repo", "number", name="uq_issue_repo_number"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    repo: Mapped[str] = mapped_column(String(200), index=True)
    number: Mapped[int] = mapped_column(Integer, index=True)
    github_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    title: Mapped[str] = mapped_column(Text)
    body: Mapped[str | None] = mapped_column(Text, nullable=True)
    state: Mapped[str] = mapped_column(String(20))
    is_pull_request: Mapped[bool] = mapped_column(Boolean, default=False)
    labels: Mapped[list] = mapped_column(JSON, default=list)
    html_url: Mapped[str] = mapped_column(Text)
    github_created_at: Mapped[datetime] = mapped_column(DateTime)
    github_closed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    raw_json: Mapped[dict] = mapped_column(JSON)
    fetched_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))


class TriageResult(Base):
    __tablename__ = "triage_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    repo: Mapped[str] = mapped_column(String(200), index=True)
    issue_number: Mapped[int] = mapped_column(Integer, index=True)
    issue_title: Mapped[str] = mapped_column(Text)
    category: Mapped[str] = mapped_column(String(50))
    router_confidence: Mapped[float] = mapped_column(Float)
    similar_issue_numbers: Mapped[list] = mapped_column(JSON, default=list)
    attempts: Mapped[int] = mapped_column(Integer)
    suggested_reply: Mapped[str] = mapped_column(Text)
    cited_issue_numbers: Mapped[list] = mapped_column(JSON, default=list)
    critic_approved: Mapped[bool] = mapped_column(Boolean)
    critic_problems: Mapped[list] = mapped_column(JSON, default=list)
    critic_confidence: Mapped[float] = mapped_column(Float)
    status: Mapped[str] = mapped_column(String(20), index=True)
    human_decision: Mapped[str | None] = mapped_column(String(20), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))


class EvalRun(Base):
    __tablename__ = "eval_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    repo: Mapped[str] = mapped_column(String(200), index=True)
    llm_model: Mapped[str] = mapped_column(String(200))
    retrieval_relevance_at_5: Mapped[float | None] = mapped_column(Float, nullable=True)
    retrieval_eval_count: Mapped[int] = mapped_column(Integer, default=0)
    category_accuracy: Mapped[float | None] = mapped_column(Float, nullable=True)
    category_eval_count: Mapped[int] = mapped_column(Integer, default=0)
    approval_rate: Mapped[float | None] = mapped_column(Float, nullable=True)
    avg_attempts: Mapped[float | None] = mapped_column(Float, nullable=True)
    avg_latency_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)
    pipeline_eval_count: Mapped[int] = mapped_column(Integer, default=0)
    details: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))