from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CURRICULUM_ROOT = REPO_ROOT / "docs" / "Curriculum_in_json"
MOJIBAKE_REPLACEMENTS = {
    "â€“": "–",
    "â€”": "—",
    "â€˜": "‘",
    "â€™": "’",
    "â€œ": "“",
    "â€": "”",
    "â€¦": "…",
    "Â ": " ",
    "Â": "",
}


def canonical_subject(value: object, *, path_hint: str = "") -> str | None:
    normalized = re.sub(r"[^a-z]+", " ", str(value or "").strip().lower()).strip()
    alias_map = {
        "math": "math",
        "maths": "math",
        "mathematics": "math",
        "general mathematics": "math",
        "english": "english",
        "english language": "english",
        "english studies": "english",
        "civic": "civic",
        "civic education": "civic",
    }
    if normalized in alias_map:
        return alias_map[normalized]
    if "math" in normalized:
        return "math"
    if normalized.startswith("english"):
        return "english"
    if normalized.startswith("civic"):
        return "civic"

    hint = path_hint.lower()
    if "mathematics" in hint or "math" in hint:
        return "math"
    if "english" in hint:
        return "english"
    if "civic" in hint:
        return "civic"
    return None


def canonical_sss_level(value: object, *, path_hint: str = "") -> str | None:
    normalized = re.sub(r"[^A-Z0-9]+", "", str(value or "").strip().upper())
    direct_match = re.fullmatch(r"S{1,3}([123])", normalized)
    if direct_match:
        return f"SSS{direct_match.group(1)}"
    named_match = re.fullmatch(r"SENIORSECONDARY([123])", normalized)
    if named_match:
        return f"SSS{named_match.group(1)}"

    hint = path_hint.upper()
    hint_match = re.search(r"SSS\s*([123])", hint)
    if hint_match:
        return f"SSS{hint_match.group(1)}"
    return None


def canonical_term(value: object, *, path_hint: str = "") -> int | None:
    try:
        term = int(value)
        if term in {1, 2, 3}:
            return term
    except (TypeError, ValueError):
        pass
    hint = path_hint.lower()
    hint_match = re.search(r"term\s*([123])", hint)
    if hint_match:
        return int(hint_match.group(1))
    return None


def repair_text_encoding(value: object) -> str:
    text = str(value or "").replace("\ufeff", "")
    for bad, good in MOJIBAKE_REPLACEMENTS.items():
        text = text.replace(bad, good)
    return text


def clean_inline_text(value: object) -> str:
    return " ".join(repair_text_encoding(value).split()).strip()


def clean_multiline_text(value: object) -> str:
    text = repair_text_encoding(value).replace("\r\n", "\n").replace("\r", "\n")
    lines = [line.strip() for line in text.split("\n")]
    while lines and not lines[0]:
        lines.pop(0)
    while lines and not lines[-1]:
        lines.pop()
    return "\n".join(lines).strip()


def slugify(value: object) -> str:
    text = clean_inline_text(value).lower()
    slug = re.sub(r"[^a-z0-9]+", "-", text).strip("-")
    slug = re.sub(r"-{2,}", "-", slug)
    return slug


def heading_detail(heading: str) -> tuple[str, str]:
    normalized = clean_inline_text(heading)
    if not normalized:
        return "", ""
    parts = re.split(r"\s*[–—:-]\s*", normalized, maxsplit=1)
    if len(parts) == 2:
        return parts[0].strip().lower(), parts[1].strip()
    return normalized.lower(), normalized


def derive_learning_objective(heading: str, *, topic_title: str) -> str | None:
    category, detail = heading_detail(heading)
    detail_text = detail or topic_title
    detail_text = re.sub(r"^words associated with\s+", "", detail_text, flags=re.IGNORECASE).strip()
    if not detail_text:
        detail_text = topic_title

    if "comprehension" in category or category.startswith("summary"):
        return f"Summarize the key ideas in {detail_text}."
    if "vocabulary" in category:
        return f"Use vocabulary related to {detail_text} correctly in context."
    if "structure" in category or "grammar" in category:
        return f"Apply {detail_text} correctly in sentences."
    if "speech work" in category or "stress" in category or "consonant" in category or "vowel" in category:
        return f"Identify and pronounce {detail_text} correctly."
    if "writing" in category or "letter" in category or "essay" in category or "report" in category:
        return f"Write a clear {detail_text} using the expected features and structure."
    if "revision" in category or "review" in category or "examination" in category:
        return f"Review the main rules and examples in {detail_text} and use them in practice."
    if detail_text and detail_text.lower() != topic_title.lower():
        return f"Explain {detail_text} clearly with a relevant example."
    return None


def derive_learning_objectives(
    *,
    topic_title: str,
    sections: list[dict[str, str]],
    keywords: list[str],
) -> list[str]:
    objectives: list[str] = []
    for section in sections:
        objective = derive_learning_objective(str(section.get("heading") or ""), topic_title=topic_title)
        if objective:
            objectives.append(clean_inline_text(objective))
        if len(objectives) >= 4:
            break
    if len(objectives) < 2:
        for keyword in keywords:
            cleaned_keyword = clean_inline_text(keyword)
            if not cleaned_keyword:
                continue
            objectives.append(f"Identify and explain {cleaned_keyword}.")
            if len(objectives) >= 4:
                break
    if not objectives:
        objectives = [
            f"Explain the main ideas in {topic_title}.",
            f"Apply the key skills from {topic_title} in guided practice.",
        ]
    unique_objectives: list[str] = []
    seen: set[str] = set()
    for objective in objectives:
        key = objective.casefold()
        if key in seen:
            continue
        seen.add(key)
        unique_objectives.append(objective)
    return unique_objectives[:4]


def strengthen_short_section(*, heading: str, content: str, topic_title: str) -> str:
    normalized_content = clean_multiline_text(content)
    if len(normalized_content) >= 60:
        return normalized_content
    category, detail = heading_detail(heading)
    detail_text = detail or topic_title or clean_inline_text(heading) or "the topic"
    if (
        not normalized_content
        or normalized_content.casefold() == clean_inline_text(heading).casefold()
    ):
        if "revision" in category or "review" in category or "examination" in category:
            return (
                f"This section revises the main ideas from {detail_text}. "
                "Review the core rules, examples, and likely examination tasks before moving on."
            )
        return (
            f"This section introduces {detail_text}. "
            "Review the main explanation, examples, and practice points linked to this lesson area."
        )
    return (
        f"{normalized_content} "
        f"Review the key rules, examples, and practice points connected to {detail_text}."
    ).strip()


def read_jsonlike_string(text: str, start: int) -> tuple[str, int]:
    if text[start] != '"':
        raise ValueError("expected quote-delimited string")
    chars: list[str] = []
    i = start + 1
    while i < len(text):
        ch = text[i]
        if ch == "\\" and i + 1 < len(text):
            chars.append(ch)
            chars.append(text[i + 1])
            i += 2
            continue
        if ch == '"':
            lookahead = i + 1
            while lookahead < len(text) and text[lookahead].isspace():
                lookahead += 1
            if lookahead >= len(text) or text[lookahead] in ",}]":
                return "".join(chars), i + 1
        chars.append(ch)
        i += 1
    raise ValueError("unterminated string")


def extract_array_block(text: str, key: str) -> str:
    match = re.search(rf'"{re.escape(key)}"\s*:\s*\[', text)
    if match is None:
        return ""
    start = match.end() - 1
    depth = 0
    for index in range(start, len(text)):
        char = text[index]
        if char == "[":
            depth += 1
        elif char == "]":
            depth -= 1
            if depth == 0:
                return text[start + 1 : index]
    return ""


def extract_string_list(text: str, key: str) -> list[str]:
    block = extract_array_block(text, key)
    if not block:
        return []
    return [clean_inline_text(item) for item in re.findall(r'"([^"]*)"', block) if clean_inline_text(item)]


def extract_sections(raw: str) -> list[dict[str, str]]:
    block = extract_array_block(raw, "sections")
    if not block:
        return []

    results: list[dict[str, str]] = []
    position = 0
    while True:
        heading_match = re.search(r'"heading"\s*:\s*', block[position:], re.S)
        if heading_match is None:
            break
        cursor = position + heading_match.end()
        while cursor < len(block) and block[cursor].isspace():
            cursor += 1

        if cursor < len(block) and block[cursor] == '"':
            heading, cursor = read_jsonlike_string(block, cursor)
        else:
            content_key_match = re.search(r',\s*"content"\s*:', block[cursor:], re.S)
            if content_key_match is None:
                break
            heading = block[cursor : cursor + content_key_match.start()]
            cursor = cursor + content_key_match.start()

        content_match = re.search(r'"content"\s*:\s*"', block[cursor:], re.S)
        if content_match is None:
            break
        content_start = cursor + content_match.end() - 1
        content, cursor = read_jsonlike_string(block, content_start)

        normalized_heading = clean_inline_text(heading)
        normalized_content = clean_multiline_text(
            content.replace('\\"', '"').replace("\\n", "\n").replace("\\t", "\t")
        )
        if normalized_content:
            results.append({"heading": normalized_heading, "content": normalized_content})
        position = cursor

    return results


def salvage_json_topic_payload(path: Path) -> dict[str, Any]:
    raw = path.read_text(encoding="utf-8", errors="ignore")

    def scalar(*keys: str) -> str | None:
        for key in keys:
            match = re.search(rf'"{re.escape(key)}"\s*:\s*"([^"]*)"', raw, re.S)
            if match:
                return match.group(1)
        return None

    def number(*keys: str) -> int | None:
        for key in keys:
            match = re.search(rf'"{re.escape(key)}"\s*:\s*([0-9]+)', raw)
            if match:
                return int(match.group(1))
        return None

    return {
        "subject": scalar("subject"),
        "sss_level": scalar("sss_level"),
        "term": number("term"),
        "week": number("week"),
        "topic_title": scalar("topic_title", "topic title"),
        "topic_slug": scalar("topic_slug", "topic slug"),
        "source_title": scalar("source_title", "source title"),
        "learning_objectives": extract_string_list(raw, "learning objectives")
        or extract_string_list(raw, "learning_objectives"),
        "sections": extract_sections(raw),
        "keywords": extract_string_list(raw, "keywords"),
    }


def load_payload(path: Path) -> tuple[dict[str, Any], bool]:
    raw = path.read_text(encoding="utf-8", errors="ignore")
    try:
        payload = json.loads(raw)
        if not isinstance(payload, dict):
            raise ValueError("payload is not an object")
        return payload, False
    except Exception:
        return salvage_json_topic_payload(path), True


def normalize_payload(path: Path, payload: dict[str, Any]) -> dict[str, Any]:
    path_hint = str(path)
    subject = canonical_subject(payload.get("subject"), path_hint=path_hint)
    sss_level = canonical_sss_level(payload.get("sss_level"), path_hint=path_hint)
    term = canonical_term(payload.get("term"), path_hint=path_hint)

    topic_title = clean_inline_text(payload.get("topic_title") or payload.get("topic title"))
    topic_slug = slugify(payload.get("topic_slug") or payload.get("topic slug") or topic_title)
    source_title = clean_inline_text(payload.get("source_title") or payload.get("source title"))

    raw_learning_objectives = payload.get("learning_objectives") or payload.get("learning objectives") or []
    raw_keywords = payload.get("keywords") or []
    raw_sections = payload.get("sections") or []

    learning_objectives = [clean_inline_text(item) for item in raw_learning_objectives if clean_inline_text(item)]
    keywords = [clean_inline_text(item) for item in raw_keywords if clean_inline_text(item)]

    sections: list[dict[str, str]] = []
    for item in raw_sections:
        if not isinstance(item, dict):
            continue
        heading = clean_inline_text(item.get("heading"))
        content = strengthen_short_section(
            heading=heading,
            content=str(item.get("content") or ""),
            topic_title=topic_title,
        )
        if content:
            sections.append({"heading": heading, "content": content})

    if not subject or not sss_level or term is None or not topic_title or not source_title or not sections:
        raise ValueError(f"Could not normalize required fields for {path}")

    if not learning_objectives:
        learning_objectives = derive_learning_objectives(
            topic_title=topic_title,
            sections=sections,
            keywords=keywords,
        )

    return {
        "subject": subject,
        "sss_level": sss_level,
        "term": term,
        "week": int(payload.get("week")) if str(payload.get("week") or "").isdigit() else None,
        "topic_title": topic_title,
        "topic_slug": topic_slug,
        "source_title": source_title,
        "learning_objectives": learning_objectives,
        "sections": sections,
        "keywords": keywords,
    }


def normalize_curriculum_tree(source_root: Path) -> tuple[int, int]:
    rewritten = 0
    scanned = 0
    for path in sorted(source_root.rglob("*.json")):
        scanned += 1
        payload, was_salvaged = load_payload(path)
        normalized = normalize_payload(path, payload)
        rendered = json.dumps(normalized, indent=2, ensure_ascii=False) + "\n"
        current = path.read_text(encoding="utf-8", errors="ignore")
        if was_salvaged or current != rendered:
            path.write_text(rendered, encoding="utf-8")
            rewritten += 1
    return scanned, rewritten


def main() -> None:
    parser = argparse.ArgumentParser(description="Normalize curriculum JSON files into the canonical topic format.")
    parser.add_argument(
        "--source-root",
        default=str(DEFAULT_CURRICULUM_ROOT),
        help="Root directory containing curriculum JSON files.",
    )
    args = parser.parse_args()

    source_root = Path(args.source_root).expanduser().resolve()
    if not source_root.exists() or not source_root.is_dir():
        raise SystemExit(f"source_root does not exist or is not a directory: {source_root}")

    scanned, rewritten = normalize_curriculum_tree(source_root)
    print(f"Scanned: {scanned}")
    print(f"Rewritten: {rewritten}")


if __name__ == "__main__":
    main()
