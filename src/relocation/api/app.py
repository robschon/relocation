from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from relocation.database import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(
    title="Relocation Planner",
    description="API for retirement relocation destination research and comparison",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from relocation.api.routers import (  # noqa: E402
    categories,
    locations,
    profile,
    pros_cons,
    rankings,
    research,
    scores,
    users,
    visa,
    weights,
)

app.include_router(locations.router, prefix="/api/v1")
app.include_router(categories.router, prefix="/api/v1")
app.include_router(scores.router, prefix="/api/v1")
app.include_router(weights.router, prefix="/api/v1")
app.include_router(research.router, prefix="/api/v1")
app.include_router(pros_cons.router, prefix="/api/v1")
app.include_router(visa.router, prefix="/api/v1")
app.include_router(profile.router, prefix="/api/v1")
app.include_router(rankings.router, prefix="/api/v1")
app.include_router(users.router, prefix="/api/v1")
