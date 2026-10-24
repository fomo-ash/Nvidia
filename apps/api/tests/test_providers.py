import pytest
from pydantic import ValidationError
from sqlalchemy import select

from app.core.config import Settings
from app.models.domain import Recommendation
from app.services.investigations import MockInvestigationProvider, Proposal
from app.services.recommendations import investigate


def test_unknown_provider_fails_closed():
    with pytest.raises(ValidationError):
        Settings(llm_provider="unconfigured-external-provider", _env_file=None)


@pytest.mark.parametrize("change", ["action", "target", "parameters", "evidence"])
def test_provider_output_is_bounded_and_schema_validated(change):
    payload = MockInvestigationProvider().investigate().model_dump()
    if change == "evidence":
        payload[change] = []
    elif change == "parameters":
        payload[change] = {"strategy": "rolling", "reason": "demo", "shell": "anything"}
    else:
        payload[change] = "unsupported"
    with pytest.raises(ValidationError):
        Proposal.model_validate(payload)


def test_invalid_provider_does_not_supersede_an_existing_proposal(database, proposal):
    class InvalidProvider:
        def investigate(self):
            return {"action": "unsupported"}

    factory, _, _ = database
    with factory() as db:
        previous = db.scalar(select(Recommendation))
        with pytest.raises(ValidationError):
            investigate(db, previous.incident_id, InvalidProvider())
        db.rollback()
        db.refresh(previous)
        assert previous.status == "proposed"
