"""Fixture safety boundaries; no Docker/Kubernetes calls are made."""

import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from scripts import kind_fixture as fixture


GOOD = {
    "spec": {"containers": [{"name": "sample-api", "env": [{"name": "FAIL_MODE", "value": "off"}]}]}
}


class FixtureTests(unittest.TestCase):
    def current(self, template=None):
        return {
            "metadata": {"uid": "original", "resourceVersion": "42"},
            "spec": {"template": copy.deepcopy(GOOD if template is None else template)},
        }

    def baseline(self):
        return {
            "cluster": fixture.CLUSTER,
            "namespace": fixture.NAMESPACE,
            "name": fixture.DEPLOYMENT,
            "uid": "original",
            "template": copy.deepcopy(GOOD),
            "template_hash": fixture.template_hash(GOOD),
        }

    def test_fault_does_not_modify_captured_baseline(self):
        original = copy.deepcopy(GOOD)
        bad = fixture.faulty_template(original)
        self.assertEqual(original, GOOD)
        self.assertEqual(bad["spec"]["containers"][0]["env"][0]["value"], "on")

    def test_patch_atomically_tests_uid_and_resource_version(self):
        with (
            patch.object(fixture, "deployment", return_value=self.current()),
            patch.object(fixture, "load_baseline", return_value=self.baseline()),
            patch.object(fixture, "wait_health"),
            patch.object(fixture, "kubectl") as kubectl,
        ):
            fixture.change(True)
            args = kubectl.call_args_list[0].args
            operations = json.loads(args[-1])
            self.assertEqual(
                operations[0], {"op": "test", "path": "/metadata/uid", "value": "original"}
            )
            self.assertEqual(
                operations[1], {"op": "test", "path": "/metadata/resourceVersion", "value": "42"}
            )
            self.assertEqual(operations[2]["path"], "/spec/template")

    def test_drift_cannot_patch(self):
        drifted = copy.deepcopy(GOOD)
        drifted["metadata"] = {"labels": {"unexpected": "change"}}
        with (
            patch.object(fixture, "deployment", return_value=self.current(drifted)),
            patch.object(fixture, "load_baseline", return_value=self.baseline()),
            patch.object(fixture, "kubectl") as kubectl,
        ):
            with self.assertRaisesRegex(RuntimeError, "drift"):
                fixture.change(False)
            kubectl.assert_not_called()

    def test_already_reset_does_not_create_another_revision(self):
        with (
            patch.object(fixture, "deployment", return_value=self.current()),
            patch.object(fixture, "load_baseline", return_value=self.baseline()),
            patch.object(fixture, "wait_health"),
            patch.object(fixture, "kubectl") as kubectl,
        ):
            fixture.change(False)
            self.assertEqual(kubectl.call_count, 1)
            self.assertEqual(kubectl.call_args.args[0], "rollout")

    def test_baseline_uid_and_hash_are_checked(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "baseline.json"
            with patch.object(fixture, "BASELINE", path):
                bad_uid = self.baseline() | {"uid": "recreated"}
                path.write_text(json.dumps(bad_uid))
                with self.assertRaisesRegex(RuntimeError, "identity"):
                    fixture.load_baseline(self.current())
                path.write_text(json.dumps(self.baseline() | {"template_hash": "tampered"}))
                with self.assertRaisesRegex(RuntimeError, "hash mismatch"):
                    fixture.load_baseline(self.current())

    def test_cluster_identity_mismatch_prevents_deletion(self):
        with tempfile.TemporaryDirectory() as directory:
            receipt = Path(directory) / "ownership.json"
            config = Path(directory) / "kubeconfig"
            config.touch()
            receipt.write_text(json.dumps({"cluster": fixture.CLUSTER, "node_id": "owned"}))
            with (
                patch.object(fixture, "RECEIPT", receipt),
                patch.object(fixture, "KUBECONFIG", config),
                patch.object(fixture, "run", return_value="other") as run,
            ):
                with self.assertRaisesRegex(RuntimeError, "identity"):
                    fixture.down()
                self.assertEqual(run.call_count, 1)
                self.assertEqual(run.call_args.args[0][:2], ["docker", "inspect"])


class ExplicitContextTests(unittest.TestCase):
    def test_kubectl_never_uses_implicit_host_context(self):
        with patch.object(fixture, "run", return_value="ok") as run:
            fixture.kubectl("get", "deployment", "sample-api", capture=True)
        args = run.call_args.args[0]
        self.assertEqual(args[0], str(fixture.KUBECTL))
        self.assertEqual(args[args.index("--kubeconfig") + 1], str(fixture.KUBECONFIG))
        self.assertEqual(args[args.index("--context") + 1], "kind-fixproof-demo")
        self.assertEqual(args[args.index("--namespace") + 1], "fixproof-demo")
