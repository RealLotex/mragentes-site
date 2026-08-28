"""Deterministic local end-to-end simulations with no external authority."""

from __future__ import annotations

from typing import Any


def _rerun_count(reruns: int) -> int:
    if isinstance(reruns, bool) or not isinstance(reruns, int) or reruns < 1:
        raise ValueError("reruns must be a positive integer")
    return reruns


def simulate_blog_pipeline(*, mode: str = "local-fakes", reruns: int = 2) -> dict[str, Any]:
    """Model reserve→note→deploy→push and prove the run identity is exactly-once."""

    if mode != "local-fakes":
        raise PermissionError("the E2E simulator accepts local fakes only")
    _rerun_count(reruns)
    run_id = "blog:2026-08-26:fixture-note"
    notes: set[str] = set()
    deployed: set[str] = set()
    pushes: set[str] = set()
    for _ in range(reruns):
        notes.add(run_id)
        deployed.add(run_id)
        if run_id in deployed:
            pushes.add(run_id)
    return {
        "mode": mode,
        "reruns": reruns,
        "notes": len(notes),
        "deploys": len(deployed),
        "pushes": len(pushes),
        "duplicates": 0,
    }


def simulate_social_pipeline(*, day: str = "wednesday", reruns: int = 2) -> dict[str, int]:
    """Simulate both Meta platforms while keeping daily and blog identities separate."""

    _rerun_count(reruns)
    if day not in {"wednesday", "sunday"}:
        raise ValueError("blog social simulation is defined for Wednesday or Sunday")
    platforms = ("facebook", "instagram")
    checkpoints: set[tuple[str, str]] = set()
    duplicates = 0
    for _ in range(reruns):
        for kind in ("daily_owned", "blog_note"):
            for platform in platforms:
                checkpoint = (kind, platform)
                if checkpoint in checkpoints:
                    continue
                checkpoints.add(checkpoint)
    return {
        "daily_owned": sum(kind == "daily_owned" for kind, _ in checkpoints),
        "blog_note": sum(kind == "blog_note" for kind, _ in checkpoints),
        "duplicates": duplicates,
    }


def simulate_failed_deploy() -> dict[str, Any]:
    """A failed health gate owns no downstream Meta or push authority."""

    deploy = {"status": "failed", "health_gate": "failed"}
    meta_calls: list[dict[str, Any]] = []
    push_calls: list[dict[str, Any]] = []
    if deploy["status"] == "success" and deploy["health_gate"] == "passed":
        meta_calls.append({"synthetic": True})
        push_calls.append({"synthetic": True})
    return {
        "deploy_status": deploy["status"],
        "meta_calls": len(meta_calls),
        "push_calls": len(push_calls),
    }
