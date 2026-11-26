"""Stores every completed test so the owner can review results later (admin-only).

Uses PostgreSQL when DATABASE_URL is set (e.g. a free Neon database - survives Render redeploys),
otherwise a local SQLite file next to the analytics database.
"""

import json
import os
from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, Integer, MetaData, String, Table, Text, create_engine, delete, \
    desc, func, select

from . import config


def _url() -> str:
    url = os.getenv("DATABASE_URL", "").strip()
    if not url:
        return f"sqlite:///{config.DB_PATH.with_name('results.db')}"
    # Neon/Render give postgres:// or postgresql:// - use the psycopg 3 driver
    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://"):]
    if url.startswith("postgresql://"):
        url = "postgresql+psycopg://" + url[len("postgresql://"):]
    return url


engine = create_engine(_url(), pool_pre_ping=True, future=True)
metadata = MetaData()

results = Table(
    "test_results", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("created_at", DateTime(timezone=True), nullable=False, index=True),
    Column("distinct_id", String(200), nullable=False, index=True),
    Column("test_id", String(64), nullable=False, index=True),
    Column("test_title", String(200), nullable=False),
    Column("headline", String(300)),
    Column("city", String(120)),
    Column("country", String(120)),
    Column("ai_used", Boolean, default=False),
    Column("answers", Text, nullable=False),    # JSON
    Column("response", Text, nullable=False),   # JSON: exactly what the user was shown
)
metadata.create_all(engine)


def backend_name() -> str:
    return engine.dialect.name  # "postgresql" or "sqlite"


def save(distinct_id: str, test_id: str, answers: dict, response: dict, place: dict) -> int:
    with engine.begin() as conn:
        r = conn.execute(results.insert().values(
            created_at=datetime.now(timezone.utc),
            distinct_id=distinct_id[:200],
            test_id=test_id,
            test_title=response.get("title", test_id)[:200],
            headline=(response.get("result", {}).get("headline") or "")[:300],
            city=(place.get("city") or "")[:120] or None,
            country=(place.get("country") or "")[:120] or None,
            ai_used=response.get("paragraph_source") == "llm",
            answers=json.dumps(answers, ensure_ascii=False),
            response=json.dumps(response, ensure_ascii=False, default=str),
        ))
        return int(r.inserted_primary_key[0])


def summary() -> dict:
    with engine.connect() as conn:
        rows = conn.execute(select(results.c.test_id, results.c.test_title, func.count().label("n"),
                                   func.count(func.distinct(results.c.distinct_id)).label("people"))
                            .group_by(results.c.test_id, results.c.test_title)).all()
        total = conn.execute(select(func.count()).select_from(results)).scalar_one()
    return {"total": total, "storage": backend_name(),
            "per_test": [{"test_id": r.test_id, "title": r.test_title, "results": r.n, "people": r.people}
                         for r in rows]}


def list_results(test_id: str | None, limit: int, offset: int) -> list[dict]:
    q = select(results.c.id, results.c.created_at, results.c.distinct_id, results.c.test_id, results.c.test_title,
               results.c.headline, results.c.city, results.c.country, results.c.ai_used)
    if test_id:
        q = q.where(results.c.test_id == test_id)
    q = q.order_by(desc(results.c.id)).limit(limit).offset(offset)
    with engine.connect() as conn:
        return [{**dict(r._mapping), "created_at": r.created_at.isoformat() if r.created_at else None}
                for r in conn.execute(q)]


def get(result_id: int) -> dict | None:
    with engine.connect() as conn:
        r = conn.execute(select(results).where(results.c.id == result_id)).first()
    if not r:
        return None
    d = dict(r._mapping)
    d["created_at"] = d["created_at"].isoformat() if d["created_at"] else None
    d["answers"] = json.loads(d["answers"])
    d["response"] = json.loads(d["response"])
    return d


def remove(result_id: int) -> bool:
    with engine.begin() as conn:
        return conn.execute(delete(results).where(results.c.id == result_id)).rowcount > 0
