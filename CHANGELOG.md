# Changelog

All notable changes to AsOfGuard are documented here. The format follows Keep a Changelog principles, and the project intends to use Semantic Versioning after the public API stabilizes.

## [Unreleased]

### Added

- Initial substantive MVP for Python 3.9+ with no runtime dependencies.
- Typed models for queries, immutable document versions and validity windows, supersession chains, retrieval events, artifacts, memory writes and reads, cited spans, model knowledge declarations, findings, and verdicts.
- JSONL parser with timezone-aware timestamp validation, duplicate-ID checks, comments, and clear source/line errors.
- Deterministic verification of post-cutoff retrieval, not-yet-valid and expired sources, superseded-as-current versions, later case/policy leakage, post-cutoff memory learning and reads, artifact build/corpus/knowledge violations, missing temporal metadata, citation integrity, and cyclic version chains.
- Explicit separation of observable event failures, missing evidence, and irreducible model-weight uncertainty.
- Exact contaminating-item lists and earliest invalid timestamps.
- `verify`, `fixtures list`, `fixtures show`, and `explain` CLI commands.
- Text, JSON, JUnit XML, and SARIF 2.1.0 reports.
- More than forty packaged synthetic adversarial scenarios and one complete clean historical scenario.
- Standard-library `unittest` suite, fixture expectation validation, and `ci/check.sh`.
- Trace schema, examples, security policy, contribution guide, Apache-2.0 license, and project README.

[Unreleased]: ./
