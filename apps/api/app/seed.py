from sqlalchemy import select
from app.db.session import SessionLocal
from app.models.domain import Incident
def main():
    db=SessionLocal()
    try:
        if not db.scalar(select(Incident)):
            db.add(Incident(title="Demo API error-rate spike", severity="high", summary="Reproducible local incident for the FixProof demo.")); db.commit()
    finally: db.close()
if __name__ == "__main__": main()
