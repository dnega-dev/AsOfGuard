import unittest

from asof_guard.fixture_library import load_fixture
from asof_guard.models import FindingCategory, VerdictStatus
from asof_guard.parser import loads_trace
from asof_guard.verifier import verify_trace


def codes(verdict):
    return {finding.code for finding in verdict.findings}


class VerifierTests(unittest.TestCase):
    def test_clean_historical_trace_is_clean_but_weights_unverifiable(self):
        verdict = verify_trace(load_fixture("clean_historical"))
        self.assertEqual(verdict.status, VerdictStatus.CLEAN)
        self.assertFalse(verdict.observable_failures)
        self.assertFalse(verdict.metadata_gaps)
        self.assertEqual(verdict.model_weight_purity, "unverifiable")
        self.assertIn("MODEL_WEIGHT_PURITY_UNVERIFIABLE", codes(verdict))
        purity = next(f for f in verdict.findings if f.code == "MODEL_WEIGHT_PURITY_UNVERIFIABLE")
        self.assertEqual(purity.category, FindingCategory.MODEL_WEIGHT_UNCERTAINTY)

    def test_exact_contaminating_items_and_earliest_invalid_timestamp(self):
        verdict = verify_trace(load_fixture("multiple_contaminants"))
        self.assertEqual(verdict.status, VerdictStatus.CONTAMINATED)
        self.assertEqual(verdict.earliest_invalid_timestamp.isoformat(), "2017-01-01T00:00:00+00:00")
        self.assertIn(("document", "d1"), verdict.contaminating_items)
        self.assertIn(("artifact", "a1"), verdict.contaminating_items)
        self.assertIn(("memory", "m1"), verdict.contaminating_items)

    def test_later_case_gets_specialized_code(self):
        verdict = verify_trace(load_fixture("later_case_contamination"))
        self.assertIn("LATER_CASE_CONTAMINATION", codes(verdict))
        finding = next(f for f in verdict.findings if f.code == "LATER_CASE_CONTAMINATION")
        self.assertEqual(finding.item_id, "d1")

    def test_later_policy_gets_specialized_code(self):
        verdict = verify_trace(load_fixture("later_policy_contamination"))
        self.assertIn("LATER_POLICY_CONTAMINATION", codes(verdict))

    def test_historical_treatment_does_not_flag_superseded_as_current(self):
        text = "\n".join(
            [
                '{"type":"query","id":"q","as_of":"2020-01-01T00:00:00Z"}',
                '{"type":"document","id":"v1","valid_from":"2010-01-01T00:00:00Z","created_at":"2010-01-01T00:00:00Z"}',
                '{"type":"document","id":"v2","valid_from":"2019-01-01T00:00:00Z","created_at":"2019-01-01T00:00:00Z","supersedes":["v1"]}',
                '{"type":"retrieval","id":"r","occurred_at":"2020-01-01T00:00:00Z","declared_as_of":"2020-01-01T00:00:00Z","document_ids":["v1"],"treatment":"historical"}',
                '{"type":"model_knowledge","model":"m","knowledge_cutoff":"2010-01-01T00:00:00Z"}',
            ]
        )
        verdict = verify_trace(loads_trace(text))
        self.assertNotIn("SUPERSEDED_AS_CURRENT", codes(verdict))
        self.assertEqual(verdict.status, VerdictStatus.CLEAN)

    def test_unused_supersession_cycle_does_not_contaminate_answer(self):
        text = "\n".join(
            [
                '{"type":"query","id":"q","as_of":"2020-01-01T00:00:00Z"}',
                '{"type":"document","id":"d","valid_from":"2010-01-01T00:00:00Z","created_at":"2010-01-01T00:00:00Z"}',
                '{"type":"document","id":"x","valid_from":"2010-01-01T00:00:00Z","created_at":"2010-01-01T00:00:00Z","supersedes":["y"]}',
                '{"type":"document","id":"y","valid_from":"2011-01-01T00:00:00Z","created_at":"2011-01-01T00:00:00Z","supersedes":["x"]}',
                '{"type":"retrieval","id":"r","occurred_at":"2020-01-01T00:00:00Z","declared_as_of":"2020-01-01T00:00:00Z","document_ids":["d"]}',
                '{"type":"model_knowledge","model":"m","knowledge_cutoff":"2010-01-01T00:00:00Z"}',
            ]
        )
        verdict = verify_trace(loads_trace(text))
        self.assertNotIn("SUPERSESSION_CYCLE", codes(verdict))
        self.assertEqual(verdict.status, VerdictStatus.CLEAN)

    def test_validity_end_is_exclusive(self):
        text = "\n".join(
            [
                '{"type":"query","id":"q","as_of":"2020-01-01T00:00:00Z"}',
                '{"type":"document","id":"d","valid_from":"2019-01-01T00:00:00Z","valid_to":"2020-01-01T00:00:00Z","created_at":"2019-01-01T00:00:00Z"}',
                '{"type":"retrieval","id":"r","occurred_at":"2020-01-01T00:00:00Z","declared_as_of":"2020-01-01T00:00:00Z","document_ids":["d"]}',
                '{"type":"model_knowledge","model":"m","knowledge_cutoff":"2010-01-01T00:00:00Z"}',
            ]
        )
        self.assertIn("EXPIRED_DOCUMENT", codes(verify_trace(loads_trace(text))))

    def test_event_equal_to_cutoff_is_allowed(self):
        verdict = verify_trace(load_fixture("clean_historical"))
        self.assertNotIn("POST_CUTOFF_RETRIEVAL", codes(verdict))
        self.assertNotIn("MEMORY_READ_AFTER_CUTOFF", codes(verdict))

    def test_missing_metadata_is_indeterminate_not_contaminated(self):
        verdict = verify_trace(load_fixture("missing_artifact_timestamp"))
        self.assertEqual(verdict.status, VerdictStatus.INDETERMINATE)
        self.assertFalse(verdict.observable_failures)
        self.assertIn("MISSING_ARTIFACT_TIMESTAMP", codes(verdict))

    def test_observable_failure_takes_precedence_over_metadata_gap(self):
        text = "\n".join(
            [
                '{"type":"query","id":"q","as_of":"2020-01-01T00:00:00Z"}',
                '{"type":"document","id":"d","valid_from":null,"created_at":"2021-01-01T00:00:00Z"}',
                '{"type":"retrieval","id":"r","occurred_at":null,"declared_as_of":"2020-01-01T00:00:00Z","document_ids":["d"]}',
                '{"type":"model_knowledge","model":"m","knowledge_cutoff":"2010-01-01T00:00:00Z"}',
            ]
        )
        verdict = verify_trace(loads_trace(text))
        self.assertEqual(verdict.status, VerdictStatus.CONTAMINATED)
        self.assertTrue(verdict.metadata_gaps)
        self.assertIn("POST_CUTOFF_DOCUMENT", codes(verdict))

    def test_model_cutoff_after_query_is_separate_uncertainty(self):
        verdict = verify_trace(load_fixture("model_knowledge_after_cutoff"))
        finding = next(f for f in verdict.findings if f.code == "MODEL_KNOWLEDGE_AFTER_CUTOFF")
        self.assertEqual(finding.category, FindingCategory.MODEL_WEIGHT_UNCERTAINTY)
        self.assertFalse(verdict.observable_failures)
        self.assertEqual(verdict.status, VerdictStatus.INDETERMINATE)

    def test_artifact_source_detects_later_publication_even_with_older_validity(self):
        text = "\n".join(
            [
                '{"type":"query","id":"q","as_of":"2020-01-01T00:00:00Z"}',
                '{"type":"document","id":"d","valid_from":"2010-01-01T00:00:00Z","created_at":"2010-01-01T00:00:00Z","published_at":"2021-01-01T00:00:00Z"}',
                '{"type":"artifact","id":"a","artifact_type":"embedding_index","built_at":"2019-01-01T00:00:00Z","knowledge_cutoff":"2019-01-01T00:00:00Z","source_document_ids":["d"]}',
                '{"type":"retrieval","id":"r","occurred_at":"2020-01-01T00:00:00Z","declared_as_of":"2020-01-01T00:00:00Z","document_ids":[],"artifact_ids":["a"]}',
                '{"type":"model_knowledge","model":"m","knowledge_cutoff":"2010-01-01T00:00:00Z"}',
            ]
        )
        verdict = verify_trace(loads_trace(text))
        self.assertIn("ARTIFACT_SOURCE_AFTER_CUTOFF", codes(verdict))

    def test_citation_can_be_supplied_by_consumed_memory_provenance(self):
        text = "\n".join(
            [
                '{"type":"query","id":"q","as_of":"2020-01-01T00:00:00Z"}',
                '{"type":"document","id":"d","valid_from":"2010-01-01T00:00:00Z","created_at":"2010-01-01T00:00:00Z","content":"History"}',
                '{"type":"memory_write","id":"m","learned_at":"2019-01-01T00:00:00Z","written_at":"2019-01-01T00:00:00Z","source_document_ids":["d"]}',
                '{"type":"memory_read","id":"mr","memory_id":"m","read_at":"2020-01-01T00:00:00Z"}',
                '{"type":"citation","id":"c","document_id":"d","start":0,"end":4,"text":"Hist"}',
                '{"type":"model_knowledge","model":"m","knowledge_cutoff":"2010-01-01T00:00:00Z"}',
            ]
        )
        verdict = verify_trace(loads_trace(text))
        self.assertNotIn("CITATION_NOT_RETRIEVED", codes(verdict))
        self.assertEqual(verdict.status, VerdictStatus.CLEAN)

    def test_only_read_memories_are_consumed(self):
        text = "\n".join(
            [
                '{"type":"query","id":"q","as_of":"2020-01-01T00:00:00Z"}',
                '{"type":"memory_write","id":"unused","learned_at":"2022-01-01T00:00:00Z"}',
                '{"type":"model_knowledge","model":"m","knowledge_cutoff":"2010-01-01T00:00:00Z"}',
            ]
        )
        verdict = verify_trace(loads_trace(text))
        self.assertNotIn("MEMORY_LEARNED_AFTER_CUTOFF", codes(verdict))
        self.assertEqual(verdict.status, VerdictStatus.CLEAN)

    def test_missing_query_is_indeterminate(self):
        verdict = verify_trace(loads_trace('{"type":"model_knowledge","model":"m","knowledge_cutoff":null}\n'))
        self.assertEqual(verdict.status, VerdictStatus.INDETERMINATE)
        self.assertIn("MISSING_QUERY", codes(verdict))

    def test_unknown_memory_reference_is_metadata_gap(self):
        text = "\n".join(
            [
                '{"type":"query","id":"q","as_of":"2020-01-01T00:00:00Z"}',
                '{"type":"memory_read","id":"mr","memory_id":"ghost","read_at":"2020-01-01T00:00:00Z"}',
                '{"type":"model_knowledge","model":"m","knowledge_cutoff":"2010-01-01T00:00:00Z"}',
            ]
        )
        self.assertIn("MISSING_MEMORY_REFERENCE", codes(verify_trace(loads_trace(text))))

    def test_citation_text_uses_half_open_offsets(self):
        verdict = verify_trace(load_fixture("clean_historical"))
        self.assertNotIn("CITATION_TEXT_MISMATCH", codes(verdict))
        self.assertNotIn("CITATION_INVALID_RANGE", codes(verdict))


if __name__ == "__main__":
    unittest.main()
