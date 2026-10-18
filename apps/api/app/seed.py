from sqlalchemy import select
from app.db.session import SessionLocal
from app.models.domain import Incident
from app.services.recommendations import audit


def main():
    db = SessionLocal()
    try:
        if not db.scalar(select(Incident)):
            incident = Incident(
                title="Demo API error-rate spike",
                severity="high",
                summary="Reproducible local incident for the FixProof demo.",
            )
            db.add(incident)
            db.flush()
            audit(db, "incident", incident.id, "created", {"source": "demo-seed"})
            db.commit()
    finally:
        db.close()


if __name__ == "__main__":
    main()
