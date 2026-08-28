from __future__ import annotations

import json
import re
from datetime import date
from pathlib import Path
from typing import Any

import pytest

from tests.support.contracts import ROOT, require_target, trace_message

MANIFEST_PATH = ".automation/cloudflare/push-worker.json"


def load_manifest(trace_id: str) -> dict[str, Any]:
    path = require_target(MANIFEST_PATH, trace_id)
    value = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict), trace_message(trace_id, "manifest root must be an object")
    return value


def canonical_script(manifest: dict[str, Any], trace_id: str) -> tuple[Path, str]:
    deployment = manifest.get("deployment")
    assert isinstance(deployment, dict), trace_message(trace_id, "deployment must be an object")
    relative = deployment.get("script")
    assert relative == "cf_worker.js", trace_message(
        trace_id, "connector handoff must use the repository's canonical Worker script"
    )
    path = (ROOT / relative).resolve(strict=False)
    assert path.parent == ROOT and path.is_file(), trace_message(
        trace_id, "canonical Worker script is missing or escapes the repository root"
    )
    return path, path.read_text(encoding="utf-8")


@pytest.mark.trace("CF-MANIFEST-001")
@pytest.mark.red_expected
def test_push_worker_manifest_has_versioned_connector_identity() -> None:
    manifest = load_manifest("CF-MANIFEST-001")
    assert set(manifest) == {
        "manifest_version",
        "deployment",
        "bindings",
        "exports",
        "required_secrets",
        "interface",
    }, trace_message("CF-MANIFEST-001", "manifest top-level contract is not closed")
    assert manifest["manifest_version"] == 1, trace_message(
        "CF-MANIFEST-001", "manifest version must begin at 1"
    )

    deployment = manifest["deployment"]
    assert deployment == {
        "provider": "cloudflare",
        "method": "connector",
        "worker_name": "mragentes-push",
        "script": "cf_worker.js",
        "compatibility_date": deployment.get("compatibility_date"),
    }, trace_message("CF-MANIFEST-001", "deployment identity has unknown or missing fields")
    compatibility_date = date.fromisoformat(deployment["compatibility_date"])
    assert compatibility_date <= date.today(), trace_message(
        "CF-MANIFEST-001", "compatibility_date cannot be in the future"
    )
    canonical_script(manifest, "CF-MANIFEST-001")


@pytest.mark.trace("CF-MANIFEST-002")
@pytest.mark.red_expected
def test_push_worker_manifest_declares_complete_runtime_bindings() -> None:
    manifest = load_manifest("CF-MANIFEST-002")
    assert manifest.get("bindings") == {
        "kv_namespaces": [
            {
                "binding": "PUSH_SUBS",
                "lifecycle": "reuse_or_create",
            }
        ],
        "durable_objects": [
            {
                "binding": "NOTIFICATION_COORDINATOR",
                "class_name": "NotificationCoordinator",
                "storage": "sqlite",
                "lifecycle": "reuse_or_create",
            }
        ],
        "vars": {
            "ENVIRONMENT": "production",
            "ALLOWED_ORIGINS": "https://mragentes.com.ar",
        },
    }, trace_message("CF-MANIFEST-002", "runtime binding declaration differs from production")
    assert manifest.get("exports") == {
        "NotificationCoordinator": {
            "type": "durable-object",
            "storage": "sqlite",
            "state": "created",
        }
    }, trace_message(
        "CF-MANIFEST-002",
        "connector manifest does not declaratively provision the SQLite Durable Object",
    )

    _, source = canonical_script(manifest, "CF-MANIFEST-002")
    assert re.search(r"export\s+class\s+NotificationCoordinator\b", source), trace_message(
        "CF-MANIFEST-002", "declared Durable Object class is not exported by the Worker"
    )
    for binding in ("PUSH_SUBS", "NOTIFICATION_COORDINATOR"):
        assert f"env.{binding}" in source, trace_message(
            "CF-MANIFEST-002", f"declared binding is not consumed by the Worker: {binding}"
        )


@pytest.mark.trace("CF-MANIFEST-003")
@pytest.mark.red_expected
def test_push_worker_manifest_names_secrets_without_values_or_account_identifiers() -> None:
    manifest = load_manifest("CF-MANIFEST-003")
    assert manifest.get("required_secrets") == [
        "API_TOKEN",
        "VAPID_PUBLIC_KEY",
        "VAPID_PRIVATE_KEY",
    ], trace_message("CF-MANIFEST-003", "required Worker secret names are incomplete")

    forbidden_keys = {
        "account_id",
        "api_token",
        "id",
        "namespace_id",
        "secret",
        "secret_value",
        "token",
        "value",
        "zone_id",
    }

    def visit(value: object) -> None:
        if isinstance(value, dict):
            lowered = {str(key).lower() for key in value}
            assert not lowered.intersection(forbidden_keys), trace_message(
                "CF-MANIFEST-003", "manifest embeds an identifier or secret-value field"
            )
            for child in value.values():
                visit(child)
        elif isinstance(value, list):
            for child in value:
                visit(child)

    visit(manifest)
    serialized = json.dumps(manifest, ensure_ascii=False, sort_keys=True)
    assert "/home/" not in serialized and "wrangler" not in serialized.lower(), trace_message(
        "CF-MANIFEST-003", "manifest depends on a local account, path, or Wrangler"
    )
    assert not re.search(
        r"(?:Bearer\s+[A-Za-z0-9._-]{12,}|ghp_[A-Za-z0-9]{20,}|"
        r"github_pat_[A-Za-z0-9_]{20,}|sk-[A-Za-z0-9]{20,})",
        serialized,
    ), trace_message("CF-MANIFEST-003", "manifest contains secret-like material")


@pytest.mark.trace("CF-MANIFEST-004")
@pytest.mark.red_expected
def test_push_worker_manifest_interface_matches_worker_and_site_clients() -> None:
    manifest = load_manifest("CF-MANIFEST-004")
    interface = manifest.get("interface")
    assert interface == {
        "site_origin": "https://mragentes.com.ar",
        "worker_origin": "https://mragentes-push.rosichmarcos.workers.dev",
        "endpoints": {
            "subscribe": {
                "method": "POST",
                "path": "/api/subscribe/",
                "authentication": "site_origin",
            },
            "unsubscribe": {
                "method": "POST",
                "path": "/api/unsubscribe/",
                "authentication": "site_origin",
            },
            "send": {
                "method": "POST",
                "path": "/api/send/",
                "authentication": "bearer",
            },
        },
    }, trace_message("CF-MANIFEST-004", "public Worker interface differs from production")

    _, source = canonical_script(manifest, "CF-MANIFEST-004")
    for endpoint in interface["endpoints"].values():
        assert f'"{endpoint["path"]}"' in source, trace_message(
            "CF-MANIFEST-004", f"manifest endpoint is not routed by Worker: {endpoint['path']}"
        )
    assert f'const SITE_ORIGIN = "{interface["site_origin"]}"' in source

    client_sources = "\n".join(
        [
            require_target("layouts/_default/baseof.html", "CF-MANIFEST-004").read_text(
                encoding="utf-8"
            ),
            require_target("static/sw.js", "CF-MANIFEST-004").read_text(encoding="utf-8"),
        ]
    )
    assert interface["worker_origin"] in client_sources, trace_message(
        "CF-MANIFEST-004", "site clients do not target the declared Worker origin"
    )
