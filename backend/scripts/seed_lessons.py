"""Seed curriculum topics + mastery baseline (no lesson boilerplate).

Usage:
  python -m backend.scripts.seed_lessons

Optional env:
  SEED_STUDENT_ID=<uuid>      # primary learner id used by frontend
  SEED_RESET=1                # clear existing topics/lessons/mastery before reseeding
  SEED_INCLUDE_DEMO_LEARNERS=1  # also seed demo users/profiles/stats/mastery (default: off)
"""

from __future__ import annotations

import json
import os
import re
import uuid
import zipfile
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path
from typing import Iterable
import xml.etree.ElementTree as ET

from sqlalchemy import text
from sqlalchemy.orm import Session

from backend.core.database import SessionLocal
from backend.models.activity import StudentStats
from backend.models.lesson import Lesson, LessonBlock
from backend.models.student import StudentProfile, StudentSubject
from backend.models.subject import Subject
from backend.models.topic import Topic
from backend.models.user import User

SEED_PASSWORD_HASH = "$2b$12$5JY6jsA5q9ODaW6fNfcohOx5l6v3PK2hQd1qi97V6S9bxR5D8Qqbi"
REPO_DOCS_ROOT = Path(__file__).resolve().parents[2] / "docs"
CANONICAL_CURRICULUM_ROOT = REPO_DOCS_ROOT / "Curriculum_in_json"
LEGACY_DOCS_ROOT = REPO_DOCS_ROOT / "SSS_NOTES_2026"
SUBJECT_SLUGS = ("math", "english", "civic")
SSS_LEVELS = ("SSS1", "SSS2", "SSS3")
TERMS = (1, 2, 3)
MIN_TOPICS_PER_SCOPE = 6
TRUTHY = {"1", "true", "yes", "on"}
NOISY_TITLE_EXACT = {
    "DATE",
    "CONTENT",
    "EVALUATION",
    "EXAMINATION",
    "REVISION",
    "REFERENCES",
    "REFERENCE",
    "ASSIGNMENT",
    "END ASSIGNMENT",
    "MID TERM",
    "MID-TERM",
    "GENERAL EVALUATION",
}
NOISY_TITLE_PATTERNS = [
    r"^(FIRST|SECOND|THIRD)\s+TERM(\s+E-?\s*LEARNING\s+NOTES?)?$",
    r"^(FIRST|SECOND|THIRD)\s+TERM\s+SS[123].*$",
    r"^WEEK\s*\d+$",
    r"^TOPIC\s*\d+$",
    r"^CLASS\s*WORK$",
    r"^HOME\s*WORK$",
    r"^P\s*=\s*\d+$",
    r"^[A-Z]{1,2}\s*/\s*[A-Z]{1,2}\]?$",
    r"^\d+$",
]

BASE_SCOPE_TOPICS = {
    "math": {
        1: [
            "Sets and Operations",
            "Indices and Logarithms",
            "Quadratic Expressions",
            "Linear Inequalities",
            "Coordinate Geometry",
            "Variation and Proportion",
            "Mensuration of Solids",
        ],
        2: [
            "Trigonometric Ratios",
            "Sequences and Series",
            "Statistics and Data Representation",
            "Probability Basics",
            "Matrices and Determinants",
            "Bearings and Distances",
            "Circle Theorems",
        ],
        3: [
            "Differentiation Fundamentals",
            "Integration Fundamentals",
            "Financial Mathematics",
            "Plane Geometry Revision",
            "Transformation Geometry",
            "Logic and Mathematical Reasoning",
            "Applied Word Problems",
        ],
    },
    "english": {
        1: [
            "Sentence Structure and Clauses",
            "Parts of Speech in Context",
            "Comprehension Skills",
            "Lexis and Structure Practice",
            "Summary Writing Techniques",
            "Speech Work and Stress Patterns",
            "Formal Letter Writing",
        ],
        2: [
            "Essay Writing and Organization",
            "Reported and Direct Speech",
            "Concord and Agreement Rules",
            "Comprehension Inference Skills",
            "Oral English Practice",
            "Vocabulary Development",
            "Argumentative Writing",
        ],
        3: [
            "Advanced Grammar Editing",
            "Critical Reading and Evaluation",
            "Narrative Writing Craft",
            "Public Speaking and Delivery",
            "Summary and Precis Writing",
            "Exam Passage Strategy",
            "Language Register and Tone",
        ],
    },
    "civic": {
        1: [
            "Citizenship and National Values",
            "Rule of Law and Justice",
            "Human Rights and Responsibilities",
            "Constitutional Democracy",
            "Public Service and Integrity",
            "Community Development",
            "National Consciousness",
        ],
        2: [
            "Electoral Process and Participation",
            "Political Parties and Governance",
            "Consumer Rights and Duties",
            "Traffic Regulations and Public Safety",
            "Cultism and Drug Abuse Prevention",
            "Responsible Leadership",
            "Conflict Resolution",
        ],
        3: [
            "Democratic Institutions",
            "Corruption and National Development",
            "Peace and Conflict Management",
            "Human Trafficking Awareness",
            "Environmental Responsibility",
            "Global Citizenship",
            "Security Awareness",
        ],
    },
}


@dataclass(frozen=True)
class ScopeTopicCandidate:
    subject: str
    sss_level: str
    term: int
    title: str
    text: str
    source_file: str


@dataclass(frozen=True)
class SeedLearner:
    user_id: uuid.UUID
    email: str
    first_name: str
    last_name: str
    display_name: str
    sss_level: str
    term: int
    streak: int
    best_streak: int
    points: int
    study_seconds: int


def _is_truthy(value: str | None) -> bool:
    return (value or "").strip().lower() in TRUTHY


def _normalize_space(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def _looks_like_heading(line: str) -> bool:
    compact = (line or "").strip()
    if len(compact) < 4 or len(compact) > 100:
        return False
    if compact.isupper() and len(compact.split()) <= 15:
        return True
    return bool(re.match(r"^(week|topic|unit|chapter|lesson)\b", compact, flags=re.IGNORECASE))


def _extract_sections(text: str) -> list[tuple[str, str]]:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not lines:
        return []

    sections: list[tuple[str, str]] = []
    current_heading = ""
    buffer: list[str] = []
    for line in lines:
        if _looks_like_heading(line) and buffer:
            sections.append((current_heading, " ".join(buffer)))
            current_heading = line
            buffer = []
            continue
        if _looks_like_heading(line):
            current_heading = line
            continue
        buffer.append(line)
    if buffer:
        sections.append((current_heading, " ".join(buffer)))
    return sections


def _clean_title(raw: str, fallback: str) -> str:
    candidate = re.sub(r"^(week|topic|unit|chapter|lesson)\s*\d*\s*[:.-]?\s*", "", raw or "", flags=re.IGNORECASE)
    candidate = re.sub(r"^[\d\W_]+", "", candidate)
    candidate = _normalize_space(candidate).strip(" -:\t")
    if len(candidate) < 4:
        candidate = fallback
    return candidate[:240]


def _is_noisy_title(value: str) -> bool:
    normalized = _normalize_space(value).upper().strip(" -:\t.")
    if not normalized:
        return True
    if normalized in NOISY_TITLE_EXACT:
        return True
    for pattern in NOISY_TITLE_PATTERNS:
        if re.match(pattern, normalized, flags=re.IGNORECASE):
            return True
    return False


def _title_from_section_text(section_text: str, fallback: str) -> str:
    source = _normalize_space(section_text)
    if not source:
        return fallback
    # Prefer sentence-level signal over file-level noise.
    first_sentence = re.split(r"[.!?]", source)[0]
    cleaned = re.sub(r"[\[\]{}()|]+", " ", first_sentence)
    cleaned = _normalize_space(cleaned)
    words = cleaned.split()
    if not words:
        return fallback
    candidate = " ".join(words[:10])
    return _clean_title(candidate, fallback)


def _read_docx(path: Path) -> str:
    from docx import Document

    try:
        doc = Document(str(path))
    except Exception:
        doc = None

    if doc is not None:
        paragraphs = [paragraph.text.strip() for paragraph in doc.paragraphs if paragraph.text and paragraph.text.strip()]
        text = "\n".join(paragraphs)
        if text.strip():
            return text

    # Fallback for malformed archives that python-docx cannot fully load.
    try:
        with zipfile.ZipFile(path, "r") as archive:
            if "word/document.xml" not in archive.namelist():
                return ""
            document_xml = archive.read("word/document.xml")
    except Exception:
        return ""

    try:
        root = ET.fromstring(document_xml)
    except ET.ParseError:
        return ""

    namespace = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
    lines: list[str] = []
    for paragraph in root.findall(".//w:p", namespace):
        tokens: list[str] = []
        for node in paragraph.findall(".//w:t", namespace):
            token = str(node.text or "").strip()
            if token:
                tokens.append(token)
        if tokens:
            lines.append(" ".join(tokens))
    return "\n".join(lines)


def _infer_subject(text: str) -> str | None:
    value = text.upper()
    matches: list[str] = []
    for match in re.finditer(r"\b(MATHEMATICS|MATHS|MATH|ENGLISH|CIVIC)\b", value):
        token = match.group(1)
        if token in {"MATHEMATICS", "MATHS", "MATH"}:
            matches.append("math")
        elif token == "ENGLISH":
            matches.append("english")
        elif token == "CIVIC":
            matches.append("civic")
    if matches:
        # Prefer the closest (most specific) scope marker in the path.
        return matches[-1]
    return None


def _infer_sss_level(text: str) -> str | None:
    value = text.upper()
    matches: list[str] = []
    pattern = re.compile(r"\bSSS?\s*([123])\b|\bS([123])\b")
    for match in pattern.finditer(value):
        digit = match.group(1) or match.group(2)
        if digit:
            matches.append(str(digit))
    if matches:
        return f"SSS{matches[-1]}"
    return None


def _infer_term(text: str) -> int | None:
    value = text.upper()
    term_matches: list[int] = []
    term_patterns = [
        (re.compile(r"FIRST\s+TERM|1ST\s+TERM|TERM\s*1|TERM\s+ONE"), 1),
        (re.compile(r"SECOND\s+TERM|2ND\s+TERM|TERM\s*2|TERM\s+TWO"), 2),
        (re.compile(r"THIRD\s+TERM|3RD\s+TERM|TERM\s*3|TERM\s+THREE"), 3),
    ]
    for pattern, term_value in term_patterns:
        term_matches.extend([term_value] * len(pattern.findall(value)))
    if term_matches:
        return term_matches[-1]
    return None


def _infer_scope(root: Path, file_path: Path) -> tuple[str, str, int] | None:
    try:
        rel_path = file_path.relative_to(root)
        parts = list(rel_path.parts)
    except ValueError:
        parts = [str(file_path)]
    # Infer from nearest-to-file segments first to avoid broad folder noise (e.g. SS1-To-SS3).
    local_hint = " ".join(reversed(parts[-3:])) + f" {file_path.stem}"
    global_hint = " ".join(parts) + f" {file_path.stem}"

    subject = _infer_subject(local_hint) or _infer_subject(global_hint)
    sss_level = _infer_sss_level(local_hint) or _infer_sss_level(global_hint)
    term = _infer_term(local_hint) or _infer_term(global_hint)
    if not subject or not sss_level or not term:
        return None
    return subject, sss_level, term


def _slice_words(text: str, max_words: int) -> str:
    words = _normalize_space(text).split()
    if not words:
        return ""
    return " ".join(words[:max_words])


def _candidate_text(topic_title: str, source_text: str, subject: str, sss_level: str, term: int) -> str:
    body = _slice_words(source_text, 180)
    if body:
        return body
    return (
        f"{topic_title} is part of {subject.upper()} for {sss_level} term {term}. "
        "Study the key principles, examples, and practice exercises in this lesson."
    )


def _root_has_json_topics(root: Path) -> bool:
    return root.exists() and any(root.rglob("*.json"))


def _default_curriculum_root() -> Path:
    if _root_has_json_topics(CANONICAL_CURRICULUM_ROOT):
        return CANONICAL_CURRICULUM_ROOT
    return LEGACY_DOCS_ROOT


def _build_doc_candidates(root: Path) -> list[ScopeTopicCandidate]:
    if not root.exists():
        return []

    candidates: list[ScopeTopicCandidate] = []
    used_titles_per_scope: dict[tuple[str, str, int], set[str]] = {}

    for file_path in sorted(root.rglob("*.docx")):
        scope = _infer_scope(root, file_path)
        if scope is None:
            continue
        subject, sss_level, term = scope
        raw_text = _read_docx(file_path)
        if not raw_text.strip():
            continue
        sections = _extract_sections(raw_text)[:12]
        if not sections:
            sections = [("", raw_text)]

        scope_key = (subject, sss_level, term)
        used_titles_per_scope.setdefault(scope_key, set())
        source_name = file_path.name
        fallback_prefix = _normalize_space(file_path.stem.title()) or "Curriculum Topic"

        for idx, (heading, section_text) in enumerate(sections):
            fallback_title = f"{fallback_prefix} Part {idx + 1}"
            title = _clean_title(heading, fallback_title)
            if _is_noisy_title(title):
                title = _title_from_section_text(section_text, fallback_title)
            if _is_noisy_title(title):
                continue
            if not title:
                continue

            dedupe_title = title
            serial = 2
            while dedupe_title.lower() in used_titles_per_scope[scope_key]:
                dedupe_title = f"{title} ({serial})"
                serial += 1
            used_titles_per_scope[scope_key].add(dedupe_title.lower())

            candidates.append(
                ScopeTopicCandidate(
                    subject=subject,
                    sss_level=sss_level,
                    term=term,
                    title=dedupe_title[:240],
                    text=_candidate_text(dedupe_title, section_text, subject, sss_level, term),
                    source_file=source_name,
                )
            )

    return candidates


def _build_json_candidates(root: Path) -> list[ScopeTopicCandidate]:
    if not root.exists():
        return []

    candidates: list[ScopeTopicCandidate] = []
    used_titles_per_scope: dict[tuple[str, str, int], set[str]] = {}

    for file_path in sorted(root.rglob("*.json")):
        try:
            payload = json.loads(file_path.read_text(encoding="utf-8", errors="ignore"))
        except json.JSONDecodeError:
            continue
        if not isinstance(payload, dict):
            continue

        subject = _normalize_space(str(payload.get("subject") or "")).lower()
        sss_level = _normalize_space(str(payload.get("sss_level") or "")).upper()
        topic_title = _normalize_space(str(payload.get("topic_title") or ""))
        if not subject or subject not in SUBJECT_SLUGS:
            continue
        if sss_level not in SSS_LEVELS:
            continue
        try:
            term = int(payload.get("term"))
        except (TypeError, ValueError):
            continue
        if term not in TERMS or not topic_title:
            continue

        learning_objectives = [
            _normalize_space(str(item))
            for item in list(payload.get("learning_objectives") or [])
            if _normalize_space(str(item))
        ]
        section_parts: list[str] = []
        for section in list(payload.get("sections") or []):
            if not isinstance(section, dict):
                continue
            heading = _normalize_space(str(section.get("heading") or ""))
            content = _normalize_space(str(section.get("content") or ""))
            if not content:
                continue
            section_parts.append(f"{heading}: {content}" if heading else content)

        candidate_body = " ".join([*learning_objectives, *section_parts]).strip()
        scope_key = (subject, sss_level, term)
        used_titles_per_scope.setdefault(scope_key, set())

        dedupe_title = topic_title
        serial = 2
        while dedupe_title.lower() in used_titles_per_scope[scope_key]:
            dedupe_title = f"{topic_title} ({serial})"
            serial += 1
        used_titles_per_scope[scope_key].add(dedupe_title.lower())

        candidates.append(
            ScopeTopicCandidate(
                subject=subject,
                sss_level=sss_level,
                term=term,
                title=dedupe_title[:240],
                text=_candidate_text(dedupe_title, candidate_body, subject, sss_level, term),
                source_file=file_path.name,
            )
        )

    return candidates


def _fallback_candidates(existing: Iterable[ScopeTopicCandidate]) -> list[ScopeTopicCandidate]:
    by_scope: dict[tuple[str, str, int], list[ScopeTopicCandidate]] = {}
    used_titles: dict[tuple[str, str, int], set[str]] = {}
    for item in existing:
        key = (item.subject, item.sss_level, item.term)
        by_scope.setdefault(key, []).append(item)
        used_titles.setdefault(key, set()).add(item.title.lower())

    additions: list[ScopeTopicCandidate] = []
    for subject in SUBJECT_SLUGS:
        for sss_level in SSS_LEVELS:
            for term in TERMS:
                key = (subject, sss_level, term)
                by_scope.setdefault(key, [])
                used_titles.setdefault(key, set())
                needed = max(0, MIN_TOPICS_PER_SCOPE - len(by_scope[key]))
                if needed == 0:
                    continue

                fallback_titles = BASE_SCOPE_TOPICS[subject][term]
                for title in fallback_titles:
                    if needed == 0:
                        break
                    if title.lower() in used_titles[key]:
                        continue
                    used_titles[key].add(title.lower())
                    needed -= 1
                    additions.append(
                        ScopeTopicCandidate(
                            subject=subject,
                            sss_level=sss_level,
                            term=term,
                            title=title,
                            text="",
                            source_file="fallback",
                        )
                    )
    return additions


def _best_doc_candidate_for_title(
    *,
    title: str,
    scope_candidates: list[ScopeTopicCandidate],
    used_indexes: set[int],
) -> ScopeTopicCandidate | None:
    normalized_title = _normalize_space(title).lower()
    if not normalized_title:
        return None

    best_index: int | None = None
    best_score = -1.0
    for index, candidate in enumerate(scope_candidates):
        if index in used_indexes:
            continue
        normalized_candidate = _normalize_space(candidate.title).lower()
        if not normalized_candidate:
            continue
        score = SequenceMatcher(a=normalized_title, b=normalized_candidate).ratio()
        if normalized_title in normalized_candidate or normalized_candidate in normalized_title:
            score = max(score, 0.92)
        if score > best_score:
            best_score = score
            best_index = index

    if best_index is None or best_score < 0.45:
        return None
    used_indexes.add(best_index)
    return scope_candidates[best_index]


def _build_seed_candidates(root: Path) -> list[ScopeTopicCandidate]:
    """Build clean canonical scope topics and attach best available document text."""
    if _root_has_json_topics(root):
        json_candidates = _build_json_candidates(root)
        if not _is_truthy(os.getenv("SEED_ENABLE_FALLBACK_TOPICS")):
            return json_candidates

        supplements = _fallback_candidates(json_candidates)
        combined = [*json_candidates]
        seen = {(item.subject, item.sss_level, item.term, item.title.lower()) for item in combined}
        for item in supplements:
            key = (item.subject, item.sss_level, item.term, item.title.lower())
            if key in seen:
                continue
            seen.add(key)
            combined.append(item)
        return combined

    doc_candidates = _build_doc_candidates(root)
    by_scope: dict[tuple[str, str, int], list[ScopeTopicCandidate]] = {}
    for candidate in doc_candidates:
        key = (candidate.subject, candidate.sss_level, candidate.term)
        by_scope.setdefault(key, []).append(candidate)

    scope_raw_text: dict[tuple[str, str, int], str] = {}
    for file_path in sorted(root.rglob("*.docx")):
        scope = _infer_scope(root, file_path)
        if scope is None:
            continue
        text = _read_docx(file_path)
        normalized = _normalize_space(text)
        if not normalized:
            continue
        existing = scope_raw_text.get(scope, "")
        scope_raw_text[scope] = f"{existing}\n{normalized}".strip()

    def _extract_scope_window(topic_title: str, scope_text: str) -> str | None:
        lowered = scope_text.lower()
        if not lowered:
            return None
        stopwords = {"and", "of", "the", "to", "in", "for", "with", "by"}
        keywords = [
            token
            for token in re.split(r"[^a-z0-9]+", topic_title.lower())
            if token and token not in stopwords and len(token) > 2
        ]
        if not keywords:
            return None
        # Prioritize longer keywords for narrower matching.
        keywords.sort(key=len, reverse=True)
        match_index = -1
        for keyword in keywords:
            index = lowered.find(keyword)
            if index >= 0:
                match_index = index
                break
        if match_index < 0:
            return None

        start = max(0, match_index - 800)
        end = min(len(scope_text), match_index + 2200)
        snippet = _normalize_space(scope_text[start:end])
        return snippet if snippet else None

    output: list[ScopeTopicCandidate] = []
    for subject in SUBJECT_SLUGS:
        for sss_level in SSS_LEVELS:
            for term in TERMS:
                key = (subject, sss_level, term)
                scope_candidates = by_scope.get(key, [])
                scope_text = scope_raw_text.get(key, "")
                used_indexes: set[int] = set()
                for canonical_title in BASE_SCOPE_TOPICS[subject][term]:
                    matched = _best_doc_candidate_for_title(
                        title=canonical_title,
                        scope_candidates=scope_candidates,
                        used_indexes=used_indexes,
                    )
                    if matched is not None:
                        text = _candidate_text(
                            canonical_title,
                            matched.text,
                            subject,
                            sss_level,
                            term,
                        )
                        source_file = matched.source_file
                    else:
                        extracted = _extract_scope_window(canonical_title, scope_text)
                        if extracted:
                            text = _candidate_text(
                                canonical_title,
                                extracted,
                                subject,
                                sss_level,
                                term,
                            )
                            source_file = "scope_window"
                        else:
                            text = ""
                            source_file = "fallback"

                    output.append(
                        ScopeTopicCandidate(
                            subject=subject,
                            sss_level=sss_level,
                            term=term,
                            title=canonical_title,
                            text=text,
                            source_file=source_file,
                        )
                    )
    return output


def _upsert_subject(db: Session, slug: str, name: str) -> Subject:
    row = db.query(Subject).filter(Subject.slug == slug).first()
    if row:
        row.name = name
        return row
    row = Subject(id=uuid.uuid4(), slug=slug, name=name)
    db.add(row)
    db.flush()
    return row


def _upsert_user(db: Session, learner: SeedLearner) -> User:
    user = db.query(User).filter(User.id == learner.user_id).first()
    if not user:
        user = db.query(User).filter(User.email == learner.email).first()
    if not user:
        user = User(id=learner.user_id, email=learner.email, password_hash=SEED_PASSWORD_HASH)
        db.add(user)
        db.flush()

    user.email = learner.email
    user.password_hash = user.password_hash or SEED_PASSWORD_HASH
    user.first_name = learner.first_name
    user.last_name = learner.last_name
    user.display_name = learner.display_name
    user.role = "student"
    user.is_active = True
    return user


def _upsert_profile(db: Session, *, user_id: uuid.UUID, sss_level: str, term: int) -> StudentProfile:
    row = db.query(StudentProfile).filter(StudentProfile.student_id == user_id).first()
    if row:
        row.sss_level = sss_level
        row.active_term = term
        return row
    row = StudentProfile(id=uuid.uuid4(), student_id=user_id, sss_level=sss_level, active_term=term)
    db.add(row)
    db.flush()
    return row


def _ensure_student_subject(db: Session, *, profile_id: uuid.UUID, subject_id: uuid.UUID) -> None:
    existing = db.query(StudentSubject).filter(
        StudentSubject.student_profile_id == profile_id,
        StudentSubject.subject_id == subject_id,
    ).first()
    if existing:
        return
    db.add(StudentSubject(id=uuid.uuid4(), student_profile_id=profile_id, subject_id=subject_id))


def _upsert_stats(db: Session, learner: SeedLearner) -> None:
    row = (
        db.query(StudentStats)
        .filter(StudentStats.student_id == learner.user_id)
        .first()
    )
    if row is None:
        row = StudentStats(
            student_id=learner.user_id,
            current_streak=0,
            max_streak=0,
            total_mastery_points=0,
            total_study_time_seconds=0,
        )
        db.add(row)
    row.current_streak = learner.streak
    row.max_streak = max(learner.best_streak, learner.streak)
    row.total_mastery_points = learner.points
    row.total_study_time_seconds = learner.study_seconds


def _upsert_topic_and_lesson(
    db: Session,
    *,
    subject_id: uuid.UUID,
    candidate: ScopeTopicCandidate,
) -> tuple[Topic, bool]:
    topic = db.query(Topic).filter(
        Topic.subject_id == subject_id,
        Topic.sss_level == candidate.sss_level,
        Topic.term == candidate.term,
        Topic.title == candidate.title,
    ).first()
    created = False
    if topic is None:
        topic = Topic(
            id=uuid.uuid4(),
            subject_id=subject_id,
            sss_level=candidate.sss_level,
            term=candidate.term,
            title=candidate.title,
            description=_slice_words(candidate.text, 40) or None,
            is_approved=True,
        )
        db.add(topic)
        db.flush()
        created = True
    else:
        topic.description = _slice_words(candidate.text, 40) or None
        topic.is_approved = True
    return topic, created


def run() -> None:
    db: Session = SessionLocal()
    try:
        # Avoid statement timeout cancellations on large seed runs.
        try:
            db.execute(text("SET statement_timeout TO 0"))
        except Exception:
            pass

        subject_map = {
            "math": _upsert_subject(db, "math", "Mathematics"),
            "english": _upsert_subject(db, "english", "English Language"),
            "civic": _upsert_subject(db, "civic", "Civic Education"),
        }

        include_demo_learners = _is_truthy(os.getenv("SEED_INCLUDE_DEMO_LEARNERS"))
        seed_student_id: uuid.UUID | None = None
        learners: list[SeedLearner] = []
        if include_demo_learners:
            seed_student_id = uuid.UUID(os.getenv("SEED_STUDENT_ID", "00000000-0000-0000-0000-000000000001"))
            learners = [
                SeedLearner(
                    user_id=seed_student_id,
                    email="olasquare.student@masteryai.local",
                    first_name="Olasquare",
                    last_name="Adeniyi",
                    display_name="Olasquare",
                    sss_level="SSS1",
                    term=1,
                    streak=9,
                    best_streak=16,
                    points=1260,
                    study_seconds=41200,
                ),
                SeedLearner(
                    user_id=uuid.UUID("00000000-0000-0000-0000-000000000002"),
                    email="amaka.student@masteryai.local",
                    first_name="Amaka",
                    last_name="Okonkwo",
                    display_name="Amaka",
                    sss_level="SSS2",
                    term=2,
                    streak=7,
                    best_streak=13,
                    points=1180,
                    study_seconds=37500,
                ),
                SeedLearner(
                    user_id=uuid.UUID("00000000-0000-0000-0000-000000000003"),
                    email="tunde.student@masteryai.local",
                    first_name="Tunde",
                    last_name="Afolabi",
                    display_name="Tunde",
                    sss_level="SSS3",
                    term=1,
                    streak=11,
                    best_streak=19,
                    points=1510,
                    study_seconds=46900,
                ),
                SeedLearner(
                    user_id=uuid.UUID("00000000-0000-0000-0000-000000000004"),
                    email="zainab.student@masteryai.local",
                    first_name="Zainab",
                    last_name="Usman",
                    display_name="Zainab",
                    sss_level="SSS1",
                    term=3,
                    streak=5,
                    best_streak=10,
                    points=980,
                    study_seconds=30400,
                ),
            ]

        for learner in learners:
            user = _upsert_user(db, learner)
            profile = _upsert_profile(db, user_id=user.id, sss_level=learner.sss_level, term=learner.term)
            _upsert_stats(db, learner)
            for subject in subject_map.values():
                _ensure_student_subject(db, profile_id=profile.id, subject_id=subject.id)
        db.commit()

        if _is_truthy(os.getenv("SEED_RESET")):
            db.query(LessonBlock).delete(synchronize_session=False)
            db.query(Lesson).delete(synchronize_session=False)
            db.query(Topic).delete(synchronize_session=False)
            db.commit()

        docs_root = _default_curriculum_root()
        candidates = _build_seed_candidates(docs_root)

        created_topics = 0
        updated_topics = 0
        scope_counter: dict[tuple[str, str, int], int] = {}
        topic_ids_by_scope: dict[tuple[str, str, int], list[uuid.UUID]] = {}

        for candidate in candidates:
            subject = subject_map[candidate.subject]
            topic, created = _upsert_topic_and_lesson(
                db,
                subject_id=subject.id,
                candidate=candidate,
            )
            if created:
                created_topics += 1
            else:
                updated_topics += 1

            scope_key = (candidate.subject, candidate.sss_level, candidate.term)
            scope_counter[scope_key] = scope_counter.get(scope_key, 0) + 1
            topic_ids_by_scope.setdefault(scope_key, []).append(topic.id)

        db.commit()

        print("Seed complete.")
        print(f"Curriculum source root: {docs_root}")
        if include_demo_learners and seed_student_id is not None:
            print(f"Primary student_id: {seed_student_id}")
            print("Demo learner mastery seeded: no (mastery should come from diagnostics, quizzes, and tutor evidence).")
        else:
            print("Demo learners seeded: no (interface should create users/profiles).")
        print(f"Topics created: {created_topics}")
        print(f"Topics updated: {updated_topics}")
        print(f"Scopes populated: {len(scope_counter)}")
        for (subject, sss_level, term), count in sorted(scope_counter.items()):
            print(f"  - {subject} {sss_level} term {term}: {count} topics")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    run()
