"""Rule catalogue used by verification, CLI explanations, and SARIF output."""

from __future__ import annotations

from typing import Dict, Iterable, Mapping


RULES: Dict[str, Dict[str, str]] = {
    "MISSING_QUERY": {
        "title": "Query record is missing",
        "description": "No query record exists, so the intended historical cutoff cannot be established.",
        "remediation": "Emit exactly one query record with a timezone-aware as_of timestamp.",
    },
    "MISSING_QUERY_AS_OF": {
        "title": "Query cutoff is missing",
        "description": "The query has no as_of timestamp.",
        "remediation": "Populate query.as_of with the historical knowledge boundary.",
    },
    "MISSING_DOCUMENT_VALID_FROM": {
        "title": "Document validity start is missing",
        "description": "A retrieved or cited document has no valid_from timestamp.",
        "remediation": "Record when the material first became valid or available.",
    },
    "MISSING_DOCUMENT_AVAILABILITY": {
        "title": "Document availability timestamp is missing",
        "description": "A retrieved or cited document has neither created_at nor published_at.",
        "remediation": "Record when the exact source version became externally available.",
    },
    "INVALID_DOCUMENT_WINDOW": {
        "title": "Document validity window is invalid",
        "description": "valid_to is not later than valid_from.",
        "remediation": "Correct the validity interval; valid_to is an exclusive boundary.",
    },
    "UNKNOWN_DOCUMENT": {
        "title": "Referenced document is absent",
        "description": "An event references a document id with no matching document record.",
        "remediation": "Include the referenced document and its temporal metadata.",
    },
    "MISSING_RETRIEVAL_TIMESTAMP": {
        "title": "Retrieval timestamp is missing",
        "description": "A retrieval event has no occurred_at timestamp.",
        "remediation": "Capture the wall-clock time of every retrieval event.",
    },
    "POST_CUTOFF_RETRIEVAL": {
        "title": "Retrieval occurred after the query cutoff",
        "description": "A retrieval event happened later than query.as_of.",
        "remediation": "Replay against a cutoff-pinned index or justify a faithful historical snapshot.",
    },
    "RETRIEVAL_AS_OF_MISMATCH": {
        "title": "Retriever cutoff does not match query cutoff",
        "description": "The retrieval declared a different as_of boundary than the query.",
        "remediation": "Propagate query.as_of unchanged through the retrieval stack.",
    },
    "UNKNOWN_RETRIEVAL_TREATMENT": {
        "title": "Retrieval treatment is unknown",
        "description": "The verifier cannot tell whether a returned version was presented as current or historical.",
        "remediation": "Set retrieval.treatment to current or historical.",
    },
    "DOCUMENT_NOT_YET_VALID": {
        "title": "Document was not yet valid",
        "description": "Document valid_from is later than query.as_of.",
        "remediation": "Exclude versions whose validity starts after the historical cutoff.",
    },
    "POST_CUTOFF_DOCUMENT": {
        "title": "Document availability is after cutoff",
        "description": "Document creation or publication metadata shows post-cutoff material.",
        "remediation": "Use a document snapshot that existed by query.as_of.",
    },
    "EXPIRED_DOCUMENT": {
        "title": "Document was expired at query time",
        "description": "Document valid_to is at or before query.as_of.",
        "remediation": "Retrieve the version valid at query.as_of, or label the expired version as historical.",
    },
    "SUPERSEDED_AS_CURRENT": {
        "title": "Superseded content treated as current",
        "description": "A successor version was already effective, but the retrieval treated the predecessor as current.",
        "remediation": "Resolve supersession chains at query.as_of or mark the predecessor treatment as historical.",
    },
    "SUPERSESSION_CYCLE": {
        "title": "Supersession chain contains a cycle",
        "description": "Version relationships are cyclic and cannot establish a current version.",
        "remediation": "Correct supersedes links to form an acyclic version graph.",
    },
    "MISSING_SUPERSESSION_EFFECTIVE_AT": {
        "title": "Successor effective timestamp is missing",
        "description": "A declared successor has no validity, publication, or creation timestamp.",
        "remediation": "Timestamp when the successor became effective so predecessor currency can be decided.",
    },
    "LATER_CASE_CONTAMINATION": {
        "title": "Later case contaminated a historical query",
        "description": "A retrieved case first became available after query.as_of.",
        "remediation": "Use an as-of-filtered case corpus.",
    },
    "LATER_POLICY_CONTAMINATION": {
        "title": "Later policy contaminated a historical query",
        "description": "A retrieved policy first became available after query.as_of.",
        "remediation": "Use the policy version effective at query.as_of.",
    },
    "UNKNOWN_ARTIFACT": {
        "title": "Referenced retrieval artifact is absent",
        "description": "A retrieval references an embedding or reranker artifact with no matching record.",
        "remediation": "Include artifact provenance and build timestamps.",
    },
    "MISSING_ARTIFACT_TIMESTAMP": {
        "title": "Artifact build timestamp is missing",
        "description": "An embedding, index, or reranker artifact has no built_at timestamp.",
        "remediation": "Stamp each artifact build and preserve immutable provenance.",
    },
    "MISSING_ARTIFACT_KNOWLEDGE_CUTOFF": {
        "title": "Artifact knowledge boundary is missing",
        "description": "A used retrieval artifact does not declare its latest represented knowledge.",
        "remediation": "Declare the artifact knowledge cutoff in addition to its build time.",
    },
    "ARTIFACT_BUILT_AFTER_CUTOFF": {
        "title": "Retrieval artifact was built after cutoff",
        "description": "An embedding, index, or reranker artifact was constructed after query.as_of.",
        "remediation": "Pin retrieval to an artifact built no later than query.as_of.",
    },
    "ARTIFACT_SOURCE_AFTER_CUTOFF": {
        "title": "Artifact includes a post-cutoff source",
        "description": "Artifact provenance includes a document unavailable at query.as_of.",
        "remediation": "Rebuild the artifact from a cutoff-filtered source set.",
    },
    "ARTIFACT_KNOWLEDGE_AFTER_CUTOFF": {
        "title": "Artifact knowledge boundary exceeds cutoff",
        "description": "The artifact declares a knowledge cutoff later than query.as_of.",
        "remediation": "Use a cutoff-compatible embedding or reranker artifact.",
    },
    "MISSING_MEMORY_REFERENCE": {
        "title": "Memory read has no matching write",
        "description": "A memory read references an unknown memory id.",
        "remediation": "Log the originating write and temporal provenance.",
    },
    "MISSING_MEMORY_LEARNED_AT": {
        "title": "Memory learning timestamp is missing",
        "description": "A consumed memory has no learned_at timestamp.",
        "remediation": "Capture when the fact first entered memory, distinct from persistence time.",
    },
    "MISSING_MEMORY_WRITTEN_AT": {
        "title": "Memory write timestamp is missing",
        "description": "A consumed memory has no written_at persistence timestamp.",
        "remediation": "Timestamp the memory write separately from the knowledge acquisition time.",
    },
    "MISSING_MEMORY_READ_AT": {
        "title": "Memory read timestamp is missing",
        "description": "A memory read has no read_at timestamp.",
        "remediation": "Timestamp every memory access.",
    },
    "MEMORY_LEARNED_AFTER_CUTOFF": {
        "title": "Memory was learned after cutoff",
        "description": "The model consumed a memory whose learned_at is later than query.as_of.",
        "remediation": "Filter memory by learned_at <= query.as_of.",
    },
    "MEMORY_WRITTEN_AFTER_CUTOFF": {
        "title": "Memory was persisted after cutoff",
        "description": "The model consumed a memory whose written_at is later than query.as_of.",
        "remediation": "Read memory from a snapshot persisted no later than query.as_of.",
    },
    "MEMORY_READ_AFTER_CUTOFF": {
        "title": "Memory was read after cutoff",
        "description": "The memory read event occurred later than query.as_of.",
        "remediation": "Replay memory access from an as-of snapshot.",
    },
    "MEMORY_SOURCE_AFTER_CUTOFF": {
        "title": "Memory derives from post-cutoff material",
        "description": "A consumed memory cites a source document unavailable at query.as_of.",
        "remediation": "Preserve and enforce source-level temporal provenance for memories.",
    },
    "UNKNOWN_CITATION_DOCUMENT": {
        "title": "Citation document is absent",
        "description": "A citation references an unknown document id.",
        "remediation": "Include the cited document record and its validity metadata.",
    },
    "MISSING_CITATION_SOURCE_CONTENT": {
        "title": "Citation source content is missing",
        "description": "The exact immutable source text is absent, so cited offsets cannot be fully checked.",
        "remediation": "Include the exact cited document version's content or an equivalent immutable span proof.",
    },
    "CITATION_INVALID_RANGE": {
        "title": "Citation span range is invalid",
        "description": "The cited offsets are missing, negative, reversed, or outside the source text.",
        "remediation": "Emit valid half-open character offsets into immutable source content.",
    },
    "CITATION_TEXT_MISMATCH": {
        "title": "Citation text does not match source span",
        "description": "The supplied citation text differs from content[start:end].",
        "remediation": "Regenerate the citation from the exact source version.",
    },
    "CITATION_NOT_RETRIEVED": {
        "title": "Cited document was not supplied",
        "description": "No retrieval or consumed-memory provenance supplies the cited document, or the named retrieval does not supply it.",
        "remediation": "Log the retrieval or memory provenance that introduced every cited source.",
    },
    "MISSING_MODEL_KNOWLEDGE_DECLARATION": {
        "title": "Model knowledge declaration is missing",
        "description": "The trace does not declare the model and its training knowledge cutoff.",
        "remediation": "Record the provider/model identifier and declared knowledge cutoff.",
    },
    "MISSING_MODEL_KNOWLEDGE_CUTOFF": {
        "title": "Model knowledge cutoff is missing",
        "description": "A model is named but its knowledge cutoff is not declared.",
        "remediation": "Add the provider's documented knowledge cutoff, while retaining an uncertainty disclaimer.",
    },
    "MODEL_KNOWLEDGE_AFTER_CUTOFF": {
        "title": "Model weights may contain post-cutoff knowledge",
        "description": "The declared model knowledge cutoff is later than query.as_of.",
        "remediation": "Use a historically compatible model or treat model-weight purity as unverified.",
    },
    "MODEL_WEIGHT_PURITY_UNVERIFIABLE": {
        "title": "Model-weight purity is irreducibly unverifiable",
        "description": "Trace inspection can prove observable contamination but cannot prove which facts encoded in opaque weights influenced generation.",
        "remediation": "Report this uncertainty separately; do not describe a clean event trace as proof of pure model weights.",
    },
}


def explain_rule(code: str) -> Mapping[str, str]:
    """Return explanatory metadata for a rule code."""

    normalized = code.strip().upper()
    if normalized not in RULES:
        raise KeyError(normalized)
    return RULES[normalized]


def iter_rules() -> Iterable[tuple[str, Mapping[str, str]]]:
    """Yield rules in stable code order."""

    for code in sorted(RULES):
        yield code, RULES[code]
