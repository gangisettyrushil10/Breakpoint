from fastapi import FastAPI

from app.routes.health import router as health_router

app = FastAPI(
    title="BreakPoint API",
    description="Deterministic financial stress-test simulation engine.",
    version="0.1.0",
)

app.include_router(health_router)
