from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from harness.agent import AgentRunRequest, run_streamed
from harness.stream import to_sse
from src.settings import settings
from src.utils import LoggerSetup

logger = LoggerSetup("FastAPI")

app = FastAPI(title="agent-harness", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/run")
async def run(req: AgentRunRequest):
    async def event_generator():
        async for event in run_streamed(req):
            yield to_sse(event)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
