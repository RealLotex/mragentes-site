#!/usr/bin/env python3
"""Detect newly merged publication contracts without shell parsing Git paths."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Sequence

from scripts.notifications.notify_deployed_note import (
    changed_note_slugs,
    changed_social_drafts,
)


def detect(repo: Path | str, before_sha: str, after_sha: str) -> dict[str, list[str]]:
    return {
        "note_slugs": sorted(changed_note_slugs(repo, before_sha, after_sha)),
        "daily_drafts": sorted(changed_social_drafts(repo, before_sha, after_sha)),
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", default=".")
    parser.add_argument("--before", required=True)
    parser.add_argument("--after", required=True)
    args = parser.parse_args(argv)
    print(
        json.dumps(
            detect(Path(args.repo), args.before, args.after),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
