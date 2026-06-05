import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from atlas import settings
from atlas.db import check_health
from atlas.loaders.fde_tables import list_fde_tables, preview_fde_table
from atlas.site_selection.api import router

app = FastAPI(
    title="FUTURE Site Selection API",
    version="0.1.0",
    description="Compute site selection intelligence API — evidence-tagged scoring with due diligence gap register.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)


@app.get("/")
def root():
    return {
        "service": "FUTURE Site Selection API",
        "version": "0.1.0",
        "database_schema": settings.database_schema,
        "endpoints": {
            "profiles": "/v1/site-selection/profiles",
            "query": "POST /v1/site-selection/query",
            "score_point": "POST /v1/site-selection/score-point",
            "candidate_detail": "/v1/site-selection/candidate/{id}",
            "export": "POST /v1/site-selection/export-report",
            "health": "/v1/site-selection/health",
            "database_health": "/health/db",
        },
    }


@app.get("/health/db")
def database_health():
    return check_health()


@app.get("/data/fde/tables")
def fde_tables():
    try:
        return {
            "schema": settings.database_schema,
            "tables": list_fde_tables(),
        }
    except Exception as exc:  # noqa: BLE001 - endpoint should report concise DB errors
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/data/fde/tables/{table_name}/preview")
def fde_table_preview(table_name: str, limit: int = Query(default=25, ge=1, le=100)):
    try:
        return preview_fde_table(table_name, limit=limit)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001 - endpoint should report concise DB errors
        raise HTTPException(status_code=500, detail=str(exc)) from exc
