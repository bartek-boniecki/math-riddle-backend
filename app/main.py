# app/main.py
import os
from typing import List

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

from .schemas import GenerateRequest, GenerateResponse

load_dotenv()

def _cors_origins_from_env() -> List[str]:
    raw = os.getenv("CORS_ORIGINS", "*").strip()
    if raw == "*" or raw == "":
        return ["*"]
    return [x.strip() for x in raw.split(",") if x.strip()]

app = FastAPI(
    title="Olympiad Math Challenge Generator (PL)",
    description="Backend AI do generowania 5 trudnych zadań olimpijskich po polsku, zgodnie z wymaganiami.",
    version="1.1.1",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins_from_env(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
def health():
    return {"status": "ok", "model": os.getenv("LLM_MODEL", "gpt-4o-mini")}

@app.get("/meta")
def meta():
    """
    Dla frontendu: listy (PL) do pól formularza + przykład (PL).
    Backend akceptuje zarówno PL, jak i dawne EN dzięki aliasom w schemas.py.
    """
    from .schemas import BRANCH_PL, LEVEL_PL, SCENARIO_PL

    return {
        "branches": list(BRANCH_PL.values()),
        "levels": list(LEVEL_PL.values()),
        "scenarios": list(SCENARIO_PL.values()),
        "example_payload": {
            "branch": "Kombinatoryka",
            "school_level": "liceum/technikum (klasy 9–12)",
            "scenario": "sport",
            "seed": 42,
        },
        "note": "Backend akceptuje także stare angielskie nazwy – ale zalecamy używać polskich.",
    }

@app.post("/generate", response_model=GenerateResponse)
def generate(req: GenerateRequest):
    from .generator import generate_batch
    try:
        challenges = generate_batch(req)
        return GenerateResponse(count=len(challenges), challenges=challenges)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/generate", response_model=GenerateResponse)
def generate_get(
    branch: str = Query(..., description="Dziedzina (PL, patrz /meta)"),
    school_level: str = Query(..., description="Poziom szkoły (PL, patrz /meta)"),
    scenario: str = Query(..., description="Scenariusz (PL, patrz /meta)"),
    seed: int | None = Query(None, description="Opcjonalne ziarno losowości"),
):
    """
    Wersja GET — wygodna dla frontendu (np. TeleportHQ).
    Akceptuje też stare EN wartości dzięki aliasom.
    """
    from .schemas import GenerateRequest as GR
    from .generator import generate_batch
    try:
        req = GR(branch=branch, school_level=school_level, scenario=scenario, seed=seed)
        challenges = generate_batch(req)
        return GenerateResponse(count=len(challenges), challenges=challenges)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/")
def root():
    return {
        "message": "POST /generate (JSON) lub GET /generate (query) do generowania 5 zadań. Sprawdź /meta po listy i przykłady.",
        "docs": "/docs",
    }
