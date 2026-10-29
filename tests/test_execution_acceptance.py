"""An interrupted acceptance run must not resume an uncertain write."""

from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from smoke_execution import validate_resume  # noqa: E402


class ResumeTests(unittest.TestCase):
    def test_recorded_or_unacknowledged_execution_cannot_resume(self):
        for marker in (
            {"execution_requested": True},
            {"execution_id": "recorded-attempt"},
            {"status": "passed"},
        ):
            with self.subTest(marker=marker), self.assertRaises(RuntimeError):
                validate_resume({"fault": {"deployment_uid": "owned"}, **marker}, "owned")

    def test_changed_target_cannot_reuse_previous_acceptance(self):
        with self.assertRaises(RuntimeError):
            validate_resume({"fault": {"deployment_uid": "previous"}}, "new")

    def test_only_unexecuted_denial_cases_may_resume(self):
        receipt = {
            "status": "incomplete",
            "fault": {"deployment_uid": "owned"},
            "cases": [{"case": "rejection"}],
        }
        validate_resume(receipt, "owned")
        self.assertEqual(receipt["cases"], [{"case": "rejection"}])
