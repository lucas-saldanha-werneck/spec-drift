"""Command line: spec-drift SPEC.md OPENAPI.json (or an http(s) URL to /openapi.json)."""
from __future__ import annotations

import argparse
import json
import sys
import urllib.request

from .core import compare, load_openapi, parse_spec


def _read_json(source: str) -> dict:
    if source.startswith(("http://", "https://")):
        with urllib.request.urlopen(source, timeout=15) as r:  # noqa: S310 - user-supplied URL by design
            return json.load(r)
    with open(source, encoding="utf-8") as f:
        return json.load(f)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="spec-drift", description=__doc__)
    p.add_argument("spec", help="markdown file with lines like '- GET /items/{id} -> 200, 404'")
    p.add_argument("openapi", help="OpenAPI JSON file, or URL such as http://localhost:8000/openapi.json")
    p.add_argument("--strict", action="store_true", help="treat warnings as errors")
    args = p.parse_args(argv)

    with open(args.spec, encoding="utf-8") as f:
        spec = parse_spec(f.read())
    if not spec:
        print("spec-drift: no endpoint lines found in the spec", file=sys.stderr)
        return 2
    try:
        api = load_openapi(_read_json(args.openapi))
    except (ValueError, OSError) as e:
        print(f"spec-drift: {e}", file=sys.stderr)
        return 2

    findings = compare(spec, api)
    for f in findings:
        print(f)
    errors = sum(f.level == "error" for f in findings)
    warnings = len(findings) - errors
    print(f"{len(spec)} spec endpoints, {len(api)} API operations: {errors} errors, {warnings} warnings")
    return 1 if errors or (args.strict and warnings) else 0


if __name__ == "__main__":
    sys.exit(main())
