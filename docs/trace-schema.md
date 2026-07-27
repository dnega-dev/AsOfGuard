# AsOfGuard JSONL trace schema

Schema version: **1.0**

AsOfGuard consumes newline-delimited JSON (JSONL): one record object per non-empty line. Lines beginning with `#` are comments. Record order is flexible; identifiers resolve across the complete file.

This document is a normative field contract for the 0.1 verifier. It is descriptive rather than a JSON Schema file because JSON Schema does not directly model cross-line identity and temporal relationships.

## Common rules

- Every record has a string `type`.
- IDs are non-empty, case-sensitive strings and must be unique within their record namespace.
- Timestamps are strings accepted by `datetime.fromisoformat`, must include a UTC offset, and may use `Z` for UTC. They are normalized to UTC.
- A missing or JSON `null` temporal value is retained as missing evidence. The verifier emits a metadata-gap finding when that value is needed.
- Arrays of identifiers must be JSON arrays containing non-empty strings.
- Unknown record types, malformed JSON, duplicate IDs, invalid field types, and naive timestamps are input errors.
- Unknown extra fields are ignored, allowing producers to add data without breaking version 1.0 consumers. Put producer-specific fields under `metadata` where practical.

## Timestamp comparison

The query boundary is `query.as_of`.

- `event_time > as_of` is post-cutoff.
- `event_time == as_of` is permitted.
- Document validity is the half-open interval `[valid_from, valid_to)`.
- Therefore `valid_from > as_of` is not yet valid, and `valid_to <= as_of` is expired.
- All comparisons happen after normalization to UTC.

## `trace`

Optional header. At most one.

```json
{
  "type": "trace",
  "id": "run-123",
  "expectations": {
    "status": "clean",
    "codes": [],
    "description": "Used by synthetic fixtures"
  }
}
```

| Field | Required | Type | Meaning |
| --- | --- | --- | --- |
| `id` | yes | string | Trace/report identifier. |
| `expectations` | no | object | Fixture-only expected results; ignored by verification. |

If omitted, the parser derives a trace ID from the source filename.

## `query`

Exactly one is needed for a decidable verification result.

```json
{
  "type": "query",
  "id": "q1",
  "text": "What policy applied?",
  "as_of": "2020-01-01T00:00:00Z",
  "occurred_at": "2020-01-01T00:00:00Z",
  "metadata": {"tenant": "example"}
}
```

| Field | Required | Type | Meaning |
| --- | --- | --- | --- |
| `id` | yes | string | Query identifier. |
| `as_of` | for decision | timestamp/null | Historical knowledge boundary. Missing yields `MISSING_QUERY_AS_OF`. |
| `text` | no | string | Query text for audit context. |
| `occurred_at` | no | timestamp/null | When the query event occurred. It does not replace `as_of`. |
| `metadata` | no | object | Producer-defined query context. |

## `document`

One record per immutable source version.

```json
{
  "type": "document",
  "id": "policy-v2",
  "title": "Policy version 2",
  "source_type": "policy",
  "valid_from": "2019-06-01T00:00:00Z",
  "valid_to": null,
  "created_at": "2019-05-20T00:00:00Z",
  "published_at": "2019-06-01T00:00:00Z",
  "supersedes": ["policy-v1"],
  "superseded_at": null,
  "content": "Exact immutable source text",
  "metadata": {"uri": "urn:policy:2"}
}
```

| Field | Required | Type | Meaning |
| --- | --- | --- | --- |
| `id` | yes | string | Immutable source-version ID. |
| `valid_from` | for decision | timestamp/null | Inclusive start of validity. |
| `valid_to` | no | timestamp/null | Exclusive end of validity; null means open-ended. |
| `created_at` | one availability value | timestamp/null | When this version was created. |
| `published_at` | one availability value | timestamp/null | When this version became externally available. |
| `supersedes` | no | string array | Direct predecessor version IDs. Defaults to `[]`. |
| `superseded_at` | no | timestamp/null | Explicit time this version ceased being current. |
| `source_type` | no | string | `document` by default. Case-like types (`case`, `case_law`, `judgment`, `decision`) and policy-like types (`policy`, `regulation`, `guidance`, `procedure`) receive specialized rule codes. |
| `title` | no | string | Human label. |
| `content` | no | string/null | Exact immutable text used to validate citation offsets. |
| `metadata` | no | object | Producer-defined provenance. |

A consumed document needs `valid_from` and at least one of `created_at` or `published_at`. If either provided availability value is later than the cutoff, the source is post-cutoff. `valid_to <= valid_from` is an observable invalid-window failure.

A document is "consumed" when directly retrieved or cited, when it supplies a read memory, or when it appears in a used artifact's source corpus.

### Supersession

`successor.supersedes` points backward. When `successor.valid_from` (falling back to publication/creation) is at or before `query.as_of`, retrieving its predecessor with `treatment: "current"` triggers `SUPERSEDED_AS_CURRENT`. If a relevant successor has none of those timestamps, `MISSING_SUPERSESSION_EFFECTIVE_AT` makes the result indeterminate. `document.superseded_at` may assert the boundary even if a successor record is not present. Cycles are invalid.

## `artifact`

Represents a retrieval-time derived artifact such as an embedding index, vector-store snapshot, BM25 index, reranker, or query-expansion model.

```json
{
  "type": "artifact",
  "id": "index-2019-12",
  "artifact_type": "embedding_index",
  "built_at": "2019-12-01T00:00:00Z",
  "knowledge_cutoff": "2019-11-30T23:59:59Z",
  "source_document_ids": ["policy-v1"],
  "metadata": {"digest": "sha256:..."}
}
```

| Field | Required | Type | Meaning |
| --- | --- | --- | --- |
| `id` | yes | string | Artifact identifier. |
| `artifact_type` | yes | string | Kind of artifact, e.g. `embedding_index` or `reranker`. |
| `built_at` | for decision | timestamp/null | Build/snapshot time. |
| `knowledge_cutoff` | for decision | timestamp/null | Declared latest knowledge represented by the artifact. Missing yields a metadata gap. |
| `source_document_ids` | no | string array | Exact corpus provenance. |
| `metadata` | no | object | Hashes, model versions, index parameters, etc. |

Only artifacts referenced by a retrieval are checked as used. Their listed documents are also checked as consumed.

## `retrieval`

```json
{
  "type": "retrieval",
  "id": "r1",
  "occurred_at": "2020-01-01T00:00:00Z",
  "declared_as_of": "2020-01-01T00:00:00Z",
  "document_ids": ["policy-v1"],
  "artifact_ids": ["index-2019-12", "reranker-2019"],
  "treatment": "current",
  "metadata": {"top_k": 5}
}
```

| Field | Required | Type | Meaning |
| --- | --- | --- | --- |
| `id` | yes | string | Retrieval event identifier. |
| `occurred_at` | for decision | timestamp/null | Wall-clock execution time. |
| `declared_as_of` | for decision | timestamp/null | Boundary actually enforced by retrieval. Must equal `query.as_of`. |
| `document_ids` | no | string array | Returned source versions. Defaults to `[]`. |
| `artifact_ids` | no | string array | Used embedding/reranking artifacts. Defaults to `[]`. |
| `treatment` | no | string | `current` (default) or `historical`. Other values create an indeterminate metadata gap. |
| `metadata` | no | object | Scores, rank, filters, and producer evidence. |

AsOfGuard treats every returned document as potentially available to answer generation, not only cited documents. This is conservative for contamination analysis.

## `memory_write`

A memory's provenance declaration. It may be emitted before or after the read record in JSONL.

```json
{
  "type": "memory_write",
  "id": "memory-7",
  "learned_at": "2019-05-01T00:00:00Z",
  "written_at": "2019-05-01T00:01:00Z",
  "source_document_ids": ["policy-v1"],
  "content": "The historical rule applies.",
  "metadata": {"namespace": "legal"}
}
```

| Field | Required | Type | Meaning |
| --- | --- | --- | --- |
| `id` | yes | string | Memory identifier read by `memory_read.memory_id`. |
| `learned_at` | for consumed memory | timestamp/null | When the information first entered memory. |
| `written_at` | for consumed memory | timestamp/null | When it was persisted; distinct from knowledge acquisition. Missing yields a metadata gap. |
| `source_document_ids` | no | string array | Source provenance for the memory. |
| `content` | no | string | Auditable memory content. |
| `metadata` | no | object | Namespace, owner, write reason, etc. |

## `memory_read`

```json
{
  "type": "memory_read",
  "id": "mr1",
  "memory_id": "memory-7",
  "read_at": "2020-01-01T00:00:00Z",
  "metadata": {"reason": "prompt context"}
}
```

| Field | Required | Type | Meaning |
| --- | --- | --- | --- |
| `id` | yes | string | Memory-read event ID. |
| `memory_id` | yes | string | Referenced `memory_write.id`. |
| `read_at` | for decision | timestamp/null | When the memory entered the run. |
| `metadata` | no | object | Producer-defined context. |

Only read memories are considered consumed. An unreferenced write does not contaminate a run. For a consumed memory, `learned_at`, `written_at`, and `memory_read.read_at` must all be present and no later than `query.as_of`.

## `citation`

Character offsets are zero-based and half-open (`[start, end)`).

```json
{
  "type": "citation",
  "id": "c1",
  "document_id": "policy-v1",
  "retrieval_id": "r1",
  "start": 0,
  "end": 19,
  "text": "The historical rule"
}
```

| Field | Required | Type | Meaning |
| --- | --- | --- | --- |
| `id` | yes | string | Citation identifier. |
| `document_id` | yes | string | Exact cited source version. |
| `retrieval_id` | no | string/null | Retrieval that supplied the source. If absent, any retrieval or a read memory's source provenance may supply it. |
| `start` | for span validation | integer/null | Inclusive start character offset. |
| `end` | for span validation | integer/null | Exclusive end offset. Must exceed `start`. |
| `text` | no | string/null | Supplied cited text. Compared exactly when document content is available. |

A citation is also a document-consumption signal. Missing source content creates `MISSING_CITATION_SOURCE_CONTENT` because the upper bound and exact text cannot be fully verified; offsets must still be present, non-negative, and ordered.

## `model_knowledge`

At most one declaration.

```json
{
  "type": "model_knowledge",
  "id": "mk1",
  "model": "provider/model-version",
  "provider": "provider",
  "knowledge_cutoff": "2019-01-01T00:00:00Z",
  "declared_at": "2019-02-01T00:00:00Z"
}
```

| Field | Required | Type | Meaning |
| --- | --- | --- | --- |
| `id` | no | string | Declaration ID; defaults to `model`. |
| `model` | yes | string | Stable model/version identifier. |
| `provider` | no | string | Declaration source. |
| `knowledge_cutoff` | for evidence | timestamp/null | Provider-declared latest training knowledge. |
| `declared_at` | no | timestamp/null | When the declaration was made. |

If the declared cutoff is later than `query.as_of`, AsOfGuard emits `MODEL_KNOWLEDGE_AFTER_CUTOFF` as **model-weight uncertainty**, not an observable event failure, and the aggregate verdict is `indeterminate` unless an observable failure makes it `contaminated`. In all cases it also emits `MODEL_WEIGHT_PURITY_UNVERIFIABLE`. Model declarations are not cryptographic proof of what affected a generation.

## Verdict JSON shape

`--format json` emits:

```json
{
  "schema_version": "1.0",
  "trace_id": "run-123",
  "status": "contaminated",
  "scope": "observable_trace_events_plus_declared_model_boundary",
  "observable_temporal_integrity": "failed",
  "model_weight_purity": "unverifiable",
  "summary": {
    "observable_failures": 1,
    "metadata_gaps": 0,
    "model_weight_uncertainties": 1
  },
  "earliest_invalid_timestamp": "2021-01-01T00:00:00Z",
  "contaminating_items": [{"type": "document", "id": "policy-v2"}],
  "findings": [
    {
      "code": "LATER_POLICY_CONTAMINATION",
      "title": "Later policy contaminated a historical query",
      "category": "observable_failure",
      "severity": "error",
      "message": "Policy 'policy-v2' first became available after query cutoff 2020-01-01T00:00:00Z.",
      "item": {"type": "document", "id": "policy-v2"},
      "timestamp": "2021-01-01T00:00:00Z"
    },
    {
      "code": "MODEL_WEIGHT_PURITY_UNVERIFIABLE",
      "title": "Model-weight purity is irreducibly unverifiable",
      "category": "model_weight_uncertainty",
      "severity": "note",
      "message": "Observable trace events can be verified, but opaque model weights cannot be proven free of post-cutoff knowledge from this trace.",
      "item": {"type": "model", "id": "example-model"},
      "timestamp": null
    }
  ]
}
```

Each finding contains `code`, `title`, `category`, `severity`, `message`, an `item` object, optional `timestamp`, and optional rule-specific `evidence`. `observable_temporal_integrity` is `failed` when an observable failure exists, `indeterminate` when event evidence is missing, and `passed` otherwise; this field remains independent of the always-unverifiable model-weight-purity claim.

## Producer checklist

1. Assign immutable IDs to exact document versions.
2. Propagate `query.as_of` into `retrieval.declared_as_of` without reinterpretation.
3. Timestamp retrievals, memory acquisition, memory reads, and artifact builds.
4. Preserve artifact source-document IDs and model/version hashes.
5. Log every returned retrieval item, not only citations.
6. Link citations to the retrieval and immutable source version.
7. Emit a model knowledge declaration, but do not describe it as proof of weight purity.
8. Keep clocks timezone-aware and synchronized; record clock source in `metadata` when assurance demands it.
