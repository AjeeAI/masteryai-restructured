from ai_core.core_engine.knowledge_graph.prerequisites import PrereqService


class _FakeNeo4jClient:
    def __init__(self):
        self.last_query = ""
        self.last_params = {}

    def run(self, query, params):
        self.last_query = query
        self.last_params = params
        return [
            {"prereq_id": "concept-a"},
            {"prereq_id": "concept-b"},
            {"prereq_id": None},
        ]


def test_get_prerequisites_for_topic_returns_ids_and_applies_topic_filter():
    client = _FakeNeo4jClient()
    service = PrereqService(client)

    out = service.get_prerequisites_for_topic(topic_id="topic-123")

    assert out == ["concept-a", "concept-b"]
    assert "COVERS" in client.last_query
    assert client.last_params == {"topic_id": "topic-123"}
