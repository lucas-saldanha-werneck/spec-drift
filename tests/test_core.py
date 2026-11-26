import json
from pathlib import Path

import pytest

from spec_drift.cli import main
from spec_drift.core import compare, load_openapi, parse_spec

EX = Path(__file__).resolve().parent.parent / "examples"


def kinds(findings):
    return sorted((f.kind, f.endpoint) for f in findings)


def test_parse_spec_reads_lines_and_ignores_prose():
    spec = parse_spec("# Title\nsome text\n- get /a/{id} -> 200, 404\n* POST /a → 201\n- FOO /x -> 200\n")
    assert spec == {("GET", "/a/{id}"): {"200", "404"}, ("POST", "/a"): {"201"}}


def test_parse_spec_merges_repeated_endpoint():
    spec = parse_spec("- GET /a -> 200\n- GET /a -> 404\n")
    assert spec[("GET", "/a")] == {"200", "404"}


def test_load_openapi_rejects_other_json():
    with pytest.raises(ValueError):
        load_openapi({"hello": "world"})


def test_no_drift():
    api = {("GET", "/a"): {"200"}}
    assert compare({("GET", "/a"): {"200"}}, api) == []


def test_missing_endpoint_with_method_hint():
    f = compare({("DELETE", "/a"): {"204"}}, {("GET", "/a"): {"200"}})
    assert kinds(f) == [("missing-endpoint", "DELETE /a"), ("undocumented-endpoint", "GET /a")]
    assert "path exists with GET" in f[0].detail


def test_missing_response_code():
    f = compare({("GET", "/a"): {"200", "404"}}, {("GET", "/a"): {"200"}})
    assert kinds(f) == [("missing-response", "GET /a")]
    assert f[0].level == "error"


def test_range_and_default_cover_codes():
    assert compare({("GET", "/a"): {"201"}}, {("GET", "/a"): {"2XX"}}) == []
    assert compare({("GET", "/a"): {"500"}}, {("GET", "/a"): {"DEFAULT"}}) == []


def test_param_name_difference_is_only_a_warning():
    f = compare({("GET", "/a/{id}"): {"200"}}, {("GET", "/a/{a_id}"): {"200"}})
    assert kinds(f) == [("param-name", "GET /a/{id}")]
    assert f[0].level == "warning"


def test_undocumented_endpoint_is_warning():
    f = compare({}, {("GET", "/metrics"): {"200"}})
    assert [x.level for x in f] == ["warning"]


def test_example_files_drift_as_documented():
    spec = parse_spec((EX / "spec.md").read_text())
    api = load_openapi(json.loads((EX / "openapi.json").read_text()))
    got = kinds(compare(spec, api))
    assert got == [
        ("missing-endpoint", "DELETE /items/{id}"),
        ("missing-endpoint", "GET /health"),
        ("missing-response", "GET /items/{id}"),
        ("missing-response", "POST /items"),
        ("param-name", "GET /items/{id}"),
        ("undocumented-endpoint", "GET /metrics"),
    ]


def test_cli_exit_codes(capsys, tmp_path):
    assert main([str(EX / "spec.md"), str(EX / "openapi.json")]) == 1
    out = capsys.readouterr().out
    assert "4 errors, 2 warnings" in out

    spec = tmp_path / "s.md"
    spec.write_text("- GET /items -> 200\n")
    assert main([str(spec), str(EX / "openapi.json")]) == 0
    assert main([str(spec), str(EX / "openapi.json"), "--strict"]) == 1  # undocumented warnings

    empty = tmp_path / "e.md"
    empty.write_text("nothing here\n")
    assert main([str(empty), str(EX / "openapi.json")]) == 2
