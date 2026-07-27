"""JSONL trace parsing.

One JSON object is expected per non-empty, non-comment line.  Record types are
``trace``, ``query``, ``document``, ``artifact``, ``retrieval``,
``memory_write``, ``memory_read``, ``citation``, and ``model_knowledge``.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Iterable, Mapping, Optional, Tuple

from .models import (
    Artifact,
    CitedSpan,
    Document,
    MemoryRead,
    MemoryWrite,
    ModelKnowledgeDeclaration,
    Query,
    RetrievalEvent,
    Trace,
    TraceFormatError,
    parse_timestamp,
)


def _require_object(value: Any, context: str) -> Mapping[str, Any]:
    if not isinstance(value, dict):
        raise TraceFormatError(f"{context} must be a JSON object")
    return value


def _string(record: Mapping[str, Any], name: str, *, default: Optional[str] = None) -> str:
    value = record.get(name, default)
    if not isinstance(value, str) or not value.strip():
        raise TraceFormatError(f"{name} must be a non-empty string")
    return value


def _text(record: Mapping[str, Any], name: str, *, default: str = "") -> str:
    value = record.get(name, default)
    if not isinstance(value, str):
        raise TraceFormatError(f"{name} must be a string")
    return value


def _optional_string(record: Mapping[str, Any], name: str) -> Optional[str]:
    value = record.get(name)
    if value is None:
        return None
    if not isinstance(value, str):
        raise TraceFormatError(f"{name} must be a string or null")
    return value


def _optional_identifier(record: Mapping[str, Any], name: str) -> Optional[str]:
    value = _optional_string(record, name)
    if value is not None and not value.strip():
        raise TraceFormatError(f"{name} must be a non-empty string or null")
    return value


def _strings(record: Mapping[str, Any], name: str) -> Tuple[str, ...]:
    value = record.get(name, [])
    if not isinstance(value, list) or any(
        not isinstance(item, str) or not item.strip() for item in value
    ):
        raise TraceFormatError(f"{name} must be an array of non-empty strings")
    return tuple(value)


def _metadata(record: Mapping[str, Any]) -> Dict[str, Any]:
    value = record.get("metadata", {})
    if not isinstance(value, dict):
        raise TraceFormatError("metadata must be a JSON object")
    return dict(value)


def _optional_integer(record: Mapping[str, Any], name: str) -> Optional[int]:
    value = record.get(name)
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int):
        raise TraceFormatError(f"{name} must be an integer or null")
    return value


def load_trace(path: str) -> Trace:
    """Load a trace from a UTF-8 JSONL file."""

    with Path(path).open("r", encoding="utf-8") as stream:
        return parse_trace(stream, source=path)


def loads_trace(content: str, source: str = "<string>") -> Trace:
    """Load a trace from an in-memory JSONL string."""

    return parse_trace(content.splitlines(), source=source)


def parse_trace(lines: Iterable[str], source: str = "<stream>") -> Trace:
    """Parse JSONL records into a :class:`Trace`."""

    trace = Trace(id=Path(source).stem or "trace")
    seen_header = False
    record_count = 0
    seen_retrieval_ids = set()
    seen_memory_read_ids = set()
    seen_citation_ids = set()

    for line_number, raw_line in enumerate(lines, 1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        record_count += 1
        try:
            value = json.loads(line)
        except json.JSONDecodeError as exc:
            raise TraceFormatError(
                f"{source}:{line_number}: invalid JSON: {exc.msg} at column {exc.colno}"
            ) from exc
        record = _require_object(value, f"{source}:{line_number}:")
        record_type = record.get("type")
        if not isinstance(record_type, str):
            raise TraceFormatError(f"{source}:{line_number}: type must be a string")

        try:
            if record_type == "trace":
                if seen_header:
                    raise TraceFormatError("duplicate trace header")
                seen_header = True
                trace.id = _string(record, "id")
                expectations = record.get("expectations", {})
                if not isinstance(expectations, dict):
                    raise TraceFormatError("expectations must be a JSON object")
                trace.expectations = dict(expectations)

            elif record_type == "query":
                if trace.query is not None:
                    raise TraceFormatError("duplicate query record")
                trace.query = Query(
                    id=_string(record, "id"),
                    as_of=parse_timestamp(record.get("as_of"), "query.as_of"),
                    text=_text(record, "text"),
                    occurred_at=parse_timestamp(record.get("occurred_at"), "query.occurred_at"),
                    metadata=_metadata(record),
                )

            elif record_type == "document":
                document_id = _string(record, "id")
                if document_id in trace.documents:
                    raise TraceFormatError(f"duplicate document id {document_id!r}")
                trace.documents[document_id] = Document(
                    id=document_id,
                    valid_from=parse_timestamp(record.get("valid_from"), f"document[{document_id}].valid_from"),
                    valid_to=parse_timestamp(record.get("valid_to"), f"document[{document_id}].valid_to"),
                    created_at=parse_timestamp(record.get("created_at"), f"document[{document_id}].created_at"),
                    published_at=parse_timestamp(record.get("published_at"), f"document[{document_id}].published_at"),
                    supersedes=_strings(record, "supersedes"),
                    superseded_at=parse_timestamp(
                        record.get("superseded_at"), f"document[{document_id}].superseded_at"
                    ),
                    source_type=_string(record, "source_type", default="document"),
                    title=_text(record, "title"),
                    content=_optional_string(record, "content"),
                    metadata=_metadata(record),
                )

            elif record_type == "artifact":
                artifact_id = _string(record, "id")
                if artifact_id in trace.artifacts:
                    raise TraceFormatError(f"duplicate artifact id {artifact_id!r}")
                trace.artifacts[artifact_id] = Artifact(
                    id=artifact_id,
                    artifact_type=_string(record, "artifact_type"),
                    built_at=parse_timestamp(record.get("built_at"), f"artifact[{artifact_id}].built_at"),
                    source_document_ids=_strings(record, "source_document_ids"),
                    knowledge_cutoff=parse_timestamp(
                        record.get("knowledge_cutoff"), f"artifact[{artifact_id}].knowledge_cutoff"
                    ),
                    metadata=_metadata(record),
                )

            elif record_type == "retrieval":
                retrieval_id = _string(record, "id")
                if retrieval_id in seen_retrieval_ids:
                    raise TraceFormatError(f"duplicate retrieval id {retrieval_id!r}")
                seen_retrieval_ids.add(retrieval_id)
                trace.retrievals.append(
                    RetrievalEvent(
                        id=retrieval_id,
                        occurred_at=parse_timestamp(
                            record.get("occurred_at"), f"retrieval[{retrieval_id}].occurred_at"
                        ),
                        document_ids=_strings(record, "document_ids"),
                        artifact_ids=_strings(record, "artifact_ids"),
                        declared_as_of=parse_timestamp(
                            record.get("declared_as_of"), f"retrieval[{retrieval_id}].declared_as_of"
                        ),
                        treatment=_string(record, "treatment", default="current"),
                        metadata=_metadata(record),
                    )
                )

            elif record_type == "memory_write":
                memory_id = _string(record, "id")
                if memory_id in trace.memory_writes:
                    raise TraceFormatError(f"duplicate memory id {memory_id!r}")
                trace.memory_writes[memory_id] = MemoryWrite(
                    id=memory_id,
                    learned_at=parse_timestamp(
                        record.get("learned_at"), f"memory_write[{memory_id}].learned_at"
                    ),
                    written_at=parse_timestamp(
                        record.get("written_at"), f"memory_write[{memory_id}].written_at"
                    ),
                    source_document_ids=_strings(record, "source_document_ids"),
                    content=_text(record, "content"),
                    metadata=_metadata(record),
                )

            elif record_type == "memory_read":
                read_id = _string(record, "id")
                if read_id in seen_memory_read_ids:
                    raise TraceFormatError(f"duplicate memory read id {read_id!r}")
                seen_memory_read_ids.add(read_id)
                trace.memory_reads.append(
                    MemoryRead(
                        id=read_id,
                        memory_id=_string(record, "memory_id"),
                        read_at=parse_timestamp(record.get("read_at"), f"memory_read[{read_id}].read_at"),
                        metadata=_metadata(record),
                    )
                )

            elif record_type == "citation":
                citation_id = _string(record, "id")
                if citation_id in seen_citation_ids:
                    raise TraceFormatError(f"duplicate citation id {citation_id!r}")
                seen_citation_ids.add(citation_id)
                trace.citations.append(
                    CitedSpan(
                        id=citation_id,
                        document_id=_string(record, "document_id"),
                        start=_optional_integer(record, "start"),
                        end=_optional_integer(record, "end"),
                        text=_optional_string(record, "text"),
                        retrieval_id=_optional_identifier(record, "retrieval_id"),
                    )
                )

            elif record_type == "model_knowledge":
                if trace.model_knowledge is not None:
                    raise TraceFormatError("duplicate model_knowledge record")
                trace.model_knowledge = ModelKnowledgeDeclaration(
                    model=_string(record, "model"),
                    knowledge_cutoff=parse_timestamp(
                        record.get("knowledge_cutoff"), "model_knowledge.knowledge_cutoff"
                    ),
                    declared_at=parse_timestamp(record.get("declared_at"), "model_knowledge.declared_at"),
                    provider=_text(record, "provider"),
                    declaration_id=_string(record, "id", default="model"),
                )

            else:
                raise TraceFormatError(f"unknown record type {record_type!r}")
        except TraceFormatError as exc:
            if str(exc).startswith(f"{source}:{line_number}:"):
                raise
            raise TraceFormatError(f"{source}:{line_number}: {exc}") from exc

    if record_count == 0:
        raise TraceFormatError(f"{source}: trace contains no JSON records")
    return trace
