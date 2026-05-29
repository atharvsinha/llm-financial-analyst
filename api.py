import asyncio
import logging
from typing import Optional, AsyncGenerator
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from dotenv import load_dotenv

# Load environment variables first
load_dotenv()

from src.analyst import analyze_stream

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="e-Analyst Financial Intelligence API",
    description="Stateless AI pipeline for extracting and evaluating financial earnings press releases.",
    version="1.0.0"
)

# Enable CORS for Next.js frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify ["http://localhost:3000"]
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class AnalyzeRequest(BaseModel):
    url1: str
    url2: Optional[str] = None


async def stream_worker(url: str, side: str, queue: asyncio.Queue):
    """Worker task that consumes an analyze_stream and forwards events to a shared queue."""
    try:
        async for event in analyze_stream(url, side):
            await queue.put(event)
    except Exception as e:
        logger.error(f"Worker exception for {side} side: {e}", exc_info=True)
        import json
        error_event = f"data: {json.dumps({'event': 'error', 'side': side, 'message': str(e)})}\n\n"
        await queue.put(error_event)


async def analyze_compare_stream(url1: str, url2: str) -> AsyncGenerator[str, None]:
    """
    Asynchronously orchestrates two parallel analysis pipelines using asyncio tasks and a queue.
    Achieves high-speed concurrent I/O execution.
    """
    queue = asyncio.Queue()
    
    # Launch both workers concurrently
    task1 = asyncio.create_task(stream_worker(url1, "left", queue))
    task2 = asyncio.create_task(stream_worker(url2, "right", queue))
    
    # Read from queue as long as workers are active or queue contains items
    while not (task1.done() and task2.done() and queue.empty()):
        try:
            # Wait a short duration for items to keep the loop active and non-blocking
            item = await asyncio.wait_for(queue.get(), timeout=0.05)
            yield item
            queue.task_done()
        except asyncio.TimeoutError:
            continue
            
    # Yield any remaining items in queue
    while not queue.empty():
        item = await queue.get()
        yield item
        queue.task_done()


@app.post("/api/analyze")
async def analyze(request: AnalyzeRequest):
    """
    Streams corporate earnings press release summaries and evaluation results.
    Accepts one or two URLs in the JSON body.
    """
    logger.info(f"Received analysis request: url1={request.url1}, url2={request.url2}")
    
    if not request.url1.strip():
        raise HTTPException(status_code=400, detail="Primary URL 'url1' is required.")
        
    if request.url2 and request.url2.strip():
        # Compare mode - parallelized asynchronous streams
        return StreamingResponse(
            analyze_compare_stream(request.url1, request.url2),
            media_type="text/event-stream"
        )
    else:
        # Single mode - standard single URL stream
        return StreamingResponse(
            analyze_stream(request.url1, "left"),
            media_type="text/event-stream"
        )


@app.get("/health")
async def health_check():
    """Service health validation."""
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api:app", host="0.0.0.0", port=8000, reload=True)
