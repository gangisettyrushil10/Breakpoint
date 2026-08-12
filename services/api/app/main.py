import logging
import os
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routes.agent import router as agent_router
from app.routes.health import router as health_router
from app.routes.simulate import router as simulate_router

# Loads services/api/.env so OPENAI_API_KEY is available under `uvicorn`.
# Real environment variables win over the file. Safe to call here: the key is
# read when a chat request first needs a client, not at import time — so the
# deterministic endpoints keep working without one.
load_dotenv()

# Without this the root logger sits at WARNING and every per-turn record —
# stop reason, tool calls, token cost — is silently dropped under `uvicorn`,
# whose own `--log-level` only configures uvicorn's loggers.
logging.basicConfig(
    level=os.environ.get("LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    client = getattr(app.state, "openai_client", None)
    if client is not None:
        await client.close()


app = FastAPI(
    title="BreakPoint API",
    description="Deterministic financial stress-test simulation engine.",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    # Add the deployed origin here before shipping. Never pair a wildcard with
    # allow_credentials — browsers reject it and it would be unsafe anyway.
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        # Next.js falls back to 3001 whenever 3000 is already taken, which is
        # routine when another project is running. Without this every dashboard
        # request fails and the browser reports only "CORS", not the cause.
        "http://localhost:3001",
        "http://127.0.0.1:3001",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router)
app.include_router(simulate_router)
app.include_router(agent_router)
