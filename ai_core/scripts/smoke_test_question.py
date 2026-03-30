from ai_core.core_engine.api_contracts.schemas import TutorRequest
from ai_core.core_engine.config.settings import get_settings
from ai_core.core_engine.curriculum.resolver import CurriculumResolver
from ai_core.core_engine.integrations.postgres_repo import PostgresRepo
from ai_core.core_engine.integrations.redis_cache import RedisCache
from ai_core.core_engine.knowledge_graph.neo4j_client import Neo4jClient
from ai_core.core_engine.knowledge_graph.prerequisites import PrereqService
from ai_core.core_engine.llm.client import LLMClient
from ai_core.core_engine.mastery.updater import MasteryUpdater
from ai_core.core_engine.observability.cost import CostTracker
from ai_core.core_engine.orchestration.tutor_engine import handle_question
from ai_core.core_engine.rag.retriever import RagRetriever


def main():
    settings = get_settings()
    pg = PostgresRepo(settings.postgres_dsn)
    cache = RedisCache(settings.redis_url) if settings.redis_url else None
    curriculum = CurriculumResolver(pg)
    retriever = RagRetriever(pg, cache=cache)
    neo = Neo4jClient(settings.neo4j_uri, settings.neo4j_user, settings.neo4j_password)
    prereqs = PrereqService(neo)
    llm = LLMClient(
        provider=settings.llm_provider, model=settings.llm_model, api_key=settings.llm_api_key
    )
    mastery = MasteryUpdater(pg)
    cost = CostTracker()

    req = TutorRequest(
        user_id="00000000-0000-0000-0000-000000000001",
        role="student",
        sss_level="SSS2",
        term=2,
        subject_id="00000000-0000-0000-0000-000000000010",
        topic_id=None,
        mode="explain",
        message="Explain photosynthesis with simple examples for SSS2.",
        session_id="demo-session-1",
    )

    resp = handle_question(
        req,
        settings=settings,
        curriculum=curriculum,
        retriever=retriever,
        prereqs=prereqs,
        llm=llm,
        mastery=mastery,
        cost_tracker=cost,
    )

    print(resp.assistant_message)
    print(resp.citations)
    print(resp.cost)
    neo.close()


if __name__ == "__main__":
    main()
