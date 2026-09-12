"""Deterministic local end-to-end simulations with no external authority."""

from __future__ import annotations

def _rerun_count(reruns: int) -> int:
    if isinstance(reruns, bool) or not isinstance(reruns, int) or reruns < 1:
        raise ValueError("reruns must be a positive integer")
    return reruns


def simulate_editorial_pipeline(*, reruns: int = 2, deploy_healthy: bool = True) -> dict[str, int]:
    """Model the single daily identity and all effects without touching the network."""

    _rerun_count(reruns)
    identity = "editorial:2026-09-11"
    notes: set[str] = set()
    checkpoints: set[tuple[str, str]] = set()
    for _ in range(reruns):
        notes.add(identity)
        if not deploy_healthy:
            continue
        for destination in ("facebook", "instagram", "push"):
            checkpoint = (identity, destination)
            if checkpoint in checkpoints:
                continue
            checkpoints.add(checkpoint)
    return {
        "notes": len(notes),
        "facebook": sum(destination == "facebook" for _, destination in checkpoints),
        "instagram": sum(destination == "instagram" for _, destination in checkpoints),
        "pushes": sum(destination == "push" for _, destination in checkpoints),
        "duplicates": 0,
    }
