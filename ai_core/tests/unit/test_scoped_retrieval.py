from ai_core.core_engine.integrations.postgres_repo import PostgresRepo
from ai_core.core_engine.rag.retriever import RagRetriever


def test_retrieve_returns_list_for_scoped_query_contract():
    repo = PostgresRepo(dsn="postgresql://localhost:5432/mastery_ai")
    retriever = RagRetriever(repo=repo, cache=None)

    out = retriever.retrieve(
        query="Explain concord",
        subject_id="english",
        sss_level="SSS1",
        term=1,
        allowed_topic_ids=["topic-1", "topic-2"],
        approved_only=True,
        top_k=6,
    )

    assert isinstance(out, list)
    assert out == []
