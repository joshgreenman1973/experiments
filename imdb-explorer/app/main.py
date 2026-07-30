"""FastAPI server for the IMDb Explorer."""
from pathlib import Path
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from . import queries

ROOT = Path(__file__).resolve().parent
app = FastAPI(title="IMDb Explorer")
app.mount("/static", StaticFiles(directory=ROOT / "static"), name="static")


@app.get("/", response_class=HTMLResponse)
def index() -> str:
    return (ROOT / "templates" / "index.html").read_text()


@app.get("/api/search")
def api_search(q: str) -> JSONResponse:
    return JSONResponse(queries.search_names(q))


@app.get("/api/collaborators/{nconst}")
def api_collab(nconst: str, min_shared: int = 2, max_nodes: int = 50) -> JSONResponse:
    data = queries.collaborators(nconst, min_shared=min_shared, max_nodes=max_nodes)
    return JSONResponse(data)


@app.get("/api/coappearances")
def api_coapp(n: list[str] = Query(default=[])) -> JSONResponse:
    return JSONResponse(queries.coappearances(n))


@app.get("/api/family/{nconst}")
def api_family(nconst: str) -> JSONResponse:
    return JSONResponse(queries.family(nconst))


@app.get("/api/name/{nconst}")
def api_name(nconst: str) -> JSONResponse:
    n = queries.get_name(nconst)
    if not n:
        raise HTTPException(404)
    return JSONResponse(n)
