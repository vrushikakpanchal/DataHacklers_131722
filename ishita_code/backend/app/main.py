from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.core.migrations import verify_schema
from app.api import (
    auth,
    organization,
    ai,
    transformations,
    sources,
    outputs,
    reviews,
    activity,
    notifications,
    rag,
    integrations,
    access,
)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    # Schema changes are explicit: production startup only verifies the schema
    # and never creates or mutates application tables implicitly.
    verify_schema()
    yield

app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    docs_url=f"{settings.API_V1_STR}/docs",
    lifespan=lifespan,
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include all API routers under the /api prefix
app.include_router(auth.router,             prefix=settings.API_V1_STR)
app.include_router(organization.router,     prefix=settings.API_V1_STR)
app.include_router(ai.router,               prefix=settings.API_V1_STR)
app.include_router(transformations.router,  prefix=settings.API_V1_STR)
app.include_router(sources.router,          prefix=settings.API_V1_STR)
app.include_router(outputs.router,          prefix=settings.API_V1_STR)
app.include_router(reviews.router,          prefix=settings.API_V1_STR)
app.include_router(activity.router,         prefix=settings.API_V1_STR)
app.include_router(notifications.router,    prefix=settings.API_V1_STR)
app.include_router(rag.router,              prefix=settings.API_V1_STR)
app.include_router(integrations.router,     prefix=settings.API_V1_STR)
app.include_router(access.router,           prefix=settings.API_V1_STR)


@app.get("/")
def root():
    return {
        "message": settings.PROJECT_NAME,
        "docs": f"{settings.API_V1_STR}/docs",
        "health": f"{settings.API_V1_STR}/health",
    }
