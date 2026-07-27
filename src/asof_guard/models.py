"""Typed, dependency-free data models used by AsOfGuard.

The models deliberately retain missing timestamps as ``None``.  A malformed JSONL
record is a syntax error, while absent temporal evidence is a verifier finding.
This distinction lets callers see exactly why a trace cannot be proved safe.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple


UTC = timezone.utc


class TraceFormatError(ValueError):
    """Raised when JSONL cannot be interpreted as an AsOfGuard trace."""


def parse_timestamp(value: Any, field_name: str) -> Optional[datetime]:
    """Parse a timezone-aware ISO-8601 timestamp and normalize it to UTC.

    ``None`` is preserved so the verifier can report missing temporal metadata.
    Naive datetimes are rejected because silently guessing a timezone would itself
    undermine temporal verification.
    """

    if value is None:
        return None
    if not isinstance(value, str):
        raise TraceFormatError(f"{field_name} must be an ISO-8601 string or null")
    candidate = value.strip()
    if candidate.endswith("Z"):
        candidate = candidate[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(candidate)
    except ValueError as exc:
        raise TraceFormatError(f"{field_name} is not a valid ISO-8601 timestamp: {value!r}") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise TraceFormatError(f"{field_name} must include a UTC offset: {value!r}")
    return parsed.astimezone(UTC)


def format_timestamp(value: Optional[datetime]) -> Optional[str]:
    """Serialize a datetime in canonical UTC form."""

    if value is None:
        return None
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


@dataclass(frozen=True)
class Query:
    id: str
    as_of: Optional[datetime]
    text: str = ""
    occurred_at: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Document:
    id: str
    valid_from: Optional[datetime]
    valid_to: Optional[datetime] = None
    created_at: Optional[datetime] = None
    published_at: Optional[datetime] = None
    supersedes: Tuple[str, ...] = ()
    superseded_at: Optional[datetime] = None
    source_type: str = "document"
    title: str = ""
    content: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def earliest_availability(self) -> Optional[datetime]:
        values = [value for value in (self.valid_from, self.published_at, self.created_at) if value is not None]
        return min(values) if values else None


@dataclass(frozen=True)
class Artifact:
    id: str
    artifact_type: str
    built_at: Optional[datetime]
    source_document_ids: Tuple[str, ...] = ()
    knowledge_cutoff: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class RetrievalEvent:
    id: str
    occurred_at: Optional[datetime]
    document_ids: Tuple[str, ...]
    artifact_ids: Tuple[str, ...] = ()
    declared_as_of: Optional[datetime] = None
    treatment: str = "current"
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class MemoryWrite:
    id: str
    learned_at: Optional[datetime]
    written_at: Optional[datetime] = None
    source_document_ids: Tuple[str, ...] = ()
    content: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class MemoryRead:
    id: str
    memory_id: str
    read_at: Optional[datetime]
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class CitedSpan:
    id: str
    document_id: str
    start: Optional[int]
    end: Optional[int]
    text: Optional[str] = None
    retrieval_id: Optional[str] = None


@dataclass(frozen=True)
class ModelKnowledgeDeclaration:
    model: str
    knowledge_cutoff: Optional[datetime]
    declared_at: Optional[datetime] = None
    provider: str = ""
    declaration_id: str = "model"


@dataclass
class Trace:
    id: str
    query: Optional[Query] = None
    documents: Dict[str, Document] = field(default_factory=dict)
    artifacts: Dict[str, Artifact] = field(default_factory=dict)
    retrievals: List[RetrievalEvent] = field(default_factory=list)
    memory_writes: Dict[str, MemoryWrite] = field(default_factory=dict)
    memory_reads: List[MemoryRead] = field(default_factory=list)
    citations: List[CitedSpan] = field(default_factory=list)
    model_knowledge: Optional[ModelKnowledgeDeclaration] = None
    expectations: Dict[str, Any] = field(default_factory=dict)


class FindingCategory(str, Enum):
    OBSERVABLE_FAILURE = "observable_failure"
    METADATA_GAP = "metadata_gap"
    MODEL_WEIGHT_UNCERTAINTY = "model_weight_uncertainty"


class Severity(str, Enum):
    ERROR = "error"
    WARNING = "warning"
    NOTE = "note"


@dataclass(frozen=True)
class Finding:
    code: str
    title: str
    category: FindingCategory
    severity: Severity
    message: str
    item_type: str
    item_id: str
    timestamp: Optional[datetime] = None
    evidence: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        result: Dict[str, Any] = {
            "code": self.code,
            "title": self.title,
            "category": self.category.value,
            "severity": self.severity.value,
            "message": self.message,
            "item": {"type": self.item_type, "id": self.item_id},
            "timestamp": format_timestamp(self.timestamp),
        }
        if self.evidence:
            result["evidence"] = self.evidence
        return result


class VerdictStatus(str, Enum):
    CLEAN = "clean"
    CONTAMINATED = "contaminated"
    INDETERMINATE = "indeterminate"


@dataclass(frozen=True)
class Verdict:
    trace_id: str
    status: VerdictStatus
    findings: Tuple[Finding, ...]
    earliest_invalid_timestamp: Optional[datetime]
    contaminating_items: Tuple[Tuple[str, str], ...]
    model_weight_purity: str = "unverifiable"

    @property
    def observable_failures(self) -> Tuple[Finding, ...]:
        return tuple(f for f in self.findings if f.category is FindingCategory.OBSERVABLE_FAILURE)

    @property
    def metadata_gaps(self) -> Tuple[Finding, ...]:
        return tuple(f for f in self.findings if f.category is FindingCategory.METADATA_GAP)

    @property
    def uncertainties(self) -> Tuple[Finding, ...]:
        return tuple(f for f in self.findings if f.category is FindingCategory.MODEL_WEIGHT_UNCERTAINTY)

    @property
    def exit_code(self) -> int:
        if self.status is VerdictStatus.CONTAMINATED:
            return 2
        if self.status is VerdictStatus.INDETERMINATE:
            return 3
        return 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "schema_version": "1.0",
            "trace_id": self.trace_id,
            "status": self.status.value,
            "scope": "observable_trace_events_plus_declared_model_boundary",
            "observable_temporal_integrity": (
                "failed"
                if self.observable_failures
                else "indeterminate"
                if self.metadata_gaps
                else "passed"
            ),
            "model_weight_purity": self.model_weight_purity,
            "summary": {
                "observable_failures": len(self.observable_failures),
                "metadata_gaps": len(self.metadata_gaps),
                "model_weight_uncertainties": len(self.uncertainties),
            },
            "earliest_invalid_timestamp": format_timestamp(self.earliest_invalid_timestamp),
            "contaminating_items": [
                {"type": item_type, "id": item_id} for item_type, item_id in self.contaminating_items
            ],
            "findings": [finding.to_dict() for finding in self.findings],
        }
