"""Persist source billing rows and an immutable calculated report in one transaction."""

from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import func, select

from app.models.domain import CostAnalysis, CostRecord
from app.schemas.lifecycle import CostAnalysisOut, CostSourceIn
from app.services.costs import SAMPLE_COSTS, summary
from app.services.recommendations import audit


def create_analysis(db, payload, actor):
    sources = (
        payload.records
        if payload.records is not None
        else [CostSourceIn.model_validate(row) for row in SAMPLE_COSTS]
    )
    rows = [row.model_dump() for row in sources]
    try:
        report = summary(
            rows, current_period=payload.current_period, previous_period=payload.previous_period
        )
    except ValueError as error:
        raise HTTPException(422, str(error)) from None
    item = CostAnalysis(
        current_period=payload.current_period,
        previous_period=payload.previous_period,
        report=report,
        mode="synthetic",
        currency="USD",
    )
    db.add(item)
    db.flush()
    for row in rows:
        db.add(CostRecord(analysis_id=item.id, **{**row, "cost": Decimal(str(row["cost"]))}))
    db.flush()
    audit(
        db,
        "cost_analysis",
        item.id,
        "created",
        {"source_count": len(rows), "mode": "synthetic", "currency": "USD"},
        actor.id,
    )
    return analysis_out(db, item)


def analysis_out(db, item):
    return CostAnalysisOut(
        **item.report,
        id=item.id,
        created_at=item.created_at,
        source_count=db.scalar(
            select(func.count()).select_from(CostRecord).where(CostRecord.analysis_id == item.id)
        ),
    )
