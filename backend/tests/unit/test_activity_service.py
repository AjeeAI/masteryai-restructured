import uuid
from types import SimpleNamespace

from backend.schemas.activity_schema import ActivityLogCreate
from backend.services.activity_service import ActivityService


class FakeActivityRepo:
    def __init__(self):
        self.logged_payload = None
        self.stats = {}
        self.rows = []

    def log_activity(self, **kwargs):
        self.logged_payload = kwargs
        return 50 if kwargs["event_type"] == "quiz_submitted" else 10

    def get_student_stats(self, student_id):
        return self.stats.get(student_id)

    def get_leaderboard(self, limit):
        return self.rows[:limit]


def test_log_activity_returns_points_awarded():
    repo = FakeActivityRepo()
    service = ActivityService(repo)
    student_id = uuid.uuid4()

    out = service.log_activity(
        ActivityLogCreate(
            student_id=student_id,
            subject="math",
            term=1,
            event_type="quiz_submitted",
            ref_id="quiz-1",
            duration_seconds=120,
        )
    )

    assert out.status == "success"
    assert out.points_awarded == 50
    assert repo.logged_payload["student_id"] == student_id


def test_get_student_stats_returns_defaults_when_missing():
    repo = FakeActivityRepo()
    service = ActivityService(repo)

    out = service.get_student_stats(uuid.uuid4())

    assert out.streak == 0
    assert out.mastery_points == 0
    assert out.study_time_seconds == 0


def test_get_leaderboard_assigns_rank_with_ties():
    repo = FakeActivityRepo()
    service = ActivityService(repo)
    repo.rows = [
        SimpleNamespace(student_id=uuid.uuid4(), total_mastery_points=100),
        SimpleNamespace(student_id=uuid.uuid4(), total_mastery_points=100),
        SimpleNamespace(student_id=uuid.uuid4(), total_mastery_points=80),
    ]

    out = service.get_leaderboard(limit=10)

    assert [entry.rank for entry in out] == [1, 1, 3]
