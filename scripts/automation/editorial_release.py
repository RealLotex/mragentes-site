#!/usr/bin/env python3
"""Publish one researched news story from a small JSON file and a local image.

The model supplies facts and prose. This command owns the repeatable packaging,
validation, Git branch and pull request. GitHub Actions owns deployment and Meta.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
from datetime import UTC, date, datetime
from pathlib import Path
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[2]


def _ensure_runtime() -> None:
    """Use one cached, locked Python environment when Linux lacks a renderer dependency."""
    if all(importlib.util.find_spec(name) for name in ("PIL", "fontTools", "brotli", "yaml")):
        return
    cache_root = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache"))
    runtime = cache_root / "mragentes" / "editorial-venv"
    runtime.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    python = runtime / "bin" / "python"
    lock = ROOT / "requirements-test.lock.txt"
    marker = runtime / ".lock-sha256"
    fingerprint = hashlib.sha256(lock.read_bytes()).hexdigest()
    if not python.exists():
        subprocess.run([sys.executable, "-m", "venv", str(runtime)], check=True)  # noqa: S603
    if not marker.exists() or marker.read_text(encoding="ascii").strip() != fingerprint:
        subprocess.run(  # noqa: S603
            [str(python), "-m", "pip", "install", "--require-hashes", "-r", str(lock)],
            check=True,
        )
        marker.write_text(fingerprint + "\n", encoding="ascii")
    if Path(sys.prefix).resolve() == runtime.resolve():
        raise RuntimeError("locked editorial runtime is missing a required package")
    os.execv(  # noqa: S606
        str(python), [str(python), str(Path(__file__).resolve()), *sys.argv[1:]]
    )


if __name__ == "__main__":
    _ensure_runtime()
if __package__ in (None, ""):
    sys.path.insert(0, str(ROOT))

from PIL import Image  # noqa: E402

from scripts.automation.blog_guard import (  # noqa: E402
    blog_run_id,
    build_front_matter,
    portable_slug,
)
from scripts.automation.news_queue import (  # noqa: E402
    load_queue,
    stable_news_id,
    validate_news_item,
)

REPOSITORY = "RealLotex/mragentes-site"
TIMEZONE = ZoneInfo("America/Argentina/Cordoba")
REQUIRED = {"title", "summary", "body", "image_alt", "source_url", "source_name", "source_date"}
OPTIONAL = {"related_sources", "tags", "image_credit"}


def _run(command: list[str], cwd: Path, *, quiet: bool = False) -> str:
    result = subprocess.run(command, cwd=cwd, capture_output=True, text=True)  # noqa: S603
    if result.returncode:
        detail = result.stderr.strip() or result.stdout.strip() or "unknown error"
        raise RuntimeError(f"{command[0]} {command[1]} failed: {detail}")
    return "" if quiet else result.stdout.strip()


def _plain(value: object, field: str, maximum: int) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > maximum:
        raise ValueError(f"{field} must be nonempty text of at most {maximum} characters")
    if any(ord(character) < 32 and character not in "\n\t" for character in value):
        raise ValueError(f"{field} contains a control character")
    return value.strip()


def _public_https(value: object, field: str) -> str:
    url = _plain(value, field, 2048)
    split = urlsplit(url)
    if split.scheme != "https" or not split.hostname or split.username or split.password:
        raise ValueError(f"{field} must be a public HTTPS URL")
    if split.hostname.casefold() in {"localhost", "127.0.0.1"}:
        raise ValueError(f"{field} must be a public HTTPS URL")
    return url


def validate_submission(submission: dict, local_day: date) -> dict:
    """Reject stale, uncited or underspecified input before touching Git."""
    if (
        not isinstance(submission, dict)
        or set(submission) - REQUIRED - OPTIONAL
        or REQUIRED - set(submission)
    ):
        raise ValueError("submission fields do not match the editorial input contract")
    result = dict(submission)
    for field, maximum in (
        ("title", 110),
        ("summary", 160),
        ("body", 12000),
        ("image_alt", 180),
        ("source_name", 120),
    ):
        result[field] = _plain(result[field], field, maximum)
    result["source_url"] = _public_https(result["source_url"], "source_url")
    if result["source_url"] not in result["body"]:
        raise ValueError("the body must cite its primary source URL")
    try:
        published = date.fromisoformat(_plain(result["source_date"], "source_date", 10))
    except ValueError as exc:
        raise ValueError("source_date must use YYYY-MM-DD") from exc
    if not 0 <= (local_day - published).days <= 2:
        raise ValueError("the news event must be recent (today or the prior two days)")
    result["source_date"] = published.isoformat()
    related = result.get("related_sources", [])
    if not isinstance(related, list) or len(related) > 3:
        raise ValueError("related_sources must contain at most three URLs")
    result["related_sources"] = [_public_https(value, "related_sources") for value in related]
    if len(set([result["source_url"], *result["related_sources"]])) != 1 + len(related):
        raise ValueError("source URLs must be distinct")
    tags = result.get("tags", ["ia", "actualidad"])
    if not isinstance(tags, list) or not 1 <= len(tags) <= 5:
        raise ValueError("tags must contain one to five terms")
    result["tags"] = [_plain(tag, "tag", 40) for tag in tags]
    credit = result.get("image_credit")
    if credit is not None:
        if not isinstance(credit, dict) or set(credit) != {"source_url", "creator", "license_url"}:
            raise ValueError("image_credit requires source_url, creator and license_url")
        result["image_credit"] = {
            "source_url": _public_https(credit["source_url"], "image_credit.source_url"),
            "creator": _plain(credit["creator"], "image_credit.creator", 120),
            "license_url": _public_https(credit["license_url"], "image_credit.license_url"),
        }
    return result


def _quoted(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


def build_note(submission: dict, local_day: date, slug: str, image_name: str) -> str:
    """Make the Hugo note from prose, with no front matter left to the model."""
    front = build_front_matter(
        title=submission["title"],
        local_date=local_day.isoformat(),
        description=submission["summary"],
        image=f"/images/stock/{image_name}",
        image_alt=submission["image_alt"],
        tags=submission.get("tags", ["ia", "actualidad"]),
        pillar="control-y-gobernanza"
        if "seguridad" in submission.get("tags", [])
        else "automatizacion-practica",
        learning_level="inicial",
        sources=[submission["source_url"], *submission.get("related_sources", [])],
        automation_id=blog_run_id(local_day.isoformat(), slug),
    )
    lines = ["---"]
    for key, value in front.items():
        if isinstance(value, list):
            if value:
                lines.append(f"{key}:")
                lines.extend(f"  - {_quoted(str(item))}" for item in value)
            else:
                lines.append(f"{key}: []")
        elif isinstance(value, bool):
            lines.append(f"{key}: {str(value).lower()}")
        elif isinstance(value, int):
            lines.append(f"{key}: {value}")
        else:
            lines.append(f"{key}: {_quoted(str(value))}")
    return "\n".join([*lines, "---", "", submission["body"].strip(), ""])


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _json_file(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _check_image(path: Path) -> str:
    if (
        not path.is_file()
        or path.is_symlink()
        or path.suffix.casefold() not in {".jpg", ".jpeg", ".png"}
    ):
        raise ValueError("image must be a regular JPG or PNG file")
    if path.stat().st_size > 15 * 1024 * 1024:
        raise ValueError("image exceeds 15 MiB")
    with Image.open(path) as image:
        if image.format not in {"JPEG", "PNG"} or image.width < 800 or image.height < 500:
            raise ValueError("image must be a real JPG/PNG at least 800x500")
        image.verify()
    return ".jpg" if path.suffix.casefold() in {".jpg", ".jpeg"} else ".png"


def prepare_release(root: Path, submission: dict, image: Path, local_day: date) -> list[str]:
    """Write exactly six reviewed artifacts in a clean checkout."""
    slug = str(portable_slug(submission["title"], max_component_bytes=120))
    suffix = _check_image(image)
    cover_rel = f"static/images/stock/{slug}{suffix}"
    note_rel = f"content/notas/{slug}.md"
    social_rel = f"static/images/social/notes/{slug}.jpg"
    queue_rel = ".automation/news/queue/news-queue.json"
    manifest_rel = f".automation/blog/{local_day.isoformat()}-{slug}.json"
    report_rel = f".automation/reports/editorial-{local_day.isoformat()}.json"
    paths = [queue_rel, note_rel, cover_rel, social_rel, manifest_rel, report_rel]
    for relative in paths[1:]:
        if (root / relative).exists():
            raise FileExistsError(f"artifact already exists: {relative}")

    note = build_note(submission, local_day, slug, Path(cover_rel).name)
    queue = load_queue(root / queue_rel)
    if any(item["canonical_url"] == submission["source_url"] for item in queue["items"]):
        raise ValueError("the primary source is already in the news queue")
    now = datetime.now(UTC).isoformat().replace("+00:00", "Z")
    story = {
        "schema_version": 1,
        "title": submission["title"],
        "canonical_url": submission["source_url"],
        "source": submission["source_name"],
        "entity": submission["source_name"],
        "published_at": f"{submission['source_date']}T12:00:00Z",
        "discovered_at": now,
        "status": "consumed",
        "evidence": [{"url": submission["source_url"], "claim": submission["summary"]}],
        "tags": submission["tags"],
        "consumed_by": slug,
        "consumed_at": now,
    }
    story["id"] = stable_news_id(story)
    queue["items"].append(validate_news_item(story))
    queue["revision"] += 1
    queue["updated_at"] = now

    (root / cover_rel).parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(image, root / cover_rel)
    (root / note_rel).parent.mkdir(parents=True, exist_ok=True)
    (root / note_rel).write_text(note, encoding="utf-8")
    _json_file(root / queue_rel, queue)
    _run([sys.executable, "-m", "scripts.social", "render-note-announcement", "--slug", slug], root)
    if not (root / social_rel).is_file():
        raise RuntimeError("social announcement was not rendered")

    manifest = {
        "schema_version": 1,
        "run_id": blog_run_id(local_day.isoformat(), slug),
        "status": "prepared",
        "local_date": local_day.isoformat(),
        "created_at": now,
        "artifacts": {
            "note": {"path": note_rel, "sha256": _sha(root / note_rel)},
            "asset": {
                "path": cover_rel,
                "sha256": _sha(root / cover_rel),
                **submission.get("image_credit", {}),
            },
            "announcement": {"path": social_rel, "sha256": _sha(root / social_rel)},
            "queue": {"path": queue_rel, "sha256": _sha(root / queue_rel)},
        },
        "sources": [submission["source_url"], *submission["related_sources"]],
    }
    _json_file(root / manifest_rel, manifest)
    _json_file(
        root / report_rel,
        {
            "schema_version": 1,
            "run_id": f"editorial:{local_day.isoformat()}",
            "status": "prepared",
            "local_date": local_day.isoformat(),
            "created_at": now,
            "branch": f"automation/editorial/{local_day.isoformat()}",
            "note_slug": slug,
            "selected_news_ids": [story["id"]],
            "artifacts": {
                "manifest": manifest_rel,
                "note": note_rel,
                "cover": cover_rel,
                "announcement": social_rel,
                "queue": queue_rel,
            },
            "validation": {"local_guards": "green", "ci": "pending"},
            "external_effects": "pending protected merge and deployment",
        },
    )
    return paths


def release(input_path: Path, image_path: Path, *, dry_run: bool = False) -> str:
    local_day = datetime.now(TIMEZONE).date()
    submission = validate_submission(json.loads(input_path.read_text(encoding="utf-8")), local_day)
    image = image_path.resolve(strict=True)
    _check_image(image)
    branch = f"automation/editorial/{local_day.isoformat()}"
    _run(["git", "fetch", "--no-tags", "origin", "main"], ROOT)
    remote = _run(["git", "ls-remote", "--heads", "origin", branch], ROOT)
    if remote:
        prs = json.loads(
            _run(
                [
                    "gh",
                    "pr",
                    "list",
                    "--repo",
                    REPOSITORY,
                    "--head",
                    branch,
                    "--state",
                    "open",
                    "--json",
                    "url",
                ],
                ROOT,
            )
        )
        if len(prs) == 1:
            return prs[0]["url"]
        raise RuntimeError("the date's branch exists without one open PR; review it manually")
    temp_parent = Path(tempfile.mkdtemp(prefix="mragentes-editorial-", dir="/var/tmp"))
    worktree = temp_parent / "worktree"
    created = False
    safe_to_clean = False
    try:
        _run(["git", "worktree", "add", "--detach", str(worktree), "origin/main"], ROOT)
        created = True
        if _run(["git", "status", "--porcelain"], worktree):
            raise RuntimeError("new editorial worktree is not clean")
        report = worktree / f".automation/reports/editorial-{local_day.isoformat()}.json"
        if report.exists():
            safe_to_clean = True
            return "skipped_valid: today's report already exists on main"
        if any(
            f'date: "{local_day.isoformat()}' in path.read_text(encoding="utf-8")
            for path in (worktree / "content/notas").glob("*.md")
        ):
            raise RuntimeError("a note for today exists without a complete editorial report")
        paths = prepare_release(worktree, submission, image, local_day)
        _run(["git", "add", "--", *paths], worktree)
        _run([sys.executable, "scripts/scan_secrets.py"], worktree, quiet=True)
        _run(["git", "diff", "--cached", "--check"], worktree)
        staged = set(_run(["git", "diff", "--cached", "--name-only"], worktree).splitlines())
        if staged != set(paths):
            raise RuntimeError("staged files differ from the six editorial artifacts")
        if dry_run:
            return f"dry_run_valid: six artifacts at {worktree}"
        _run(["gh", "auth", "status"], worktree, quiet=True)
        permission = _run(
            ["gh", "api", f"repos/{REPOSITORY}", "--jq", ".permissions.push"], worktree
        )
        if permission != "true":
            raise RuntimeError("GitHub account lacks push permission for the repository")
        _run(
            [
                "git",
                "-c",
                "user.name=MR Agentes Editorial",
                "-c",
                "user.email=editorial@mragentes.com.ar",
                "commit",
                "-m",
                f"content(editorial): news for {local_day.isoformat()}",
            ],
            worktree,
        )
        _run(["git", "push", "origin", f"HEAD:refs/heads/{branch}"], worktree)
        try:
            url = _run(
                [
                    "gh",
                    "pr",
                    "create",
                    "--repo",
                    REPOSITORY,
                    "--base",
                    "main",
                    "--head",
                    branch,
                    "--title",
                    submission["title"],
                    "--body",
                    (
                        f"Nota informativa del {local_day.isoformat()}. "
                        f"Fuente principal: {submission['source_url']}"
                    ),
                ],
                worktree,
            )
        except RuntimeError:
            prs = json.loads(
                _run(
                    [
                        "gh",
                        "pr",
                        "list",
                        "--repo",
                        REPOSITORY,
                        "--head",
                        branch,
                        "--state",
                        "open",
                        "--json",
                        "url",
                    ],
                    worktree,
                )
            )
            if len(prs) != 1:
                raise
            url = prs[0]["url"]
        safe_to_clean = True
        return url
    finally:
        if created and safe_to_clean:
            _run(["git", "worktree", "remove", str(worktree)], ROOT, quiet=True)
            temp_parent.rmdir()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True, help="researched story JSON")
    parser.add_argument("--image", type=Path, required=True, help="JPG or PNG cover")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    try:
        print(release(args.input, args.image, dry_run=args.dry_run))
    except (OSError, ValueError, RuntimeError, json.JSONDecodeError) as exc:
        print(f"needs_review: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
