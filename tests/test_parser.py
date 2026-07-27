import unittest
from datetime import timezone

from asof_guard.models import TraceFormatError
from asof_guard.parser import loads_trace


class ParserTests(unittest.TestCase):
    def test_parses_all_record_families_and_normalizes_offsets(self):
        trace = loads_trace(
            "\n".join(
                [
                    '# comments and blank lines are allowed',
                    '{"type":"trace","id":"all"}',
                    '{"type":"query","id":"q","as_of":"2020-01-01T01:00:00+01:00"}',
                    '{"type":"document","id":"d","valid_from":"2019-01-01T00:00:00Z","created_at":"2019-01-01T00:00:00Z","supersedes":[]}',
                    '{"type":"artifact","id":"a","artifact_type":"reranker","built_at":"2019-02-01T00:00:00Z","source_document_ids":["d"]}',
                    '{"type":"retrieval","id":"r","occurred_at":"2020-01-01T00:00:00Z","declared_as_of":"2020-01-01T00:00:00Z","document_ids":["d"],"artifact_ids":["a"]}',
                    '{"type":"memory_write","id":"m","learned_at":"2019-01-01T00:00:00Z","source_document_ids":["d"]}',
                    '{"type":"memory_read","id":"mr","memory_id":"m","read_at":"2020-01-01T00:00:00Z"}',
                    '{"type":"citation","id":"c","document_id":"d","start":0,"end":1}',
                    '{"type":"model_knowledge","model":"model","knowledge_cutoff":"2018-01-01T00:00:00Z"}',
                ]
            )
        )
        self.assertEqual(trace.id, "all")
        self.assertEqual(trace.query.as_of.tzinfo, timezone.utc)
        self.assertEqual(trace.query.as_of.hour, 0)
        self.assertIn("d", trace.documents)
        self.assertIn("a", trace.artifacts)
        self.assertEqual(len(trace.retrievals), 1)
        self.assertIn("m", trace.memory_writes)
        self.assertEqual(len(trace.memory_reads), 1)
        self.assertEqual(len(trace.citations), 1)
        self.assertEqual(trace.model_knowledge.model, "model")

    def test_missing_timestamp_is_preserved_for_verifier(self):
        trace = loads_trace('{"type":"query","id":"q","as_of":null}\n')
        self.assertIsNone(trace.query.as_of)

    def test_naive_timestamp_is_rejected(self):
        with self.assertRaisesRegex(TraceFormatError, "must include a UTC offset"):
            loads_trace('{"type":"query","id":"q","as_of":"2020-01-01T00:00:00"}\n')

    def test_bad_json_includes_line_number(self):
        with self.assertRaisesRegex(TraceFormatError, r"memory.jsonl:2: invalid JSON"):
            loads_trace('\n{bad}\n', source="memory.jsonl")

    def test_unknown_record_type_is_rejected(self):
        with self.assertRaisesRegex(TraceFormatError, "unknown record type"):
            loads_trace('{"type":"surprise","id":"x"}\n')

    def test_duplicate_document_is_rejected(self):
        payload = (
            '{"type":"document","id":"d","valid_from":null}\n'
            '{"type":"document","id":"d","valid_from":null}\n'
        )
        with self.assertRaisesRegex(TraceFormatError, "duplicate document id"):
            loads_trace(payload)

    def test_duplicate_query_is_rejected(self):
        payload = (
            '{"type":"query","id":"q1","as_of":null}\n'
            '{"type":"query","id":"q2","as_of":null}\n'
        )
        with self.assertRaisesRegex(TraceFormatError, "duplicate query"):
            loads_trace(payload)

    def test_non_string_identifier_is_rejected(self):
        with self.assertRaisesRegex(TraceFormatError, "id must be a non-empty string"):
            loads_trace('{"type":"query","id":7,"as_of":null}\n')

    def test_non_string_text_field_is_rejected(self):
        with self.assertRaisesRegex(TraceFormatError, "text must be a string"):
            loads_trace('{"type":"query","id":"q","as_of":null,"text":{}}\n')

    def test_blank_array_identifier_is_rejected(self):
        with self.assertRaisesRegex(TraceFormatError, "document_ids must be an array"):
            loads_trace('{"type":"retrieval","id":"r","document_ids":["   "]}\n')

    def test_boolean_citation_offset_is_rejected(self):
        payload = '{"type":"citation","id":"c","document_id":"d","start":true,"end":2}\n'
        with self.assertRaisesRegex(TraceFormatError, "start must be an integer"):
            loads_trace(payload)

    def test_empty_input_is_rejected(self):
        with self.assertRaisesRegex(TraceFormatError, "contains no JSON records"):
            loads_trace("\n# only comment\n")

    def test_metadata_must_be_object(self):
        with self.assertRaisesRegex(TraceFormatError, "metadata must be a JSON object"):
            loads_trace('{"type":"query","id":"q","as_of":null,"metadata":[]}\n')
        with self.assertRaisesRegex(TraceFormatError, "metadata must be a JSON object"):
            loads_trace('{"type":"retrieval","id":"r","metadata":[],"document_ids":[]}\n')


if __name__ == "__main__":
    unittest.main()
