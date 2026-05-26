import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
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
        "endpoints": {
            "profiles": "/v1/site-selection/profiles",
            "query": "POST /v1/site-selection/query",
            "score_point": "POST /v1/site-selection/score-point",
            "candidate_detail": "/v1/site-selection/candidate/{id}",
            "export": "POST /v1/site-selection/export-report",
            "health": "/v1/site-selection/health",
        },
    }
