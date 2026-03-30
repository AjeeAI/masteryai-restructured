# Mastery AI Endpoint User Flow

Last updated: March 13, 2026  
Applies to: current `main.py` router wiring and schemas in this repository.

## Purpose

This document is the canonical frontend-to-backend flow for Mastery AI.
It shows the required request order, state dependencies, and route ownership.

## Core Rules

1. Use `Authorization: Bearer <token>` after login for protected routes.
2. `student_id` in payload/query must match authenticated user id on protected student flows.
3. Store and reuse generated IDs:
- `session_id` from tutor session start.
- `quiz_id` from quiz generate.
- `attempt_id` from quiz submit.
- `diagnostic_id` from diagnostic start.
 - `assessment_id` from tutor checkpoint start.
4. Do not call `/api/v1/internal/*` endpoints directly from frontend.

## Base Prefix

All public API routes are under:

`/api/v1`

## Recommended End-to-End Sequence

## 1) Bootstrap

1. `GET /system/health`
2. `GET /metadata/subjects`
3. `GET /metadata/levels`

## 2) Auth

1. `POST /auth/register`
2. `POST /auth/login`
3. Store `access_token`, `user_id`, `role`.

## 3) Onboarding + Profile

1. `GET /students/profile/status`
2. If `has_profile=false`:
- `POST /students/profile/setup`
3. Always load identity card:
- `GET /users/me`
4. Optional identity update:
- `PUT /users/me`
5. Optional learning preference update:
- `PUT /users/{user_id}/preferences`  
  (legacy path still available: `PUT /students/users/{user_id}/preferences`)
6. Optional profile scope update:
- `PUT /students/profile`

## 4) Dashboard + Course Bootstrap

1. `GET /learning/dashboard/bootstrap?student_id=...&subject=...`
2. `GET /learning/course/bootstrap?student_id=...&subject=...&term=...`
3. Optional:
- `GET /learning/graph/lesson-context?student_id=...&subject=...&sss_level=...&term=...&topic_id=...`
- `GET /learning/graph/why-this-topic?student_id=...&subject=...&sss_level=...&term=...&topic_id=...`
4. `GET /students/stats`
5. `GET /students/leaderboard?limit=10`

## 5) Lesson Cockpit

1. `GET /learning/topics?student_id=...&subject=...&term=...`
2. `POST /learning/lesson/prewarm`
3. `POST /learning/lessons/cockpit/bootstrap`
4. `GET /learning/topics/{topic_id}/lesson?student_id=...`
5. `POST /learning/activity/log`

## 6) Tutor Flow

1. `POST /tutor/session/bootstrap`
2. `GET /tutor/sessions/{session_id}/history?student_id=...`
3. `POST /tutor/chat`
4. Optional guided tutor routes:
- `POST /tutor/chat/stream`
- `POST /tutor/recap`
- `POST /tutor/drill`
- `POST /tutor/prereq-bridge`
- `POST /tutor/study-plan`
- `POST /tutor/hint`
- `POST /tutor/explain-mistake`
5. Tutor checkpoints:
- `POST /tutor/assessment/start`
- `POST /tutor/assessment/submit`
6. `POST /tutor/sessions/{session_id}/end?student_id=...`

## 7) Diagnostic + Learning Path

1. `POST /learning/diagnostic/start`
2. `POST /learning/diagnostic/submit`
3. `POST /learning/path/next`
4. `GET /learning/path/map/visual?student_id=...&subject=...&sss_level=...&term=...&view=topic|concept`
5. `GET /learning/mastery?student_id=...&subject=...&term=...&view=concept|topic`

## 8) Quiz Lifecycle

1. `POST /learning/quizzes/generate`
2. `POST /learning/quizzes/{quiz_id}/submit`
3. `GET /learning/quizzes/{quiz_id}/results?student_id=...&attempt_id=...`

## 9) Teacher and Admin Flows (Role-Based)

Teacher routes:

- `/teachers/classes` (GET, POST)
- `/teachers/classes/{class_id}/enroll` (POST, DELETE by student id)
- `/teachers/classes/{class_id}/dashboard`
- `/teachers/classes/{class_id}/heatmap`
- `/teachers/classes/{class_id}/alerts`
- `/teachers/classes/{class_id}/students/{student_id}/timeline`
- `/teachers/assignments`
- `/teachers/interventions`

Admin curriculum routes:

- `POST /admin/curriculum/upload`
- `POST /admin/curriculum/ingest-all`
- `GET /admin/curriculum/ingestion-status`
- `GET /admin/curriculum/pending-approvals`
- `POST /admin/curriculum/versions/{version_id}/approve`
- `POST /admin/curriculum/versions/{version_id}/rollback`

Admin governance routes:

- `GET /admin/governance/metrics`
- `GET /admin/governance/hallucinations`
- `POST /admin/governance/hallucinations/{hallucination_id}/resolve`

## State You Must Persist in Frontend

1. `access_token`
2. `user_id` (use as `student_id` for student flows)
3. `session_id` (current tutor session)
4. `assessment_id` when a tutor checkpoint is active
5. `quiz_id` and `attempt_id` (quiz pages)
6. `diagnostic_id` (diagnostic flow)
7. Current scope filters (`subject`, `sss_level`, `term`)

## Common Integration Mistakes

1. Sending wrong `student_id` for authenticated routes -> 403.
2. Calling quiz submit without generating quiz first.
3. Calling lesson/topics before profile setup.
4. Frontend calling `/internal/*` routes directly.
5. Losing `session_id` between tutor pages.
6. Losing `assessment_id` when a tutor checkpoint is pending.
7. Calling old lesson/chat pages without first hydrating dashboard/course/lesson bootstrap state.

## Example Minimal Happy Path (Student)

1. Register -> Login.
2. `GET /students/profile/status`.
3. If no profile: `POST /students/profile/setup`.
4. `GET /learning/dashboard/bootstrap`.
5. `GET /learning/course/bootstrap`.
6. `POST /learning/lesson/prewarm`.
7. `POST /learning/lessons/cockpit/bootstrap`.
8. `GET /learning/topics/{topic_id}/lesson`.
9. Start tutor bootstrap, guided chat, checkpoint, and recap/drill as needed.
10. Generate quiz, submit, get results.
11. Return to dashboard/course and resume graph-backed intervention.

## Notes on AI/LLM Behavior

Curriculum ingestion is LLM-first by default in current scripts.
When LLM extraction/inference fails validation, backend uses deterministic fallback and logs fallback mode in ingestion job logs.
Base lesson serving now prefers structured lesson content stored in Postgres when canonical JSON curriculum is available.
RAG is used as supporting evidence for tutor and quiz grounding, not as the only lesson-serving path.
