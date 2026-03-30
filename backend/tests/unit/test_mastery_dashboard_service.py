from uuid import uuid4

from backend.services.mastery_dashboard_service import MasteryDashboardService


class _FakeStats:
    current_streak = 6
    max_streak = 10


class FakeMasteryRepo:
    def __init__(self):
        self.badges: list[str] = []
        self.snapshots = []

    def get_concept_mastery(self, *, student_id, subject, term):
        return [{"concept_id": "c1", "score": 0.82}, {"concept_id": "c2", "score": 0.55}]

    def get_topic_mastery(self, *, student_id, subject, term):
        return [{"topic_id": "t1", "score": 0.74}]

    def get_student_stats(self, student_id):
        return _FakeStats()

    def ensure_badge(self, *, student_id, badge_code, badge_name, description=None, metadata=None):
        if badge_name not in self.badges:
            self.badges.append(badge_name)
        return badge_name

    def list_badges(self, student_id):
        return list(self.badges)

    def upsert_snapshot(self, **kwargs):
        self.snapshots.append(kwargs)
        return kwargs

    def commit(self):
        return None


def test_mastery_dashboard_concept_view_awards_badges_and_snapshot():
    repo = FakeMasteryRepo()
    service = MasteryDashboardService(repo)
    student_id = uuid4()

    out = service.get_dashboard(
        student_id=student_id,
        subject="math",
        term=1,
        view="concept",
        persist_snapshot=True,
    )

    assert out.subject == "math"
    assert out.view == "concept"
    assert out.streak.current == 6
    assert "Consistency-5" in out.badges
    assert "Topic-Milestone-1" in out.badges
    assert len(repo.snapshots) == 1


def test_mastery_dashboard_topic_view_returns_topic_payload():
    repo = FakeMasteryRepo()
    service = MasteryDashboardService(repo)

    out = service.get_dashboard(
        student_id=uuid4(),
        subject="english",
        term=2,
        view="topic",
        persist_snapshot=False,
    )

    assert out.view == "topic"
    assert out.mastery[0]["topic_id"] == "t1"
