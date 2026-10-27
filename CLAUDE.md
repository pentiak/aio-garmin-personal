# aio-garmin-personal

Async client for the Garmin Connect Personal API, used by the `garmin_connect_personal` Home
Assistant integration. Project documents are in `../ha-garmin-connect-personal/docs/`; read the
Status section of `PLAN.md` there first.

## Commands

```shell
.venv/bin/pytest                                  # includes the 95% coverage gate
.venv/bin/mypy                                    # strict, src and tests
.venv/bin/ruff check . && .venv/bin/ruff format --check .
.venv/bin/pre-commit run --all-files              # all of the above that is fast, plus secrets and zizmor
.venv/bin/pip-audit --skip-editable               # known vulnerabilities in installed packages
.venv/bin/zizmor --offline .                      # GitHub Actions security lint
```

Fresh clone: `python3 -m venv .venv && .venv/bin/pip install -e ".[dev]"`, then
`.venv/bin/pre-commit install`. Every pre-commit hook runs a tool from `.venv`; none is
downloaded.

## Guardrails

CI (`ci.yml`) runs ruff, mypy and the tests on 3.13 and 3.14, and `pip-audit` on the runtime
dependencies. `security.yml` runs gitleaks, Trivy (`fs`: vulnerabilities, secrets,
misconfiguration) and zizmor on every push and PR and weekly, and CodeQL once the repository
is public. Dependabot proposes action and pip updates weekly, a week after each release.

- **Pin every action to a full commit SHA** with the version as a comment
  (`uses: owner/repo@<40-char sha> # vX.Y.Z`). Resolve a tag with
  `git ls-remote https://github.com/<owner>/<repo>.git refs/tags/<tag> 'refs/tags/<tag>^{}'`
  and take the last line. Choose a release at least seven days old (ADR-0019).
- `actions/checkout` always gets `persist-credentials: false`; workflows start from
  `permissions: {}` and grant per job. zizmor enforces both.
- A `# noqa` needs a comment above it saying why the finding is a false positive.
- `.gitleaks.toml` skips `.secrets.baseline`, whose SHA-1 hashes match the generic API key
  rule of gitleaks. The gitleaks-action v3 runs gitleaks 8.24, which ignores the newer
  `[[allowlists]]` syntax; keep the single `[allowlist]` table.
- `.secrets.baseline` lists the fake credentials in the tests. When detect-secrets flags a new
  one, confirm it is fake, then run
  `.venv/bin/detect-secrets scan --baseline .secrets.baseline --exclude-files '^\.venv/'`.

## Rules for this library

These come from Home Assistant's requirements for core dependencies (Platinum tier):

- `asyncio` and `aiohttp` only. The caller passes the `ClientSession`; the client never creates
  or closes one.
- Every failure surfaces as one of the exceptions in `exceptions.py`. Never let an
  `aiohttp.ClientError`, `TimeoutError` or `json.JSONDecodeError` escape.
- Keep `py.typed` and `mypy --strict` clean; the integration's `strict-typing` rule depends on
  it.
- No disk I/O, no environment variables, no logging of keys or tokens.
- Each PyPI version must match a `vX.Y.Z` tag and be published by `.github/workflows/release.yml`.
  Never upload by hand. Bump `version` in `pyproject.toml` and move the CHANGELOG entries under a
  `## X.Y.Z - YYYY-MM-DD` heading in the same commit as the release. That section becomes the
  GitHub release notes; without it the workflow fails before publishing.

## Tests

Tests run against `FakeGarmin` in `tests/conftest.py`, a local aiohttp server with queued
replies. Do not reintroduce `aioresponses`: 0.7.9 does not work with aiohttp 3.14 (ADR-0011).
Fixture JSON in `tests/fixtures/` has the shape of real responses, with every identifier,
metric and timestamp made up (ADR-0021 in the integration repository). Never commit a real
response: replace all of it, not only the identifiers.

## The API spec

`scripts/extract_openapi.py` regenerates Garmin's OpenAPI document from the Swagger page bundle.
Write its output to `../reference/`, never into this repository.
