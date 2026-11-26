# spec-drift

Checks a plain-text endpoint spec against an OpenAPI document and lists where they disagree.

Independent demo, not affiliated with CI&T. I wrote it after applying for a Python backend role that asks for Spec-Driven Development, FastAPI and pytest. It is a small example of the first idea, with no dependencies beyond the Python standard library.

## The problem

In spec-driven work the spec is written first, often as a short list in a markdown file, and the code follows. FastAPI generates `/openapi.json` from the code, so the two can be compared mechanically. Without a check, they drift: an endpoint is renamed, a 404 is never implemented, a debug route ships without being in the spec.

## The spec format

One endpoint per line. Everything else in the file is ignored.

```
- GET /items/{id} -> 200, 404
- POST /items -> 201, 422
```

## Run it

Python 3.10+.

```sh
pip install -e ".[dev]"
spec-drift examples/spec.md examples/openapi.json
# or against a running FastAPI app:
spec-drift my-spec.md http://localhost:8000/openapi.json
```

Exit code 0 means no errors, 1 means drift, 2 means a bad input file. `--strict` counts warnings as errors.

Output for the bundled example (an invented sample API, not a real one):

```
[error] missing-endpoint: DELETE /items/{id} - in spec, not in API
[error] missing-endpoint: GET /health - in spec, not in API
[warning] param-name: GET /items/{id} - API names the parameter differently: /items/{item_id}
[error] missing-response: GET /items/{id} - spec lists 404, API documents ['200', '422']
[error] missing-response: POST /items - spec lists 422, API documents ['201']
[warning] undocumented-endpoint: GET /metrics - in API, not in spec
5 spec endpoints, 4 API operations: 4 errors, 2 warnings
```

## Rules

- Paths match when they have the same shape, so `/items/{id}` equals `/items/{item_id}`. A different parameter name gives a warning.
- A status code in the spec must appear in the operation's `responses`. `2XX`-style ranges and `default` count as covering it.
- An operation in the API that is not in the spec is a warning.

## What was tested

- 11 pytest tests, run offline in CI on Python 3.10 and 3.12: spec parsing, each kind of finding, range and `default` codes, the bundled example, and the CLI exit codes.
- I ran the CLI on the bundled example by hand and the output above is what it printed.

## What was not tested

- No real FastAPI app. The example OpenAPI file is hand-written. I have not run the URL mode against a live server.
- Only OpenAPI 3.x JSON with a `paths` object. YAML files, `$ref` handling and webhooks are not supported.
- It compares paths, methods and status codes only. It does not look at request or response schemas.
- The spec parser is strict about the line format. A typo in a line means that endpoint is silently skipped; the tool only complains when it finds no endpoints at all.
