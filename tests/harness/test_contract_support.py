from __future__ import annotations

import json
from pathlib import Path

import pytest

import scripts.test.build_traceability as trace_builder
import scripts.test.summarize_results as result_summary
import scripts.test.validate_traceability as traceability
from scripts.test.collect_symbols import collect
from scripts.test.validate_traceability import collect_test_metadata, collect_test_nodes
from tests.support.contracts import repository_path, trace_message
from tests.support.git_tree import component_overruns
from tests.support.safety import assert_command_allowed, assert_not_source_path


@pytest.mark.trace("HARNESS-TRACE-001")
@pytest.mark.baseline_green
def test_trace_message_requires_stable_id() -> None:
    assert trace_message("HARNESS-TRACE-001", "ok") == "[HARNESS-TRACE-001] ok"
    with pytest.raises(ValueError, match="invalid trace id"):
        trace_message("bad", "no")


@pytest.mark.trace("HARNESS-TRACE-002")
@pytest.mark.baseline_green
def test_repository_path_rejects_escape() -> None:
    with pytest.raises(ValueError, match="escapes root"):
        repository_path("../../outside")


@pytest.mark.trace("HARNESS-TRACE-003")
@pytest.mark.baseline_green
def test_component_overruns_count_utf8_bytes() -> None:
    paths = ["ok/áá.md", "bad/" + ("á" * 72)]
    assert component_overruns(paths, 143) == [(paths[1], "á" * 72, 144)]


@pytest.mark.trace("HARNESS-TRACE-004")
@pytest.mark.baseline_green
def test_source_path_guard_is_pure_and_blocks_source() -> None:
    with pytest.raises(PermissionError, match="SRC-IMM-001"):
        assert_not_source_path("/home/openclaw/sentinel-do-not-open")


@pytest.mark.trace("HARNESS-TRACE-005")
@pytest.mark.baseline_green
def test_command_guard_blocks_account_commands(tmp_path: Path) -> None:
    with pytest.raises(PermissionError, match="SRC-IMM-002"):
        assert_command_allowed(["sudo", "-u", "openclaw", "true"], tmp_path, tmp_path)


@pytest.mark.trace("HARNESS-TRACE-006")
@pytest.mark.baseline_green
def test_symbol_collector_handles_nested_python_and_typescript(tmp_path: Path) -> None:
    (tmp_path / "module.py").write_text(
        "def outer():\n    def inner():\n        return 1\n    return inner()\n",
        encoding="utf-8",
    )
    (tmp_path / "worker.ts").write_text(
        "export async function fetcher() {}\nexport class Coordinator {}\n",
        encoding="utf-8",
    )
    result = collect(tmp_path)
    assert result["module.py"] == ["outer", "outer.inner"]
    assert result["worker.ts"] == ["Coordinator", "fetcher"]


@pytest.mark.trace("HARNESS-TRACE-007")
@pytest.mark.baseline_green
def test_test_node_collector_requires_literal_trace_marker(tmp_path: Path) -> None:
    tests = tmp_path / "tests"
    tests.mkdir()
    (tests / "test_ok.py").write_text(
        "import pytest\n"
        "@pytest.mark.trace('HARNESS-TRACE-007')\n"
        "@pytest.mark.baseline_green\n"
        "def test_ok():\n    pass\n",
        encoding="utf-8",
    )
    assert collect_test_nodes(tmp_path) == {
        "tests/test_ok.py::test_ok": "HARNESS-TRACE-007"
    }


@pytest.mark.trace("HARNESS-TRACE-008")
@pytest.mark.baseline_green
def test_red_baseline_schema_is_closed() -> None:
    schema = json.loads(
        repository_path(".testplan/schemas/red-baseline.schema.json").read_text(encoding="utf-8")
    )
    assert schema["additionalProperties"] is False
    assert set(schema["required"]) == {
        "schema_version",
        "run_id",
        "generated_at",
        "git",
        "environment",
        "counts",
        "requirements",
    }


@pytest.mark.trace("HARNESS-TRACE-011")
@pytest.mark.baseline_green
def test_test_metadata_collector_captures_initial_state(tmp_path: Path) -> None:
    tests = tmp_path / "tests"
    tests.mkdir()
    (tests / "test_state.py").write_text(
        "import pytest\n"
        "@pytest.mark.trace('HARNESS-TRACE-011')\n"
        "@pytest.mark.red_expected\n"
        "def test_state():\n    pass\n",
        encoding="utf-8",
    )
    assert collect_test_metadata(tmp_path)["tests/test_state.py::test_state"] == {
        "trace_id": "HARNESS-TRACE-011",
        "initial_state": "RED_EXPECTED",
        "name": "test_state",
    }


@pytest.mark.trace("HARNESS-TRACE-012")
@pytest.mark.baseline_green
def test_javascript_catalogue_collector_requires_closed_unique_entries(tmp_path: Path) -> None:
    catalogue = tmp_path / "tests-js" / "traceability.json"
    catalogue.parent.mkdir()
    catalogue.write_text(
        json.dumps(
            [
                {
                    "id": "PUSH-AUTH-001",
                    "initial_state": "RED_EXPECTED",
                    "requirement": "token exacto",
                    "source_symbols": ["workers/push/src/index.ts::tokenOk"],
                    "test_paths": [
                        "tests-js/worker-auth-payload.test.mjs::[PUSH-AUTH-001] token exacto"
                    ],
                }
            ]
        ),
        encoding="utf-8",
    )
    collector = getattr(traceability, "collect_javascript_metadata", None)
    assert callable(collector), trace_message(
        "HARNESS-TRACE-012", "JavaScript catalogue collector is absent"
    )
    assert collector(tmp_path) == {
        "tests-js/worker-auth-payload.test.mjs::[PUSH-AUTH-001] token exacto": {
            "trace_id": "PUSH-AUTH-001",
            "initial_state": "RED_EXPECTED",
            "name": "token exacto",
        }
    }


@pytest.mark.trace("HARNESS-TRACE-013")
@pytest.mark.baseline_green
def test_javascript_catalogue_collector_rejects_duplicate_nodeids(tmp_path: Path) -> None:
    catalogue = tmp_path / "tests-js" / "traceability.json"
    catalogue.parent.mkdir()
    nodeid = "tests-js/push.test.mjs::[PUSH-AUTH-001] token exacto"
    entry = {
        "id": "PUSH-AUTH-001",
        "initial_state": "RED_EXPECTED",
        "requirement": "token exacto",
        "source_symbols": ["workers/push/src/index.ts::tokenOk"],
        "test_paths": [nodeid],
    }
    catalogue.write_text(json.dumps([entry, entry]), encoding="utf-8")
    collector = getattr(traceability, "collect_javascript_metadata", None)
    assert callable(collector), trace_message(
        "HARNESS-TRACE-013", "JavaScript catalogue collector is absent"
    )
    with pytest.raises(ValueError, match="duplicate JavaScript test node"):
        collector(tmp_path)


@pytest.mark.trace("HARNESS-TRACE-014")
@pytest.mark.baseline_green
def test_vitest_json_results_preserve_nodeids_and_failure_prefix(tmp_path: Path) -> None:
    report = tmp_path / "javascript.json"
    report.write_text(
        json.dumps(
            {
                "testResults": [
                    {
                        "name": str(tmp_path / "tests-js" / "push.test.mjs"),
                        "assertionResults": [
                            {
                                "ancestorTitles": ["Worker"],
                                "title": "[PUSH-AUTH-001] token exacto",
                                "fullName": "Worker [PUSH-AUTH-001] token exacto",
                                "status": "failed",
                                "failureMessages": ["AssertionError: [PUSH-AUTH-001] missing target"],
                            }
                        ],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    parser = getattr(result_summary, "vitest_results", None)
    assert callable(parser), trace_message(
        "HARNESS-TRACE-014", "Vitest JSON result parser is absent"
    )
    assert parser(report, tmp_path) == {
        "tests-js/push.test.mjs::[PUSH-AUTH-001] token exacto": (
            "FAILED",
            "AssertionError: [PUSH-AUTH-001] missing target",
        )
    }


@pytest.mark.trace("HARNESS-TRACE-015")
@pytest.mark.baseline_green
def test_vitest_json_results_reject_duplicate_nodeids(tmp_path: Path) -> None:
    report = tmp_path / "javascript.json"
    assertion = {
        "title": "[PUSH-AUTH-001] token exacto",
        "status": "passed",
        "failureMessages": [],
    }
    report.write_text(
        json.dumps(
            {
                "testResults": [
                    {
                        "name": str(tmp_path / "tests-js" / "push.test.mjs"),
                        "assertionResults": [assertion, assertion],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    parser = getattr(result_summary, "vitest_results", None)
    assert callable(parser), trace_message(
        "HARNESS-TRACE-015", "Vitest JSON result parser is absent"
    )
    with pytest.raises(ValueError, match="duplicate Vitest node"):
        parser(report, tmp_path)


@pytest.mark.trace("HARNESS-TRACE-016")
@pytest.mark.baseline_green
def test_vitest_list_rows_generate_closed_javascript_catalogue(tmp_path: Path) -> None:
    test_file = tmp_path / "tests-js" / "worker-auth-payload.test.mjs"
    test_file.parent.mkdir()
    rows = [
        {
            "name": "suite > [PUSH-AUTH-001] token exacto",
            "file": str(test_file),
        },
        {
            "name": "suite > [PUSH-AUTH-004] secreto vacío",
            "file": str(test_file),
        },
    ]
    builder = getattr(trace_builder, "build_javascript_catalogue_from_rows", None)
    assert callable(builder), trace_message(
        "HARNESS-TRACE-016", "Vitest-list catalogue builder is absent"
    )
    entries = builder(rows, tmp_path)
    assert entries == [
        {
            "id": "PUSH-AUTH-001",
            "initial_state": "BASELINE_GREEN",
            "requirement": "token exacto",
            "source_symbols": ["workers/push/src/auth.ts"],
            "test_paths": [
                "tests-js/worker-auth-payload.test.mjs::[PUSH-AUTH-001] token exacto"
            ],
        },
        {
            "id": "PUSH-AUTH-004",
            "initial_state": "RED_EXPECTED",
            "requirement": "secreto vacío",
            "source_symbols": ["workers/push/src/auth.ts"],
            "test_paths": [
                "tests-js/worker-auth-payload.test.mjs::[PUSH-AUTH-004] secreto vacío"
            ],
        },
    ]


@pytest.mark.trace("HARNESS-TRACE-017")
@pytest.mark.baseline_green
def test_vitest_list_catalogue_rejects_duplicate_trace_ids(tmp_path: Path) -> None:
    test_file = tmp_path / "tests-js" / "push.test.mjs"
    test_file.parent.mkdir()
    rows = [
        {"name": "one > [PUSH-AUTH-001] first", "file": str(test_file)},
        {"name": "two > [PUSH-AUTH-001] second", "file": str(test_file)},
    ]
    builder = getattr(trace_builder, "build_javascript_catalogue_from_rows", None)
    assert callable(builder), trace_message(
        "HARNESS-TRACE-017", "Vitest-list catalogue builder is absent"
    )
    with pytest.raises(ValueError, match="duplicate JavaScript trace id"):
        builder(rows, tmp_path)
