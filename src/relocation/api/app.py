from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from relocation.database import SessionLocal, init_db
from relocation.services.errors import NotFound, ValidationFailed
from relocation.services.research_runs import mark_interrupted_runs


def startup() -> None:
    """Migrate the database and close out runs a previous backend process left open."""
    init_db()
    with SessionLocal() as session:
        mark_interrupted_runs(session)


@asynccontextmanager
async def lifespan(app: FastAPI):
    startup()
    yield


app = FastAPI(
    title="Relocation Planner",
    description="API for retirement relocation destination research and comparison",
    version="0.1.0",
    lifespan=lifespan,
)

@app.exception_handler(NotFound)
async def _not_found(_request: Request, exc: NotFound):
    return JSONResponse(status_code=404, content={"detail": str(exc)})


@app.exception_handler(ValidationFailed)
async def _validation_failed(_request: Request, exc: ValidationFailed):
    return JSONResponse(status_code=422, content={"detail": str(exc)})


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from relocation.api.routers import (  # noqa: E402
    categories,
    countries,
    full_research,
    locations,
    ocean_temperatures,
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
app.include_router(ocean_temperatures.router, prefix="/api/v1")
app.include_router(categories.router, prefix="/api/v1")
app.include_router(countries.router, prefix="/api/v1")
app.include_router(scores.router, prefix="/api/v1")
app.include_router(weights.router, prefix="/api/v1")
app.include_router(research.router, prefix="/api/v1")
app.include_router(pros_cons.router, prefix="/api/v1")
app.include_router(visa.router, prefix="/api/v1")
app.include_router(profile.router, prefix="/api/v1")
app.include_router(rankings.router, prefix="/api/v1")
app.include_router(users.router, prefix="/api/v1")
app.include_router(full_research.router, prefix="/api/v1")
