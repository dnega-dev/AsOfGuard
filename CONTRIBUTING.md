# Contributing to AsOfGuard

Thank you for improving temporal verification.

## Principles

Contributions must preserve these invariants:

1. **Zero runtime dependencies.** The verifier and CLI use only the Python 3.9+ standard library.
2. **Evidence before inference.** Missing temporal metadata produces a metadata gap; the verifier must not invent dates.
3. **Observable failure is distinct from model-weight uncertainty.** Do not turn a model cutoff declaration into proof of weight purity.
4. **Deterministic output.** Findings and serialized reports must have stable ordering.
5. **Exact attribution.** New rules identify the implicated item and timestamp when one exists.
6. **Backward-compatible JSONL.** New optional fields are preferred; breaking schema changes require a documented schema-version transition.

## Development setup

No test framework needs to be installed:

```bash
python3 --version  # 3.9 or newer
./ci/check.sh
```

The check script runs the `unittest` suite, validates packaged fixture expectations, and runs `compileall`.

To exercise the CLI from a checkout:

```bash
PYTHONPATH=src python3 -m asof_guard verify --fixture clean_historical
PYTHONPATH=src python3 -m asof_guard explain
```

## Adding a verification rule

1. Add a stable uppercase code, title, description, and remediation to `src/asof_guard/rules.py`.
2. Emit the finding from `src/asof_guard/verifier.py` with the correct category:
   - `observable_failure` for demonstrated trace violations;
   - `metadata_gap` when required evidence is absent;
   - `model_weight_uncertainty` for weight-level claims the trace cannot settle.
3. Choose the item type and ID that identify the direct contaminant.
4. Attach the earliest timestamp that made that item invalid. Do not attach unrelated event time merely to avoid `null`.
5. Add at least one adversarial packaged fixture with expected status and code.
6. Add focused unit tests and update `docs/trace-schema.md` and `CHANGELOG.md`.
7. Confirm text, JSON, JUnit, and SARIF rendering still escapes and classifies the finding correctly.

## Fixture conventions

Fixtures live in `src/asof_guard/fixtures/` and are package data. Use lowercase snake-case filenames and matching trace IDs. The header should include:

```json
{"type":"trace","id":"scenario_name","expectations":{"status":"contaminated","codes":["RULE_CODE"],"description":"One sentence."}}
```

Expected codes are a required subset, not necessarily the full finding set: one adversarial fact can legitimately trigger multiple complementary rules. Every fixture must include a model declaration unless its purpose is to test that declaration's absence.

## Style

- Follow PEP 8 and existing type-hint conventions.
- Use frozen dataclasses for immutable trace records.
- Keep parsing, verification, and reporting concerns separate.
- Read files before editing and preserve existing naming patterns.
- Avoid third-party syntax, generated vendored files, or network-dependent tests.
- Write public API docstrings and comments only where they explain intent or assurance semantics.

## Tests

Tests use `unittest` and live under `tests/`. Name test methods for behavior, not implementation. Include boundary tests for equality at `as_of`, UTC-offset normalization, missing metadata, duplicate IDs, report validity, and exit codes when relevant.

Run:

```bash
./ci/check.sh
```

A change is ready only when all tests and `compileall` pass on Python 3.9+.

## Security changes

Do not include real sensitive traces in tests or discussions. Follow `SECURITY.md` for vulnerabilities. Parser hardening changes should include a regression test with a minimal synthetic input.

## License

By contributing, you agree that your contribution is licensed under the Apache License 2.0 in `LICENSE`.
