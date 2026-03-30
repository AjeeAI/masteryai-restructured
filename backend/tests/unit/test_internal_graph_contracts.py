import importlib
import importlib.util
from datetime import datetime, timezone
from uuid import uuid4

import pytest


if importlib.util.find_spec("backend.schemas.internal_graph_schema") is None:
    pytest.skip(
        "Section 3 Lane B pending: backend.schemas.internal_graph_schema is not created yet.",
        allow_module_level=True,
    )


internal_graph_schema_module = importlib.import_module("backend.schemas.internal_graph_schema")


def test_internal_graph_schema_contract_models_exist():
    assert hasattr(internal_graph_schema_module, "InternalGraphContextOut")
    assert hasattr(internal_graph_schema_module, "InternalGraphUpdateIn")
    assert hasattr(internal_graph_schema_module, "InternalGraphUpdateOut")


def test_internal_graph_update_contract_accepts_normalized_payload():
    InternalGraphUpdateIn = internal_graph_schema_module.InternalGraphUpdateIn

    payload = InternalGraphUpdateIn(
        student_id=uuid4(),
        quiz_id=uuid4(),
        attempt_id=uuid4(),
        subject="math",
        sss_level="SSS2",
        term=2,
        timestamp=datetime.now(timezone.utc),
        source="practice",
        concept_breakdown=[
            {"concept_id": "concept-a", "is_correct": True, "weight_change": 0.15},
            {"concept_id": "concept-b", "is_correct": False, "weight_change": -0.05},
        ],
    )

    assert payload.subject == "math"
    assert payload.term == 2
    assert len(payload.concept_breakdown) == 2
