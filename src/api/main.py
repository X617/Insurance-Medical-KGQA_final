import json
import logging
import time
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Dict, List, Optional

import uvicorn
from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from src.graph_rag.rag_engine import RAGEngine
from src.utils.logger import get_logger, log_with_trace
from src.utils.config_loader import get_project_root

logger = get_logger("api")
rag_engine: Optional[RAGEngine] = None


class Message(BaseModel):
    role: str = Field(description="user or assistant")
    content: str


class ChatRequest(BaseModel):
    query: str
    history: List[Message] = Field(default_factory=list)


class ChatResponse(BaseModel):
    answer: str
    context: str
    intent: Optional[dict] = None
    rewritten_query: Optional[str] = None


class ErrorResponse(BaseModel):
    code: str
    message: str
    trace_id: str


def build_error_response(status_code: int, code: str, message: str, trace_id: str) -> JSONResponse:
    payload = ErrorResponse(code=code, message=message, trace_id=trace_id).model_dump()
    return JSONResponse(status_code=status_code, content=payload)


@asynccontextmanager
async def lifespan(app: FastAPI):
    global rag_engine
    rag_engine = RAGEngine()
    log_with_trace(logger, logging.INFO, "RAGEngine initialized")
    yield
    if rag_engine:
        rag_engine.close()
    log_with_trace(logger, logging.INFO, "RAGEngine closed")


app = FastAPI(title="Insurance Medical KGQA API", lifespan=lifespan)


@app.middleware("http")
async def request_logging_middleware(request: Request, call_next):
    trace_id = request.headers.get("x-trace-id", str(uuid.uuid4()))
    request.state.trace_id = trace_id
    start = time.perf_counter()
    try:
        response = await call_next(request)
        latency_ms = int((time.perf_counter() - start) * 1000)
        response.headers["x-trace-id"] = trace_id
        log_with_trace(
            logger,
            logging.INFO,
            f"path={request.url.path} method={request.method} status={response.status_code} latency_ms={latency_ms}",
            trace_id,
        )
        return response
    except Exception as exc:
        latency_ms = int((time.perf_counter() - start) * 1000)
        log_with_trace(
            logger,
            logging.ERROR,
            f"path={request.url.path} method={request.method} unhandled_exception={exc} latency_ms={latency_ms}",
            trace_id,
        )
        raise


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    trace_id = getattr(request.state, "trace_id", str(uuid.uuid4()))
    message = str(exc.detail)
    log_with_trace(logger, logging.WARNING, f"HTTPException status={exc.status_code} detail={message}", trace_id)
    return build_error_response(exc.status_code, "HTTP_ERROR", message, trace_id)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    trace_id = getattr(request.state, "trace_id", str(uuid.uuid4()))
    log_with_trace(logger, logging.WARNING, f"ValidationError detail={exc.errors()}", trace_id)
    return build_error_response(422, "VALIDATION_ERROR", "Request validation failed", trace_id)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    trace_id = getattr(request.state, "trace_id", str(uuid.uuid4()))
    log_with_trace(logger, logging.ERROR, f"Unhandled error detail={exc}", trace_id)
    return build_error_response(500, "INTERNAL_ERROR", "Internal server error", trace_id)


@app.get("/health")
async def health_check():
    neo4j_connected = bool(rag_engine and getattr(rag_engine, "retriever", None))
    return {"status": "ok", "neo4j_connected": neo4j_connected}


class ImportStatusResponse(BaseModel):
    status: str
    data: Optional[Dict[str, Dict]] = None
    message: str


@app.get("/import/status", response_model=ImportStatusResponse)
async def import_status_check():
    project_root = Path(get_project_root())
    logs_dir = project_root / "import_logs"
    
    if not logs_dir.exists():
        return ImportStatusResponse(
            status="no_import",
            data=None,
            message="No import logs found. Please run data import first."
        )
    
    progress_files = {
        "diseases": "Diseases_progress.json",
        "drugs": "Drugs_progress.json",
        "nursing_homes": "NursingHomes_progress.json",
        "insurances": "Insurance_progress.json",
    }
    
    import_status = {}
    all_complete = True
    any_started = False
    
    for key, filename in progress_files.items():
        file_path = logs_dir / filename
        if file_path.exists():
            any_started = True
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    imported = data.get("imported", 0)
                    total = data.get("total", 0)
                    progress_pct = round(imported / total * 100, 1) if total > 0 else 0
                    
                    import_status[key] = {
                        "total": total,
                        "imported": imported,
                        "progress_percent": progress_pct,
                        "failed_batches": data.get("failed_batches", []),
                        "complete": imported == total and len(data.get("failed_batches", [])) == 0
                    }
                    
                    if import_status[key]["complete"] is False:
                        all_complete = False
            except Exception as e:
                import_status[key] = {"error": str(e)}
                all_complete = False
        else:
            import_status[key] = {"status": "not_started"}
    
    if not any_started:
        return ImportStatusResponse(
            status="no_import",
            data=None,
            message="No import logs found. Please run data import first."
        )
    
    if all_complete:
        overall_status = "complete"
        message = "All data import completed successfully."
    else:
        overall_status = "in_progress"
        message = "Some data imports are still in progress or incomplete."
    
    return ImportStatusResponse(
        status=overall_status,
        data=import_status,
        message=message
    )


@app.post("/chat", response_model=ChatResponse, responses={400: {"model": ErrorResponse}, 500: {"model": ErrorResponse}})
async def chat_endpoint(request: ChatRequest, raw_request: Request):
    trace_id = getattr(raw_request.state, "trace_id", str(uuid.uuid4()))
    query = request.query.strip()
    if not query:
        raise HTTPException(status_code=400, detail="query cannot be empty")

    if rag_engine is None:
        raise HTTPException(status_code=500, detail="rag_engine is not initialized")

    log_with_trace(logger, logging.INFO, f"chat query_len={len(query)} history_len={len(request.history)}", trace_id)
    history_payload = [item.model_dump() for item in request.history]
    result = rag_engine.chat(query, history_payload)

    return ChatResponse(
        answer=result["answer"],
        context=result["context"],
        intent=result.get("intent"),
        rewritten_query=result.get("rewritten_query"),
    )


if __name__ == "__main__":
    uvicorn.run("src.api.main:app", host="0.0.0.0", port=8000, reload=True)
