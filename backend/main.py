"""FastAPI entrypoint.

Logic:
- Wires routers under /api/v1
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Load ORM model registry once at startup so relationship() string refs resolve.
import backend.models  # noqa: F401

from backend.core.config import settings
from backend.endpoints.auth import router as auth_router
from backend.endpoints.lessons import router as lessons_router
from backend.endpoints.metadata import router as metadata_router
from backend.endpoints.student_learning_activity import learning_router, student_router
from backend.endpoints.students import router as students_router
from backend.endpoints.system import router as system_router
from backend.endpoints.topics import router as topics_router
from backend.endpoints.users import router as users_router

# Section 2 Routers
from backend.endpoints.tutor_sessions import router as tutor_sessions_router
from backend.endpoints.internal_postgres import router as internal_postgres_router

# Section 3 Routers
from backend.endpoints.diagnostic import router as diagnostic_router
from backend.endpoints.learning_path import router as learning_path_router
from backend.endpoints.internal_graph import router as internal_graph_router
from backend.endpoints.graph_learning import router as graph_learning_router
from backend.endpoints.course_learning import router as course_learning_router
from backend.endpoints.dashboard_learning import router as dashboard_learning_router

# Section 4 Routers
from backend.endpoints.quizzes import router as quizzes_router

# Section 5 Routers
from backend.endpoints.tutor import router as tutor_router
from backend.endpoints.mastery import router as mastery_router
from backend.endpoints.teachers import router as teachers_router

# Section 7 Routers
from backend.endpoints.admin_curriculum import router as admin_curriculum_router
from backend.endpoints.admin_governance import router as admin_governance_router
from backend.endpoints.internal_rag import router as internal_rag_router
from backend.services.prewarm_job_service import start_prewarm_worker, stop_prewarm_worker

API_PREFIX = "/api/v1"


@asynccontextmanager
async def lifespan(_: FastAPI):
    start_prewarm_worker()
    try:
        yield
    finally:
        stop_prewarm_worker()


app = FastAPI(title="Mastery AI Backend", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Register the routers
# This mounts the endpoints defined in your other files onto the app
app.include_router(learning_router, prefix=API_PREFIX)
app.include_router(student_router, prefix=API_PREFIX)
app.include_router(auth_router, prefix=API_PREFIX)
app.include_router(lessons_router, prefix=API_PREFIX)
app.include_router(topics_router, prefix=API_PREFIX)
app.include_router(metadata_router, prefix=API_PREFIX)
app.include_router(students_router, prefix=API_PREFIX)
app.include_router(users_router, prefix=API_PREFIX)
app.include_router(system_router, prefix=API_PREFIX)

# Section 2 Router Wiring
app.include_router(tutor_sessions_router, prefix=API_PREFIX)
app.include_router(internal_postgres_router, prefix=API_PREFIX)

# Section 3 router wiring
app.include_router(diagnostic_router, prefix=API_PREFIX)
app.include_router(learning_path_router, prefix=API_PREFIX)
app.include_router(internal_graph_router, prefix=API_PREFIX)
app.include_router(graph_learning_router, prefix=API_PREFIX)
app.include_router(course_learning_router, prefix=API_PREFIX)
app.include_router(dashboard_learning_router, prefix=API_PREFIX)

# Section 4 router wiring
app.include_router(quizzes_router, prefix=API_PREFIX)

# Section 5 router wiring
app.include_router(tutor_router, prefix=API_PREFIX)
app.include_router(mastery_router, prefix=API_PREFIX)

# Section 6 router wiring
app.include_router(teachers_router, prefix=API_PREFIX)

# Section 7 router wiring
app.include_router(admin_curriculum_router, prefix=API_PREFIX)
app.include_router(admin_governance_router, prefix=API_PREFIX)
app.include_router(internal_rag_router, prefix=API_PREFIX)

@app.get("/")
async def root():
    """Health check endpoint."""
    return {
        "status": "online",
        "message": "Welcome to the Personalized AI Tutor API. Visit /docs for interactive documentation."
    }
