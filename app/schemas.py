# app/schemas.py
from typing import List, Optional
from pydantic import BaseModel, Field, field_validator

ALLOWED_BRANCHES = [
    "Numbers and operations",
    "Algebraic expressions",
    "Equations and inequalities",
    "Systems of equations",
    "Functions",
    "Percentages",
    "Fractions",
    "Powers and roots",
    "Formulas of special products",
    "Plane geometry",
    "Solid geometry",
    "Statistics and probability",
    "Combinatorics",
    "Quadratic equations",
    "Sequences",
    "Trigonometry",
    "Logarithms",
]

ALLOWED_LEVELS = [
    "lower elementary school (grades 1-5)",
    "higher elementary school / middle school (grades 6-8)",
    "high school (grades 9-12)",
]

ALLOWED_SCENARIOS = [
    "engineering",
    "transport",
    "sport",
    "food and beverage",
    "entertainment",
    "family",
    "holidays",
]


class GenerateRequest(BaseModel):
    branch: str = Field(..., description="Wybrana dziedzina matematyki (patrz ALLOWED_BRANCHES).")
    school_level: str = Field(..., description="Poziom szkoły (patrz ALLOWED_LEVELS).")
    scenario: str = Field(..., description="Scenariusz z życia codziennego (patrz ALLOWED_SCENARIOS).")
    seed: Optional[int] = Field(None, description="Opcjonalne ziarno losowości dla powtarzalności wyniku.")

    @field_validator("branch")
    @classmethod
    def validate_branch(cls, v: str) -> str:
        if v not in ALLOWED_BRANCHES:
            raise ValueError(f"branch must be one of {ALLOWED_BRANCHES}")
        return v

    @field_validator("school_level")
    @classmethod
    def validate_level(cls, v: str) -> str:
        if v not in ALLOWED_LEVELS:
            raise ValueError(f"school_level must be one of {ALLOWED_LEVELS}")
        return v

    @field_validator("scenario")
    @classmethod
    def validate_scenario(cls, v: str) -> str:
        if v not in ALLOWED_SCENARIOS:
            raise ValueError(f"scenario must be one of {ALLOWED_SCENARIOS}")
        return v


class Challenge(BaseModel):
    id: int
    branch: str
    school_level: str
    scenario: str
    challenge_type: str
    tool: str
    problem: str
    solution_outline: str
    verification: str


class GenerateResponse(BaseModel):
    count: int
    challenges: List[Challenge]
