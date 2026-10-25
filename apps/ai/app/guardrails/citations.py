"""Guardrail: Validate evidence citations against actual collected evidence snapshots."""

import re
from typing import Sequence
from app.schemas.state import EvidenceReference, Hypothesis

EVIDENCE_TAG_REGEX = re.compile(r"EVD-[0-9a-fA-F]{8}")


class CitationValidatorGuard:
    @staticmethod
    def extract_evidence_ids(text: str) -> set[str]:
        """Extract all EVD-... identifiers from text."""
        return set(EVIDENCE_TAG_REGEX.findall(text))

    @staticmethod
    def validate_hypotheses(
        hypotheses: Sequence[Hypothesis], available_evidence: Sequence[EvidenceReference]
    ) -> list[Hypothesis]:
        """Ensure all supporting_evidence_ids in hypotheses actually exist in available evidence."""
        valid_ids = {evd.id for evd in available_evidence}
        sanitized = []

        for h in hypotheses:
            verified_ids = [eid for eid in h.supporting_evidence_ids if eid in valid_ids]
            embedded_ids = CitationValidatorGuard.extract_evidence_ids(h.cause)
            for eid in embedded_ids:
                if eid in valid_ids and eid not in verified_ids:
                    verified_ids.append(eid)

            sanitized.append(
                Hypothesis(
                    cause=h.cause,
                    confidence=h.confidence if verified_ids else max(0.1, h.confidence * 0.5),
                    supporting_evidence_ids=verified_ids,
                    is_root_cause=h.is_root_cause and bool(verified_ids),
                )
            )

        return sanitized

    @staticmethod
    def sanitize_chat_citations(text: str, available_evidence: Sequence[EvidenceReference]) -> tuple[str, list[str]]:
        """Validate citations in a conversational response, returning clean text and valid cited IDs."""
        valid_ids = {evd.id for evd in available_evidence}
        mentioned_ids = CitationValidatorGuard.extract_evidence_ids(text)
        verified_ids = [eid for eid in mentioned_ids if eid in valid_ids]

        phantom_ids = [eid for eid in mentioned_ids if eid not in valid_ids]
        cleaned_text = text
        for phantom in phantom_ids:
            cleaned_text = cleaned_text.replace(f"[{phantom}]", "").replace(phantom, "[unverified evidence]")

        return cleaned_text, verified_ids
