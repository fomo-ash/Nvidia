"""Decisions package supporting TypeSafe Jev & Laya System-1 logic."""

from app.decisions.jev_engine import JevDecisionEngine

# Laya alias for backward compatibility and explicit Laya typing
LayaDecisionEngine = JevDecisionEngine

__all__ = ["JevDecisionEngine", "LayaDecisionEngine"]
