"""Read-only Kubernetes access for the registered demo workload."""

import hashlib
import json
import os
import re
from typing import Any

import httpx

from app.config import settings


class BoundedClient(httpx.AsyncClient):
    async def get(self, url, **kwargs):
        async with self.stream("GET", url, **kwargs) as response:
            response.raise_for_status()
            parts, size = [], 0
            async for part in response.aiter_bytes():
                size += len(part)
                if size > 262144:
                    raise ValueError("Kubernetes response exceeds the read bound")
                parts.append(part)
            return httpx.Response(
                response.status_code, content=b"".join(parts), request=response.request
            )


ANSI_REGEX = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")


def strip_ansi(value: str) -> str:
    return ANSI_REGEX.sub("", value)


class KubernetesClient:
    def __init__(self) -> None:
        self.api_url = settings.KUBERNETES_API_URL.rstrip("/")
        self.token_path = settings.KUBERNETES_TOKEN_PATH
        self.ca_cert_path = settings.KUBERNETES_CA_CERT_PATH

    def _require_target(self, namespace: str, deployment_name: str | None = None) -> None:
        if namespace != settings.KUBERNETES_NAMESPACE:
            raise ValueError("Namespace is outside the registered target")
        if deployment_name is not None and deployment_name != "sample-api":
            raise ValueError("Deployment is outside the registered target")

    def _connection(self) -> tuple[dict[str, str], str]:
        if not os.path.isfile(self.ca_cert_path):
            raise RuntimeError("Kubernetes CA certificate is unavailable")
        with open(self.token_path, encoding="utf-8") as stream:
            token = stream.read().strip()
        if not token:
            raise RuntimeError("Kubernetes credential is empty")
        return {"Authorization": f"Bearer {token}"}, self.ca_cert_path

    async def get_deployment_status(
        self, namespace: str = "fixproof-demo", deployment_name: str = "sample-api"
    ) -> dict[str, Any]:
        self._require_target(namespace, deployment_name)
        headers, verify = self._connection()
        url = f"{self.api_url}/apis/apps/v1/namespaces/{namespace}/deployments/{deployment_name}"
        async with BoundedClient(verify=verify, timeout=5.0) as client:
            response = await client.get(url, headers=headers)
            response.raise_for_status()
        if (
            settings.KUBERNETES_TARGET_UID
            and data_uid(response.json()) != settings.KUBERNETES_TARGET_UID
        ):
            raise ValueError("Deployment UID differs from the registered target")
        data = response.json()
        spec = data.get("spec", {})
        status = data.get("status", {})
        template = spec.get("template", {})
        template_hash = hashlib.sha256(json.dumps(template, sort_keys=True).encode()).hexdigest()
        containers = template.get("spec", {}).get("containers", [])
        container = containers[0] if containers else {}
        fail_mode = next(
            (
                env.get("value")
                for env in container.get("env", [])
                if env.get("name") == "FAIL_MODE"
            ),
            None,
        )
        headers, verify = self._connection()
        async with BoundedClient(verify=verify, timeout=5.0) as client:
            replicas = await client.get(
                f"{self.api_url}/apis/apps/v1/namespaces/{namespace}/replicasets",
                headers=headers,
                params={"labelSelector": "app=sample-api", "limit": 100},
            )
            replicas.raise_for_status()
            history = [
                item
                for item in replicas.json().get("items", [])
                if any(
                    owner.get("uid") == data["metadata"]["uid"]
                    for owner in item.get("metadata", {}).get("ownerReferences", [])
                )
            ]
            replica_ids = {item["metadata"]["uid"] for item in history}
            pods = await client.get(
                f"{self.api_url}/api/v1/namespaces/{namespace}/pods",
                headers=headers,
                params={"labelSelector": "app=sample-api", "limit": 100},
            )
            pods.raise_for_status()
            owned_pods = [
                item
                for item in pods.json().get("items", [])
                if any(
                    owner.get("uid") in replica_ids
                    for owner in item.get("metadata", {}).get("ownerReferences", [])
                )
            ]
        return {
            "revision": data.get("metadata", {})
            .get("annotations", {})
            .get("deployment.kubernetes.io/revision"),
            "generation": data.get("metadata", {}).get("generation"),
            "observed_generation": status.get("observedGeneration"),
            "replicasets": [
                {
                    "uid": item["metadata"]["uid"],
                    "name": item["metadata"]["name"],
                    "replicas": item.get("spec", {}).get("replicas", 0),
                    "revision": item["metadata"]
                    .get("annotations", {})
                    .get("deployment.kubernetes.io/revision"),
                }
                for item in history[:10]
            ],
            "pods": [
                {
                    "uid": item["metadata"]["uid"],
                    "name": item["metadata"]["name"],
                    "phase": item.get("status", {}).get("phase"),
                    "created_at": item["metadata"].get("creationTimestamp"),
                    "container_statuses": [
                        {
                            "name": c.get("name"),
                            "ready": c.get("ready"),
                            "restarts": c.get("restartCount"),
                        }
                        for c in item.get("status", {}).get("containerStatuses", [])[:5]
                    ],
                }
                for item in owned_pods[:10]
            ],
            "namespace": namespace,
            "deployment_name": deployment_name,
            "uid": data.get("metadata", {}).get("uid"),
            "resource_version": data.get("metadata", {}).get("resourceVersion"),
            "replicas_desired": spec.get("replicas", 1),
            "replicas_ready": status.get("readyReplicas", 0),
            "replicas_available": status.get("availableReplicas", 0),
            "image": container.get("image", ""),
            "env_vars": {"FAIL_MODE": fail_mode} if fail_mode is not None else {},
            "template_hash": template_hash,
            "conditions": [
                {
                    "type": c.get("type"),
                    "status": c.get("status"),
                    "reason": c.get("reason"),
                    "message": (c.get("message") or "")[:500],
                    "last_transition_time": c.get("lastTransitionTime"),
                }
                for c in status.get("conditions", [])[:10]
            ],
        }

    async def get_pod_events(
        self, namespace: str = "fixproof-demo", limit: int = 20
    ) -> list[dict[str, Any]]:
        self._require_target(namespace)
        target = await self.get_deployment_status(namespace, "sample-api")
        allowed = {target["uid"]} | {item["uid"] for item in target["replicasets"] + target["pods"]}
        if not 1 <= limit <= 20:
            raise ValueError("Event limit must be between 1 and 20")
        headers, verify = self._connection()
        url = f"{self.api_url}/api/v1/namespaces/{namespace}/events"
        async with BoundedClient(verify=verify, timeout=5.0) as client:
            response = await client.get(url, headers=headers, params={"limit": 100})
            response.raise_for_status()
        return [
            {
                "type": item.get("type"),
                "reason": item.get("reason"),
                "message": (item.get("message") or "")[:500],
                "count": item.get("count"),
                "last_timestamp": item.get("lastTimestamp"),
                "involved_object": {
                    "kind": item.get("involvedObject", {}).get("kind"),
                    "name": item.get("involvedObject", {}).get("name"),
                },
            }
            for item in response.json().get("items", [])
            if item.get("involvedObject", {}).get("uid") in allowed
        ][:limit]

    async def get_pod_logs(
        self,
        namespace: str = "fixproof-demo",
        deployment_name: str = "sample-api",
        lines: int = 100,
    ) -> dict[str, Any]:
        self._require_target(namespace, deployment_name)
        if not 1 <= lines <= 100:
            raise ValueError("Log line limit must be between 1 and 100")
        target = await self.get_deployment_status(namespace, deployment_name)
        allowed_pods = {item["uid"] for item in target["pods"]}
        headers, verify = self._connection()
        pods_url = f"{self.api_url}/api/v1/namespaces/{namespace}/pods"
        async with BoundedClient(verify=verify, timeout=5.0) as client:
            pods = await client.get(
                pods_url, headers=headers, params={"labelSelector": f"app={deployment_name}"}
            )
            pods.raise_for_status()
            items = [
                item
                for item in pods.json().get("items", [])
                if item["metadata"]["uid"] in allowed_pods
            ]
            items.sort(key=lambda item: item["metadata"].get("creationTimestamp", ""), reverse=True)
            if not items:
                raise RuntimeError("No owned sample pod is available for log collection")
            pod_name = items[0]["metadata"]["name"]
            log_url = f"{pods_url}/{pod_name}/log"
            logs = await client.get(
                log_url,
                headers=headers,
                params={"tailLines": lines, "limitBytes": 16384, "timestamps": "true"},
            )
            logs.raise_for_status()
        return {
            "pod_name": pod_name,
            "pod_uid": items[0]["metadata"]["uid"],
            "deployment_uid": target["uid"],
            "timestamps": True,
            "lines": [
                line[:500] for line in strip_ansi(logs.text[:16384]).splitlines() if line.strip()
            ][:lines],
        }

    async def patch_deployment_env(
        self, namespace: str, deployment_name: str, env_updates: dict[str, str]
    ) -> bool:
        """Execution is disabled until exact approval and preflight are integrated."""
        self._require_target(namespace, deployment_name)
        return False


def data_uid(data):
    return data.get("metadata", {}).get("uid")
