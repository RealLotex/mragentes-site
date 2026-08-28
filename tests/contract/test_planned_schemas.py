from __future__ import annotations

import json

import jsonschema
import pytest

from tests.support.contracts import require_target, trace_message


SCHEMAS = [
    ("NEWS-SCHEMA-001", ".automation/schemas/news-item.schema.json"),
    ("BLOG-FM-001", ".automation/schemas/blog-draft.schema.json"),
    ("SOCIAL-SCHEMA-001", ".automation/schemas/social-post.schema.json"),
]


@pytest.mark.parametrize("trace_id,relative_path", SCHEMAS, ids=[item[0] for item in SCHEMAS])
@pytest.mark.trace("SCHEMA-TARGET-001")
@pytest.mark.red_expected
def test_planned_schema_exists_and_is_closed(trace_id: str, relative_path: str) -> None:
    path = require_target(relative_path, "SCHEMA-TARGET-001")
    schema = json.loads(path.read_text(encoding="utf-8"))
    jsonschema.Draft202012Validator.check_schema(schema)
    assert schema.get("additionalProperties") is False, trace_message(
        "SCHEMA-TARGET-001", f"schema is not closed: {relative_path} ({trace_id})"
    )


@pytest.mark.trace("HARNESS-TRACE-009")
@pytest.mark.baseline_green
def test_traceability_schema_is_valid_draft_2020_12() -> None:
    path = require_target(
        ".testplan/schemas/traceability.schema.json", "HARNESS-TRACE-009"
    )
    jsonschema.Draft202012Validator.check_schema(json.loads(path.read_text(encoding="utf-8")))


@pytest.mark.trace("HARNESS-TRACE-010")
@pytest.mark.baseline_green
def test_red_baseline_schema_is_valid_draft_2020_12() -> None:
    path = require_target(
        ".testplan/schemas/red-baseline.schema.json", "HARNESS-TRACE-010"
    )
    jsonschema.Draft202012Validator.check_schema(json.loads(path.read_text(encoding="utf-8")))
