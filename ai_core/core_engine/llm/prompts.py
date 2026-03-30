"""Prompt templates (MVP)."""

from __future__ import annotations

from typing import Any, Dict, List


def build_tutor_prompt(
    *,
    user_message: str,
    mode: str,
    sss_level: str,
    term: int,
    citations: List[Dict[str, Any]],
    remediation_prereqs: List[str],
) -> str:
    citations_block = (
        "\n".join([f"- ({c['source_id']}#{c['chunk_id']}): {c['snippet']}" for c in citations])
        or "- (no citations)"
    )
    prereq_block = ", ".join(remediation_prereqs) if remediation_prereqs else "None"
    return f"""You are an AI tutor for Nigerian Senior Secondary School (SSS).
Scope rules:
- Teach ONLY within {sss_level}, Term {term}, for the selected subject.
- If out of scope, politely say so and suggest the closest in-scope topic.

Mode: {mode}
Prerequisite hints: {prereq_block}

CURRICULUM EXCERPTS:
{citations_block}

STUDENT QUESTION:
{user_message}

Answer in simple steps with examples suitable for SSS learners.
"""
