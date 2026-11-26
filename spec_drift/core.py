"""Parse a markdown endpoint spec, load an OpenAPI document, report drift."""
from __future__ import annotations

import re
from dataclasses import dataclass

METHODS = {"GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"}
SPEC_LINE = re.compile(
    r"^\s*[-*]\s+(?P<method>[A-Za-z]+)\s+(?P<path>/\S*)\s*(?:->|→)\s*(?P<codes>.+?)\s*$"
)
PARAM = re.compile(r"\{([^}]+)\}")


@dataclass(frozen=True)
class Finding:
    level: str  # "error" or "warning"
    kind: str
    endpoint: str
    detail: str

    def __str__(self) -> str:
        return f"[{self.level}] {self.kind}: {self.endpoint} - {self.detail}"


def parse_spec(text: str) -> dict[tuple[str, str], set[str]]:
    """Return {(METHOD, path): {status codes}} from lines like `- GET /a/{id} -> 200, 404`."""
    spec: dict[tuple[str, str], set[str]] = {}
    for line in text.splitlines():
        m = SPEC_LINE.match(line)
        if not m or m["method"].upper() not in METHODS:
            continue
        codes = {c.strip().upper() for c in re.split(r"[,\s]+", m["codes"]) if c.strip()}
        spec.setdefault((m["method"].upper(), m["path"]), set()).update(codes)
    return spec


def load_openapi(doc: dict) -> dict[tuple[str, str], set[str]]:
    """Return {(METHOD, path): {status codes}} from an OpenAPI 3.x document."""
    paths = doc.get("paths")
    if not isinstance(paths, dict):
        raise ValueError("not an OpenAPI document: no 'paths' object")
    api: dict[tuple[str, str], set[str]] = {}
    for path, item in paths.items():
        if not isinstance(item, dict):
            continue
        for method, op in item.items():
            if method.upper() in METHODS and isinstance(op, dict):
                api[(method.upper(), path)] = {str(c).upper() for c in op.get("responses", {})}
    return api


def _shape(path: str) -> str:
    """Path with parameter names removed, so /items/{id} and /items/{item_id} match."""
    return PARAM.sub("{}", path)


def _code_covered(code: str, documented: set[str]) -> bool:
    if code in documented or "DEFAULT" in documented:
        return True
    return len(code) == 3 and code[0] + "XX" in documented


def compare(spec, api) -> list[Finding]:
    findings: list[Finding] = []
    api_by_shape = {(m, _shape(p)): (p, codes) for (m, p), codes in api.items()}
    spec_shapes = set()
    for (method, path), want in sorted(spec.items()):
        shape = (method, _shape(path))
        spec_shapes.add(shape)
        ep = f"{method} {path}"
        if shape not in api_by_shape:
            other = sorted(m for (m, p) in api if p == path and m != method)
            hint = f" (path exists with {', '.join(other)})" if other else ""
            findings.append(Finding("error", "missing-endpoint", ep, "in spec, not in API" + hint))
            continue
        api_path, have = api_by_shape[shape]
        if api_path != path:
            findings.append(Finding(
                "warning", "param-name", ep, f"API names the parameter differently: {api_path}"))
        for code in sorted(want):
            if not _code_covered(code, have):
                findings.append(Finding(
                    "error", "missing-response", ep, f"spec lists {code}, API documents {sorted(have) or 'none'}"))
    for (method, path), _codes in sorted(api.items()):
        if (method, _shape(path)) not in spec_shapes:
            findings.append(Finding("warning", "undocumented-endpoint", f"{method} {path}", "in API, not in spec"))
    return findings
