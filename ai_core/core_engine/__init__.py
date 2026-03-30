"""core_engine package.

MVP AI core engine that:
- scopes requests to SSS1-SSS3 curriculum and Terms 1-3,
- retrieves grounded curriculum chunks via RAG,
- consults Neo4j for prerequisite hints,
- calls the LLM and returns cited answers,
- updates mastery minimally,
- emits logs + cost counters.
"""
