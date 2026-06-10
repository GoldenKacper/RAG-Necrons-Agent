from __future__ import annotations

from fastapi import FastAPI, HTTPException

from app.db import SessionLocal, engine
from app.models import Base
from app.schemas import AskRequest, AskResponse, HealthResponse, SearchRequest, SearchResponse, SearchResult
from app.services.llm import generate_answer
from app.services.prompt import build_prompt
from app.services.retrieval import search_similar_chunks

app = FastAPI(title="RAG Necrons", version="0.1.0")


@app.on_event("startup")
def on_startup() -> None:
    Base.metadata.create_all(bind=engine)


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse()


@app.post("/search", response_model=SearchResponse)
def search(request: SearchRequest) -> SearchResponse:
    session = SessionLocal()
    try:
        results = search_similar_chunks(request.query, request.top_k)
        return SearchResponse(query=request.query, results=results)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()


@app.post("/ask", response_model=AskResponse)
def ask(request: AskRequest) -> AskResponse:
    session = SessionLocal()
    try:
        results = search_similar_chunks(request.query, request.top_k)

        if not results:
            raise HTTPException(status_code=404, detail="No chunks found")

        prompt = build_prompt(request.query, results)
        answer = generate_answer(prompt)
        print(answer)

        return AskResponse(query=request.query, answer=answer, results=results)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()
