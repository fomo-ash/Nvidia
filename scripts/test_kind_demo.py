"""Check the trusted baseline refuses faulty or mismatched targets."""

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import kind_demo


def deployment(fail_mode=None, uid="uid-1"):
    container = {"name": "sample-api", "image": "fixproof/sample-api:local"}
    if fail_mode:
        container["env"] = [{"name": "FAIL_MODE", "value": fail_mode}]
    return {
        "metadata": {
            "uid": uid,
            "resourceVersion": "1",
            "annotations": {"deployment.kubernetes.io/revision": "1"},
        },
        "spec": {
            "template": {
                "metadata": {"labels": {"app": "sample-api"}},
                "spec": {"containers": [container]},
            }
        },
    }


class BaselineTest(unittest.TestCase):
    def test_refuses_faulty_capture(self):
        with (
            tempfile.TemporaryDirectory() as directory,
            patch.object(kind_demo, "BASELINE", Path(directory) / "baseline.json"),
        ):
            with self.assertRaisesRegex(RuntimeError, "faulty"):
                kind_demo.save_baseline(deployment("on"))
            self.assertFalse(kind_demo.BASELINE.exists())

    def test_rejects_uid_or_hash_drift(self):
        with (
            tempfile.TemporaryDirectory() as directory,
            patch.object(kind_demo, "BASELINE", Path(directory) / "baseline.json"),
        ):
            current = deployment()
            baseline = kind_demo.save_baseline(current)
            self.assertEqual(
                kind_demo.load_baseline(current)["template_hash"], baseline["template_hash"]
            )
            with self.assertRaisesRegex(RuntimeError, "UID changed"):
                kind_demo.load_baseline(deployment(uid="another-uid"))
            baseline["template"]["spec"]["containers"][0]["image"] = "changed"
            kind_demo.BASELINE.write_text(json.dumps(baseline), encoding="utf-8")
            with self.assertRaisesRegex(RuntimeError, "hash mismatch"):
                kind_demo.load_baseline(current)


if __name__ == "__main__":
    unittest.main()
