from datetime import datetime, timezone
from uuid import uuid4

import pytest

from backend.schemas.tutor_session_schema import TutorSessionEndIn, TutorSessionStartIn
from backend.services.tutor_session_service import TutorSessionNotFoundError, TutorSessionService


class FakeTutorSessionRepo:
    def __init__(self):
        self.created = None
        self.exists = True
        self.history_rows = []
        self.end_row = None

    def create_session(self, *, student_id, subject, term):
        self.created = {"student_id": student_id, "subject": subject, "term": term}
        return {
            "id": uuid4(),
            "student_id": student_id,
            "subject": subject,
            "term": term,
            "started_at": datetime.now(timezone.utc),
        }

    def session_exists_for_student(self, *, session_id, student_id):
        return self.exists

    def get_session_history(self, *, session_id):
        return self.history_rows

    def end_session(
        self,
        *,
        session_id,
        student_id,
        total_tokens,
        prompt_tokens,
        completion_tokens,
        cost_usd,
        end_reason,
    ):
        _ = (session_id, student_id, total_tokens, prompt_tokens, completion_tokens, cost_usd, end_reason)
        return self.end_row


def test_start_session_success_maps_response():
    repo = FakeTutorSessionRepo()
    service = TutorSessionService(repo)
    student_id = uuid4()

    out = service.start_session(TutorSessionStartIn(student_id=student_id, subject="math", term=1))

    assert out.student_id == student_id
    assert out.subject == "math"
    assert out.term == 1
    assert repo.created["student_id"] == student_id


def test_start_session_failure_raises_runtime_error():
    repo = FakeTutorSessionRepo()
    service = TutorSessionService(repo)
    repo.create_session = lambda **kwargs: {}  # type: ignore[assignment]

    with pytest.raises(RuntimeError, match="Failed to create tutor session"):
        service.start_session(TutorSessionStartIn(student_id=uuid4(), subject="english", term=2))


def test_get_history_raises_when_session_missing():
    repo = FakeTutorSessionRepo()
    repo.exists = False
    service = TutorSessionService(repo)

    with pytest.raises(TutorSessionNotFoundError, match="Session not found"):
        service.get_history(session_id=uuid4(), student_id=uuid4())


def test_get_history_success_maps_messages():
    repo = FakeTutorSessionRepo()
    service = TutorSessionService(repo)
    session_id = uuid4()

    repo.history_rows = [
        {
            "id": uuid4(),
            "role": "student",
            "content": "Explain concord",
            "created_at": datetime.now(timezone.utc),
        },
        {
            "id": uuid4(),
            "role": "assistant",
            "content": "Concord means agreement in grammar.",
            "created_at": datetime.now(timezone.utc),
        },
    ]

    out = service.get_history(session_id=session_id, student_id=uuid4())

    assert out.session_id == session_id
    assert len(out.messages) == 2
    assert out.messages[0].role == "student"


def test_end_session_raises_when_missing():
    repo = FakeTutorSessionRepo()
    service = TutorSessionService(repo)
    repo.end_row = {}

    with pytest.raises(TutorSessionNotFoundError, match="Session not found"):
        service.end_session(
            session_id=uuid4(),
            student_id=uuid4(),
            payload=TutorSessionEndIn(total_tokens=100),
        )


def test_end_session_success_maps_cost_summary():
    repo = FakeTutorSessionRepo()
    service = TutorSessionService(repo)
    session_id = uuid4()
    ended_at = datetime.now(timezone.utc)
    repo.end_row = {
        "id": session_id,
        "status": "ended",
        "ended_at": ended_at,
        "duration_seconds": 120,
        "total_tokens": 350,
        "prompt_tokens": 200,
        "completion_tokens": 150,
        "cost_usd": 0.01,
    }

    out = service.end_session(
        session_id=session_id,
        student_id=uuid4(),
        payload=TutorSessionEndIn(total_tokens=350, prompt_tokens=200, completion_tokens=150, cost_usd=0.01),
    )

    assert out.session_id == session_id
    assert out.status == "ended"
    assert out.duration_seconds == 120
    assert out.cost_summary["total_tokens"] == 350
