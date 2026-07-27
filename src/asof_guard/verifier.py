"""Temporal contamination verification engine."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional, Set, Tuple

from .models import (
    Document,
    Finding,
    FindingCategory,
    Severity,
    Trace,
    Verdict,
    VerdictStatus,
    format_timestamp,
)
from .rules import RULES


class TemporalVerifier:
    """Verify observable trace events against the query's historical cutoff.

    The verifier is intentionally deterministic: the same parsed trace yields the
    same sorted findings and serialized verdict on every supported Python version.
    """

    def __init__(self, trace: Trace):
        self.trace = trace
        self.findings: List[Finding] = []
        self._finding_keys: Set[Tuple[str, str, str, Optional[datetime]]] = set()

    def verify(self) -> Verdict:
        """Run all verification rules and return a structured verdict."""

        query = self.trace.query
        if query is None:
            self._add(
                "MISSING_QUERY",
                FindingCategory.METADATA_GAP,
                Severity.ERROR,
                "Trace has no query record; no historical cutoff can be verified.",
                "trace",
                self.trace.id,
            )
            as_of = None
        else:
            as_of = query.as_of
            if as_of is None:
                self._add(
                    "MISSING_QUERY_AS_OF",
                    FindingCategory.METADATA_GAP,
                    Severity.ERROR,
                    f"Query {query.id!r} has no as_of timestamp.",
                    "query",
                    query.id,
                )

        consumed_documents = self._consumed_document_ids()
        self._check_document_metadata(consumed_documents, as_of)
        self._check_retrievals(as_of)
        self._check_supersession(as_of)
        self._check_artifacts(as_of)
        self._check_memories(as_of)
        self._check_citations()
        self._check_model_knowledge(as_of)

        self.findings.sort(
            key=lambda finding: (
                finding.timestamp is None,
                finding.timestamp or datetime.max.replace(tzinfo=as_of.tzinfo if as_of else None),
                finding.code,
                finding.item_type,
                finding.item_id,
            )
        )
        observable = [
            finding for finding in self.findings if finding.category is FindingCategory.OBSERVABLE_FAILURE
        ]
        gaps = [finding for finding in self.findings if finding.category is FindingCategory.METADATA_GAP]
        declared_weight_risk = any(
            finding.code == "MODEL_KNOWLEDGE_AFTER_CUTOFF" for finding in self.findings
        )
        if observable:
            status = VerdictStatus.CONTAMINATED
        elif gaps or declared_weight_risk:
            status = VerdictStatus.INDETERMINATE
        else:
            status = VerdictStatus.CLEAN

        timed_failures = [finding.timestamp for finding in observable if finding.timestamp is not None]
        earliest = min(timed_failures) if timed_failures else None
        contaminating_items = tuple(
            sorted({(finding.item_type, finding.item_id) for finding in observable})
        )
        return Verdict(
            trace_id=self.trace.id,
            status=status,
            findings=tuple(self.findings),
            earliest_invalid_timestamp=earliest,
            contaminating_items=contaminating_items,
            model_weight_purity="unverifiable",
        )

    def _add(
        self,
        code: str,
        category: FindingCategory,
        severity: Severity,
        message: str,
        item_type: str,
        item_id: str,
        timestamp: Optional[datetime] = None,
        evidence: Optional[Dict[str, Any]] = None,
    ) -> None:
        key = (code, item_type, item_id, timestamp)
        if key in self._finding_keys:
            return
        self._finding_keys.add(key)
        self.findings.append(
            Finding(
                code=code,
                title=RULES[code]["title"],
                category=category,
                severity=severity,
                message=message,
                item_type=item_type,
                item_id=item_id,
                timestamp=timestamp,
                evidence=evidence or {},
            )
        )

    def _consumed_document_ids(self) -> Set[str]:
        result: Set[str] = set()
        for retrieval in self.trace.retrievals:
            result.update(retrieval.document_ids)
            for artifact_id in retrieval.artifact_ids:
                artifact = self.trace.artifacts.get(artifact_id)
                if artifact is not None:
                    result.update(artifact.source_document_ids)
        for citation in self.trace.citations:
            result.add(citation.document_id)
        read_memory_ids = {read.memory_id for read in self.trace.memory_reads}
        for memory_id in read_memory_ids:
            memory = self.trace.memory_writes.get(memory_id)
            if memory is not None:
                result.update(memory.source_document_ids)
        return result

    def _check_document_metadata(self, document_ids: Set[str], as_of: Optional[datetime]) -> None:
        for document_id in sorted(document_ids):
            document = self.trace.documents.get(document_id)
            if document is None:
                self._add(
                    "UNKNOWN_DOCUMENT",
                    FindingCategory.METADATA_GAP,
                    Severity.ERROR,
                    f"Referenced document {document_id!r} has no document record.",
                    "document",
                    document_id,
                )
                continue
            if document.valid_from is None:
                self._add(
                    "MISSING_DOCUMENT_VALID_FROM",
                    FindingCategory.METADATA_GAP,
                    Severity.ERROR,
                    f"Document {document_id!r} has no valid_from timestamp.",
                    "document",
                    document_id,
                )
            if document.created_at is None and document.published_at is None:
                self._add(
                    "MISSING_DOCUMENT_AVAILABILITY",
                    FindingCategory.METADATA_GAP,
                    Severity.WARNING,
                    f"Document {document_id!r} has neither created_at nor published_at.",
                    "document",
                    document_id,
                )
            if (
                document.valid_from is not None
                and document.valid_to is not None
                and document.valid_to <= document.valid_from
            ):
                self._add(
                    "INVALID_DOCUMENT_WINDOW",
                    FindingCategory.OBSERVABLE_FAILURE,
                    Severity.ERROR,
                    f"Document {document_id!r} has valid_to <= valid_from.",
                    "document",
                    document_id,
                    document.valid_to,
                    {
                        "valid_from": format_timestamp(document.valid_from),
                        "valid_to": format_timestamp(document.valid_to),
                    },
                )
            if as_of is None:
                continue
            material_code = self._later_material_code(document)
            if (
                document.valid_from is not None
                and document.valid_from > as_of
                and material_code == "DOCUMENT_NOT_YET_VALID"
            ):
                self._add(
                    material_code,
                    FindingCategory.OBSERVABLE_FAILURE,
                    Severity.ERROR,
                    f"{document.source_type.title()} {document_id!r} became valid at "
                    f"{format_timestamp(document.valid_from)}, after query cutoff {format_timestamp(as_of)}.",
                    "document",
                    document_id,
                    document.valid_from,
                    {"query_as_of": format_timestamp(as_of), "valid_from": format_timestamp(document.valid_from)},
                )
            availability = [
                value
                for value in (document.created_at, document.published_at)
                if value is not None and value > as_of
            ]
            if availability:
                invalid_at = min(availability)
                self._add(
                    "POST_CUTOFF_DOCUMENT",
                    FindingCategory.OBSERVABLE_FAILURE,
                    Severity.ERROR,
                    f"Document {document_id!r} was created or published after query cutoff.",
                    "document",
                    document_id,
                    invalid_at,
                    {
                        "query_as_of": format_timestamp(as_of),
                        "created_at": format_timestamp(document.created_at),
                        "published_at": format_timestamp(document.published_at),
                    },
                )
            if material_code in {"LATER_CASE_CONTAMINATION", "LATER_POLICY_CONTAMINATION"}:
                later_times = [
                    value
                    for value in (document.valid_from, document.created_at, document.published_at)
                    if value is not None and value > as_of
                ]
                if later_times:
                    invalid_at = min(later_times)
                    self._add(
                        material_code,
                        FindingCategory.OBSERVABLE_FAILURE,
                        Severity.ERROR,
                        f"{document.source_type.title()} {document_id!r} first became available after "
                        f"query cutoff {format_timestamp(as_of)}.",
                        "document",
                        document_id,
                        invalid_at,
                        {
                            "query_as_of": format_timestamp(as_of),
                            "valid_from": format_timestamp(document.valid_from),
                            "created_at": format_timestamp(document.created_at),
                            "published_at": format_timestamp(document.published_at),
                        },
                    )
            if document.valid_to is not None and document.valid_to <= as_of:
                self._add(
                    "EXPIRED_DOCUMENT",
                    FindingCategory.OBSERVABLE_FAILURE,
                    Severity.ERROR,
                    f"Document {document_id!r} expired at {format_timestamp(document.valid_to)} "
                    f"and was not valid at query cutoff {format_timestamp(as_of)}.",
                    "document",
                    document_id,
                    document.valid_to,
                    {"query_as_of": format_timestamp(as_of), "valid_to": format_timestamp(document.valid_to)},
                )

    @staticmethod
    def _later_material_code(document: Document) -> str:
        source_type = document.source_type.lower().replace("-", "_")
        if source_type in {"case", "case_law", "judgment", "decision"}:
            return "LATER_CASE_CONTAMINATION"
        if source_type in {"policy", "regulation", "guidance", "procedure"}:
            return "LATER_POLICY_CONTAMINATION"
        return "DOCUMENT_NOT_YET_VALID"

    @staticmethod
    def _post_cutoff_source_timestamp(document: Document, as_of: datetime) -> Optional[datetime]:
        """Return the earliest supplied source timestamp that exceeds the cutoff."""

        post_cutoff = [
            value
            for value in (document.valid_from, document.created_at, document.published_at)
            if value is not None and value > as_of
        ]
        return min(post_cutoff) if post_cutoff else None

    def _check_retrievals(self, as_of: Optional[datetime]) -> None:
        for retrieval in self.trace.retrievals:
            if retrieval.treatment.lower() not in {"current", "historical"}:
                self._add(
                    "UNKNOWN_RETRIEVAL_TREATMENT",
                    FindingCategory.METADATA_GAP,
                    Severity.WARNING,
                    f"Retrieval {retrieval.id!r} uses unknown treatment {retrieval.treatment!r}.",
                    "retrieval",
                    retrieval.id,
                )
            if retrieval.occurred_at is None:
                self._add(
                    "MISSING_RETRIEVAL_TIMESTAMP",
                    FindingCategory.METADATA_GAP,
                    Severity.ERROR,
                    f"Retrieval {retrieval.id!r} has no occurred_at timestamp.",
                    "retrieval",
                    retrieval.id,
                )
            if as_of is None:
                continue
            if retrieval.occurred_at is not None and retrieval.occurred_at > as_of:
                self._add(
                    "POST_CUTOFF_RETRIEVAL",
                    FindingCategory.OBSERVABLE_FAILURE,
                    Severity.ERROR,
                    f"Retrieval {retrieval.id!r} occurred at {format_timestamp(retrieval.occurred_at)}, "
                    f"after query cutoff {format_timestamp(as_of)}.",
                    "retrieval",
                    retrieval.id,
                    retrieval.occurred_at,
                    {"query_as_of": format_timestamp(as_of)},
                )
            if retrieval.declared_as_of is None:
                self._add(
                    "RETRIEVAL_AS_OF_MISMATCH",
                    FindingCategory.METADATA_GAP,
                    Severity.WARNING,
                    f"Retrieval {retrieval.id!r} did not declare the as_of boundary it enforced.",
                    "retrieval",
                    retrieval.id,
                )
            elif retrieval.declared_as_of != as_of:
                self._add(
                    "RETRIEVAL_AS_OF_MISMATCH",
                    FindingCategory.OBSERVABLE_FAILURE,
                    Severity.ERROR,
                    f"Retrieval {retrieval.id!r} enforced {format_timestamp(retrieval.declared_as_of)} "
                    f"instead of query cutoff {format_timestamp(as_of)}.",
                    "retrieval",
                    retrieval.id,
                    retrieval.declared_as_of,
                    {"query_as_of": format_timestamp(as_of)},
                )

    def _check_supersession(self, as_of: Optional[datetime]) -> None:
        self._check_supersession_cycles(self._consumed_document_ids())
        if as_of is None:
            return
        successors: Dict[str, List[Document]] = {}
        for successor in self.trace.documents.values():
            for predecessor_id in successor.supersedes:
                successors.setdefault(predecessor_id, []).append(successor)

        for retrieval in self.trace.retrievals:
            if retrieval.treatment.lower() != "current":
                continue
            for document_id in retrieval.document_ids:
                document = self.trace.documents.get(document_id)
                if document is None:
                    continue
                invalid_times: List[datetime] = []
                successor_ids: List[str] = []
                if document.superseded_at is not None and document.superseded_at <= as_of:
                    invalid_times.append(document.superseded_at)
                for successor in successors.get(document_id, []):
                    effective = successor.valid_from or successor.published_at or successor.created_at
                    if effective is None:
                        self._add(
                            "MISSING_SUPERSESSION_EFFECTIVE_AT",
                            FindingCategory.METADATA_GAP,
                            Severity.ERROR,
                            f"Successor {successor.id!r} has no timestamp establishing when it superseded "
                            f"document {document_id!r}.",
                            "document",
                            successor.id,
                            evidence={"predecessor_id": document_id},
                        )
                    elif effective <= as_of:
                        invalid_times.append(effective)
                        successor_ids.append(successor.id)
                if invalid_times:
                    invalid_at = min(invalid_times)
                    self._add(
                        "SUPERSEDED_AS_CURRENT",
                        FindingCategory.OBSERVABLE_FAILURE,
                        Severity.ERROR,
                        f"Retrieval {retrieval.id!r} treated superseded document {document_id!r} as current.",
                        "document",
                        document_id,
                        invalid_at,
                        {
                            "retrieval_id": retrieval.id,
                            "successor_ids": sorted(successor_ids),
                            "query_as_of": format_timestamp(as_of),
                        },
                    )

    def _check_supersession_cycles(self, consumed_document_ids: Set[str]) -> None:
        graph = {document.id: tuple(document.supersedes) for document in self.trace.documents.values()}
        states: Dict[str, int] = {}
        stack: List[str] = []

        def visit(node: str) -> None:
            state = states.get(node, 0)
            if state == 2:
                return
            if state == 1:
                try:
                    cycle = stack[stack.index(node) :] + [node]
                except ValueError:
                    cycle = [node]
                if consumed_document_ids.intersection(cycle):
                    self._add(
                        "SUPERSESSION_CYCLE",
                        FindingCategory.OBSERVABLE_FAILURE,
                        Severity.ERROR,
                        "Supersession cycle detected: " + " -> ".join(cycle),
                        "document",
                        node,
                        evidence={"cycle": cycle},
                    )
                return
            states[node] = 1
            stack.append(node)
            for predecessor in graph.get(node, ()):
                if predecessor in graph:
                    visit(predecessor)
            stack.pop()
            states[node] = 2

        for document_id in sorted(graph):
            visit(document_id)

    def _check_artifacts(self, as_of: Optional[datetime]) -> None:
        used_artifact_ids = {
            artifact_id for retrieval in self.trace.retrievals for artifact_id in retrieval.artifact_ids
        }
        for artifact_id in sorted(used_artifact_ids):
            artifact = self.trace.artifacts.get(artifact_id)
            if artifact is None:
                self._add(
                    "UNKNOWN_ARTIFACT",
                    FindingCategory.METADATA_GAP,
                    Severity.ERROR,
                    f"Referenced artifact {artifact_id!r} has no artifact record.",
                    "artifact",
                    artifact_id,
                )
                continue
            if artifact.built_at is None:
                self._add(
                    "MISSING_ARTIFACT_TIMESTAMP",
                    FindingCategory.METADATA_GAP,
                    Severity.ERROR,
                    f"Artifact {artifact_id!r} has no built_at timestamp.",
                    "artifact",
                    artifact_id,
                )
            if artifact.knowledge_cutoff is None:
                self._add(
                    "MISSING_ARTIFACT_KNOWLEDGE_CUTOFF",
                    FindingCategory.METADATA_GAP,
                    Severity.WARNING,
                    f"Artifact {artifact_id!r} has no declared knowledge cutoff.",
                    "artifact",
                    artifact_id,
                )
            if as_of is None:
                continue
            if artifact.built_at is not None and artifact.built_at > as_of:
                self._add(
                    "ARTIFACT_BUILT_AFTER_CUTOFF",
                    FindingCategory.OBSERVABLE_FAILURE,
                    Severity.ERROR,
                    f"{artifact.artifact_type.title()} artifact {artifact_id!r} was built after query cutoff.",
                    "artifact",
                    artifact_id,
                    artifact.built_at,
                    {"query_as_of": format_timestamp(as_of)},
                )
            if artifact.knowledge_cutoff is not None and artifact.knowledge_cutoff > as_of:
                self._add(
                    "ARTIFACT_KNOWLEDGE_AFTER_CUTOFF",
                    FindingCategory.OBSERVABLE_FAILURE,
                    Severity.ERROR,
                    f"Artifact {artifact_id!r} declares knowledge through "
                    f"{format_timestamp(artifact.knowledge_cutoff)}, after the query cutoff.",
                    "artifact",
                    artifact_id,
                    artifact.knowledge_cutoff,
                    {"query_as_of": format_timestamp(as_of)},
                )
            for source_id in artifact.source_document_ids:
                source = self.trace.documents.get(source_id)
                if source is None:
                    # UNKNOWN_DOCUMENT is emitted by document metadata inspection.
                    continue
                available = self._post_cutoff_source_timestamp(source, as_of)
                if available is not None:
                    self._add(
                        "ARTIFACT_SOURCE_AFTER_CUTOFF",
                        FindingCategory.OBSERVABLE_FAILURE,
                        Severity.ERROR,
                        f"Artifact {artifact_id!r} includes post-cutoff source document {source_id!r}.",
                        "artifact",
                        artifact_id,
                        available,
                        {"source_document_id": source_id, "query_as_of": format_timestamp(as_of)},
                    )

    def _check_memories(self, as_of: Optional[datetime]) -> None:
        for read in self.trace.memory_reads:
            if read.read_at is None:
                self._add(
                    "MISSING_MEMORY_READ_AT",
                    FindingCategory.METADATA_GAP,
                    Severity.ERROR,
                    f"Memory read {read.id!r} has no read_at timestamp.",
                    "memory_read",
                    read.id,
                )
            memory = self.trace.memory_writes.get(read.memory_id)
            if memory is None:
                self._add(
                    "MISSING_MEMORY_REFERENCE",
                    FindingCategory.METADATA_GAP,
                    Severity.ERROR,
                    f"Memory read {read.id!r} references unknown memory {read.memory_id!r}.",
                    "memory",
                    read.memory_id,
                )
                continue
            if memory.learned_at is None:
                self._add(
                    "MISSING_MEMORY_LEARNED_AT",
                    FindingCategory.METADATA_GAP,
                    Severity.ERROR,
                    f"Consumed memory {memory.id!r} has no learned_at timestamp.",
                    "memory",
                    memory.id,
                )
            if memory.written_at is None:
                self._add(
                    "MISSING_MEMORY_WRITTEN_AT",
                    FindingCategory.METADATA_GAP,
                    Severity.WARNING,
                    f"Consumed memory {memory.id!r} has no written_at timestamp.",
                    "memory",
                    memory.id,
                )
            if as_of is None:
                continue
            if memory.learned_at is not None and memory.learned_at > as_of:
                self._add(
                    "MEMORY_LEARNED_AFTER_CUTOFF",
                    FindingCategory.OBSERVABLE_FAILURE,
                    Severity.ERROR,
                    f"Memory {memory.id!r} was learned after query cutoff.",
                    "memory",
                    memory.id,
                    memory.learned_at,
                    {"memory_read_id": read.id, "query_as_of": format_timestamp(as_of)},
                )
            if memory.written_at is not None and memory.written_at > as_of:
                self._add(
                    "MEMORY_WRITTEN_AFTER_CUTOFF",
                    FindingCategory.OBSERVABLE_FAILURE,
                    Severity.ERROR,
                    f"Memory {memory.id!r} was persisted after query cutoff.",
                    "memory",
                    memory.id,
                    memory.written_at,
                    {"memory_read_id": read.id, "query_as_of": format_timestamp(as_of)},
                )
            if read.read_at is not None and read.read_at > as_of:
                self._add(
                    "MEMORY_READ_AFTER_CUTOFF",
                    FindingCategory.OBSERVABLE_FAILURE,
                    Severity.ERROR,
                    f"Memory {memory.id!r} was read after query cutoff.",
                    "memory_read",
                    read.id,
                    read.read_at,
                    {"memory_id": memory.id, "query_as_of": format_timestamp(as_of)},
                )
            for source_id in memory.source_document_ids:
                source = self.trace.documents.get(source_id)
                if source is None:
                    continue
                available = self._post_cutoff_source_timestamp(source, as_of)
                if available is not None:
                    self._add(
                        "MEMORY_SOURCE_AFTER_CUTOFF",
                        FindingCategory.OBSERVABLE_FAILURE,
                        Severity.ERROR,
                        f"Memory {memory.id!r} derives from post-cutoff document {source_id!r}.",
                        "memory",
                        memory.id,
                        available,
                        {"source_document_id": source_id, "query_as_of": format_timestamp(as_of)},
                    )

    def _check_citations(self) -> None:
        retrievals_by_id = {retrieval.id: retrieval for retrieval in self.trace.retrievals}
        all_supplied = {
            document_id for retrieval in self.trace.retrievals for document_id in retrieval.document_ids
        }
        for read in self.trace.memory_reads:
            memory = self.trace.memory_writes.get(read.memory_id)
            if memory is not None:
                all_supplied.update(memory.source_document_ids)
        for citation in self.trace.citations:
            document = self.trace.documents.get(citation.document_id)
            if document is None:
                self._add(
                    "UNKNOWN_CITATION_DOCUMENT",
                    FindingCategory.METADATA_GAP,
                    Severity.ERROR,
                    f"Citation {citation.id!r} references unknown document {citation.document_id!r}.",
                    "citation",
                    citation.id,
                )
                continue
            if citation.retrieval_id is not None:
                retrieval = retrievals_by_id.get(citation.retrieval_id)
                supplied = retrieval is not None and citation.document_id in retrieval.document_ids
            else:
                supplied = citation.document_id in all_supplied
            if not supplied:
                self._add(
                    "CITATION_NOT_RETRIEVED",
                    FindingCategory.OBSERVABLE_FAILURE,
                    Severity.ERROR,
                    f"Citation {citation.id!r} cites document {citation.document_id!r} without a matching "
                    "retrieval or consumed-memory provenance.",
                    "citation",
                    citation.id,
                    evidence={"document_id": citation.document_id},
                )
            if document.content is None:
                self._add(
                    "MISSING_CITATION_SOURCE_CONTENT",
                    FindingCategory.METADATA_GAP,
                    Severity.WARNING,
                    f"Citation {citation.id!r} cannot be fully checked because document "
                    f"{document.id!r} has no immutable content.",
                    "citation",
                    citation.id,
                    evidence={"document_id": document.id},
                )

            invalid_range = (
                citation.start is None
                or citation.end is None
                or citation.start < 0
                or citation.end <= citation.start
                or (document.content is not None and citation.end > len(document.content))
            )
            if invalid_range:
                self._add(
                    "CITATION_INVALID_RANGE",
                    FindingCategory.OBSERVABLE_FAILURE,
                    Severity.ERROR,
                    f"Citation {citation.id!r} has an invalid source span.",
                    "citation",
                    citation.id,
                    evidence={"start": citation.start, "end": citation.end},
                )
            elif document.content is not None and citation.text is not None:
                actual = document.content[citation.start : citation.end]
                if citation.text != actual:
                    self._add(
                        "CITATION_TEXT_MISMATCH",
                        FindingCategory.OBSERVABLE_FAILURE,
                        Severity.ERROR,
                        f"Citation {citation.id!r} text does not match the exact source span.",
                        "citation",
                        citation.id,
                        evidence={"expected": actual, "observed": citation.text},
                    )

    def _check_model_knowledge(self, as_of: Optional[datetime]) -> None:
        declaration = self.trace.model_knowledge
        if declaration is None:
            self._add(
                "MISSING_MODEL_KNOWLEDGE_DECLARATION",
                FindingCategory.METADATA_GAP,
                Severity.WARNING,
                "No model knowledge-cutoff declaration is present.",
                "model",
                "undeclared",
            )
        elif declaration.knowledge_cutoff is None:
            self._add(
                "MISSING_MODEL_KNOWLEDGE_CUTOFF",
                FindingCategory.METADATA_GAP,
                Severity.WARNING,
                f"Model {declaration.model!r} has no declared knowledge cutoff.",
                "model",
                declaration.model,
            )
        elif as_of is not None and declaration.knowledge_cutoff > as_of:
            self._add(
                "MODEL_KNOWLEDGE_AFTER_CUTOFF",
                FindingCategory.MODEL_WEIGHT_UNCERTAINTY,
                Severity.WARNING,
                f"Model {declaration.model!r} declares knowledge through "
                f"{format_timestamp(declaration.knowledge_cutoff)}, after query cutoff {format_timestamp(as_of)}.",
                "model",
                declaration.model,
                declaration.knowledge_cutoff,
                {"query_as_of": format_timestamp(as_of)},
            )

        model_id = declaration.model if declaration is not None else "undeclared"
        self._add(
            "MODEL_WEIGHT_PURITY_UNVERIFIABLE",
            FindingCategory.MODEL_WEIGHT_UNCERTAINTY,
            Severity.NOTE,
            "Observable trace events can be verified, but opaque model weights cannot be proven free of "
            "post-cutoff knowledge from this trace.",
            "model",
            model_id,
        )


def verify_trace(trace: Trace) -> Verdict:
    """Convenience API for verifying a parsed trace."""

    return TemporalVerifier(trace).verify()
