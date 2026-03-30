import types

from backend.services.lesson_service import _extract_covered_concepts


def _chunk(**kwargs):
    return types.SimpleNamespace(**kwargs)


def test_extract_covered_concepts_from_rag_chunk_metadata():
    chunks = [
        _chunk(
            metadata={
                "concept_id": "math:sss2:t2:matrices",
                "citation_concept_label": "matrices",
            }
        ),
        _chunk(
            metadata={
                "concept_id": "math:sss2:t2:determinants",
                "concept_label": "determinants",
            }
        ),
        _chunk(
            metadata={
                "concept_id": "math:sss2:t2:matrices",
                "citation_concept_label": "matrices",
            }
        ),
    ]

    concept_ids, concept_labels = _extract_covered_concepts(chunks)

    assert concept_ids == [
        "math:sss2:t2:matrices",
        "math:sss2:t2:determinants",
    ]
    assert concept_labels["math:sss2:t2:matrices"] == "matrices"
    assert concept_labels["math:sss2:t2:determinants"] == "determinants"
