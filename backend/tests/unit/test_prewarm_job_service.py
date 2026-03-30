from types import SimpleNamespace
from uuid import uuid4

from backend.services.prewarm_job_service import PrewarmJobService


def test_enqueue_lesson_related_reuses_active_job(monkeypatch):
    existing_id = uuid4()

    class _Repo:
        def __init__(self, db):
            self.db = db

        def find_active_by_dedupe_key(self, *, job_type, dedupe_key):
            return SimpleNamespace(id=existing_id)

    monkeypatch.setattr("backend.services.prewarm_job_service.PrewarmJobRepository", _Repo)

    out = PrewarmJobService(db=object()).enqueue_lesson_related(
        student_id=uuid4(),
        subject="math",
        sss_level="SSS2",
        term=2,
        topic_ids=[uuid4()],
    )

    assert out == existing_id


def test_process_once_dispatches_lesson_related(monkeypatch):
    processed_calls = {"lesson": 0, "course": 0, "dashboard": 0, "completed": 0}
    job = SimpleNamespace(
        id=uuid4(),
        job_type="lesson_related",
        payload={
            "student_id": str(uuid4()),
            "subject": "english",
            "sss_level": "SSS1",
            "term": 1,
            "topic_ids": [str(uuid4())],
        },
    )

    class _Repo:
        def __init__(self, db):
            self.db = db
            self.claimed = False

        def claim_next_job(self):
            if self.claimed:
                return None
            self.claimed = True
            return job

        def mark_completed(self, row):
            processed_calls["completed"] += 1
            return row

        def mark_failed(self, row, *, error_message):
            raise AssertionError(f"Unexpected failure: {error_message}")

    class _Session:
        bind = SimpleNamespace(dialect=SimpleNamespace(name="sqlite"))

        def close(self):
            return None

    repo = _Repo(_Session())
    monkeypatch.setattr("backend.services.prewarm_job_service.SessionLocal", lambda: _Session())
    monkeypatch.setattr("backend.services.prewarm_job_service.PrewarmJobRepository", lambda db: repo)
    monkeypatch.setattr(
        "backend.services.prewarm_job_service.PrewarmJobService._process_lesson_related_job",
        lambda payload: processed_calls.__setitem__("lesson", processed_calls["lesson"] + 1),
    )

    out = PrewarmJobService.process_once(batch_size=1)

    assert out == 1
    assert processed_calls["lesson"] == 1
    assert processed_calls["completed"] == 1


def test_process_once_rolls_back_before_mark_failed(monkeypatch):
    processed_calls = {"failed": 0, "rollback": 0}
    job = SimpleNamespace(
        id=uuid4(),
        job_type="lesson_related",
        payload={
            "student_id": str(uuid4()),
            "subject": "civic",
            "sss_level": "SSS2",
            "term": 1,
            "topic_ids": [str(uuid4())],
        },
    )

    class _Repo:
        def __init__(self, db):
            self.db = db
            self.claimed = False

        def claim_next_job(self):
            if self.claimed:
                return None
            self.claimed = True
            return job

        def mark_completed(self, row):
            raise RuntimeError("commit dropped")

        def mark_failed(self, row, *, error_message):
            assert processed_calls["rollback"] == 1
            processed_calls["failed"] += 1
            return row

    class _Session:
        bind = SimpleNamespace(dialect=SimpleNamespace(name="sqlite"))

        def rollback(self):
            processed_calls["rollback"] += 1

        def close(self):
            return None

    repo = _Repo(_Session())
    monkeypatch.setattr("backend.services.prewarm_job_service.SessionLocal", lambda: _Session())
    monkeypatch.setattr("backend.services.prewarm_job_service.PrewarmJobRepository", lambda db: repo)
    monkeypatch.setattr(
        "backend.services.prewarm_job_service.PrewarmJobService._process_lesson_related_job",
        lambda payload: None,
    )

    out = PrewarmJobService.process_once(batch_size=1)

    assert out == 0
    assert processed_calls["rollback"] == 1
    assert processed_calls["failed"] == 1
