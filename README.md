# AsOfGuard

AsOfGuard is a zero-runtime-dependency Python 3.9+ verifier for **temporal contamination** in retrieval-augmented generation (RAG) and agent-memory traces. It asks a narrow, auditable question:

> Given a query with an `as_of` boundary, did any observable retrieval, source version, memory, citation, embedding index, or reranker artifact violate that boundary?

It reports the exact contaminating items, the earliest invalid timestamp, missing evidence, and the special uncertainty introduced by opaque model weights.

## Assurance boundary

AsOfGuard deliberately separates two claims that are often conflated:

1. **Observable trace integrity** can be checked from timestamped events and provenance. AsOfGuard returns `contaminated` when those records demonstrate a violation.
2. **Model-weight purity is unverifiable from a trace.** A model knowledge-cutoff declaration is useful evidence, but neither it nor a clean event trace proves that no post-cutoff fact encoded in model weights affected the answer.

A `clean` verdict therefore means **no observable temporal failure was found and required event metadata was present**. It never means that opaque model weights were proved historically pure. Every report states this limitation.

## What it detects

- retrieval events executed after the query cutoff;
- retrieved documents not yet valid or no longer valid at query time;
- post-cutoff creation/publication despite back-dated validity metadata;
- superseded versions treated as current, plus cyclic version chains;
- memories learned or read after the cutoff and memories sourced from later documents;
- later cases, decisions, policies, regulations, guidance, or procedures entering historical answers;
- embedding-index, vector-store snapshot, and reranker artifacts built after the cutoff;
- artifact knowledge boundaries and source corpora extending beyond the cutoff;
- missing timestamps, absent references, and undeclared model knowledge cutoffs;
- cited offsets that are impossible, stale, text-mismatched, or unsupported by a retrieval;
- irreducible model-weight uncertainty, separately from observable failures.

## Install and run

No third-party package is needed at runtime.

```bash
python -m pip install .
asof-guard --version
```

From a source checkout, without installing:

```bash
PYTHONPATH=src python -m asof_guard fixtures list
PYTHONPATH=src python -m asof_guard verify --fixture clean_historical
```

Verify a JSONL file or standard input:

```bash
asof-guard verify trace.jsonl
cat trace.jsonl | asof-guard verify - --format json
```

Write CI-friendly reports:

```bash
asof-guard verify trace.jsonl --format junit --output asof-junit.xml
asof-guard verify trace.jsonl --format sarif --output asof.sarif
```

Inspect built-in adversarial cases and rule explanations:

```bash
asof-guard fixtures list
asof-guard fixtures list --format json
asof-guard fixtures show superseded_as_current
asof-guard explain SUPERSEDED_AS_CURRENT
asof-guard explain --format json
```

## Exit codes

| Code | Meaning |
| ---: | --- |
| `0` | Clean observable trace; model weights remain explicitly unverifiable |
| `2` | One or more observable temporal failures |
| `3` | No observable failure, but required metadata is missing or the declared model knowledge boundary exceeds the query cutoff |
| `4` | Invalid command, unreadable input, or malformed JSONL/schema value |

When a trace has both demonstrated failures and uncertainty, `contaminated` takes precedence and exit code `2` is returned. All metadata gaps and model-weight uncertainty findings remain in the report.

## Minimal JSONL trace

Each non-empty line is one JSON object. Timestamps must be ISO-8601 values with an explicit UTC offset. `Z` is accepted and all values are normalized to UTC.

```jsonl
{"type":"trace","id":"historical-answer-17"}
{"type":"query","id":"q1","as_of":"2020-01-01T00:00:00Z","occurred_at":"2020-01-01T00:00:00Z","text":"What rule applied?"}
{"type":"document","id":"policy-v1","source_type":"policy","valid_from":"2018-01-01T00:00:00Z","valid_to":"2021-01-01T00:00:00Z","created_at":"2017-12-01T00:00:00Z","published_at":"2018-01-01T00:00:00Z","supersedes":[],"content":"The historical rule."}
{"type":"artifact","id":"index-2019","artifact_type":"embedding_index","built_at":"2019-12-01T00:00:00Z","knowledge_cutoff":"2019-12-01T00:00:00Z","source_document_ids":["policy-v1"]}
{"type":"retrieval","id":"r1","occurred_at":"2020-01-01T00:00:00Z","declared_as_of":"2020-01-01T00:00:00Z","document_ids":["policy-v1"],"artifact_ids":["index-2019"],"treatment":"current"}
{"type":"citation","id":"c1","document_id":"policy-v1","retrieval_id":"r1","start":0,"end":19,"text":"The historical rule"}
{"type":"model_knowledge","id":"mk1","model":"example-model","provider":"example","knowledge_cutoff":"2019-01-01T00:00:00Z","declared_at":"2019-01-01T00:00:00Z"}
```

The complete field contract is in [`docs/trace-schema.md`](docs/trace-schema.md). Runnable files are in [`examples/`](examples/).

## Temporal semantics

- `query.as_of` is the historical boundary against which consumed evidence is checked.
- Document validity is a half-open interval: **`[valid_from, valid_to)`**. A document with `valid_to == query.as_of` is expired.
- A timestamp equal to `query.as_of` is allowed for event checks; strictly later values violate the boundary.
- `created_at` and `published_at` are independent availability evidence. Either one being after the cutoff is a demonstrated post-cutoff source problem.
- `retrieval.declared_as_of` records the boundary enforced by the retrieval layer. It must exactly equal `query.as_of`.
- `retrieval.treatment` defaults to `current`. A predecessor whose successor was effective by the cutoff triggers `SUPERSEDED_AS_CURRENT` only when treated as current. Use `historical` when intentionally retrieving an older version as historical evidence.
- `memory_write.learned_at` identifies when information entered memory; `written_at` identifies persistence time. Both must be present and no later than the cutoff for a consumed memory; `memory_read.read_at` is checked separately.
- Artifact `built_at`, `knowledge_cutoff`, and `source_document_ids` jointly describe embedding/reranker provenance; the first two are required for a decidable used-artifact check.
- A model declaration is evidence, not proof. `MODEL_WEIGHT_PURITY_UNVERIFIABLE` is always emitted as a note.

## Verdict model

Findings have one of three categories:

- `observable_failure`: evidence directly demonstrates a temporal or provenance failure;
- `metadata_gap`: evidence needed to decide is absent;
- `model_weight_uncertainty`: uncertainty intrinsic to model-weight inspection.

The aggregate status is:

- `contaminated` if any `observable_failure` exists;
- otherwise `indeterminate` if any `metadata_gap` exists or the declared model knowledge cutoff exceeds `query.as_of`;
- otherwise `clean` (while the irreducible weight-purity note remains).

JSON reports include:

- `contaminating_items`: deduplicated `{type, id}` objects for every observable failure;
- `earliest_invalid_timestamp`: minimum timestamp among observable failures with a timestamp;
- separate counts for observable failures, metadata gaps, and model-weight uncertainty;
- `model_weight_purity: "unverifiable"` on every verdict.

Untimed structural failures, such as a citation not tied to a retrieval or a supersession cycle, are exact observable failures but cannot contribute a timestamp. If all failures are untimed, `earliest_invalid_timestamp` is `null`.

## Synthetic adversarial corpus

The package ships with more than forty deterministic adversarial scenarios plus one complete clean historical scenario, including:

- later case and later policy contamination;
- stale, future, expired, and superseded documents;
- future-built embeddings and rerankers;
- artifact corpus and knowledge-boundary leakage;
- post-cutoff memory learning, reads, and source provenance;
- missing query, document, retrieval, memory, artifact, and model timestamps;
- citation range, retrieval, and source-text failures;
- multiple simultaneous contaminants with an earliest-invalid-time assertion;
- a complete clean historical scenario.

Fixture headers contain expected status and required finding codes. The unit suite verifies the entire fixture catalog against those expectations.

## Python API

```python
from asof_guard import load_trace, verify_trace
from asof_guard.reporting import render_json

trace = load_trace("trace.jsonl")
verdict = verify_trace(trace)
print(verdict.status.value)
print(render_json(verdict))
```

The parser preserves absent timestamps as `None` so they become auditable `metadata_gap` findings. Invalid timestamps, duplicate identifiers, unknown record types, naive datetimes, and malformed JSON fail fast with `TraceFormatError`.

## Development

The project uses only the standard library for implementation and tests:

```bash
./ci/check.sh
```

That command runs all `unittest` tests, validates every packaged fixture, and compiles source and tests with `compileall`.

See [`CONTRIBUTING.md`](CONTRIBUTING.md), [`SECURITY.md`](SECURITY.md), and [`CHANGELOG.md`](CHANGELOG.md).

## License

Apache License 2.0. See [`LICENSE`](LICENSE).
