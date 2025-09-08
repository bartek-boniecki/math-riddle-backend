from typing import List, Optional
from pydantic import BaseModel, Field, field_validator

# ==== KANONICZNE KLUCZE (wewnętrzne) – niezmienne, po angielsku ====
CANONICAL_BRANCHES = [
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

CANONICAL_LEVELS = [
    "lower elementary school (grades 1-5)",
    "higher elementary school / middle school (grades 6-8)",
    "high school (grades 9-12)",
]

CANONICAL_SCENARIOS = [
    "engineering",
    "transport",
    "sport",
    "food and beverage",
    "entertainment",
    "family",
    "holidays",
]

# ==== POLSKIE ETYKIETY (to pokazujemy na froncie i w odpowiedziach) ====
BRANCH_PL = {
    "Numbers and operations": "Arytmetyka",
    "Algebraic expressions": "Wyrażenia algebraiczne",
    "Equations and inequalities": "Równania i nierówności",
    "Systems of equations": "Układy równań",
    "Functions": "Funkcje",
    "Percentages": "Procenty",
    "Fractions": "Ułamki",
    "Powers and roots": "Potęgi i pierwiastki",
    "Formulas of special products": "Wzory skróconego mnożenia",
    "Plane geometry": "Geometria płaska",
    "Solid geometry": "Geometria przestrzenna",
    "Statistics and probability": "Statystyka i prawdopodobieństwo",
    "Combinatorics": "Kombinatoryka",
    "Quadratic equations": "Równania kwadratowe",
    "Sequences and series": "Ciągi i szeregi",
    "Trigonometry": "Trygonometria",
    "Logarithms": "Logarytmy",
}

LEVEL_PL = {
    "lower elementary school (grades 1-5)": "szkoła podstawowa (klasy 1–5)",
    "higher elementary school / middle school (grades 6-8)": "szkoła podstawowa (klasy 6–8)",
    "high school (grades 9-12)": "liceum/technikum (klasy 9–12)",
}

SCENARIO_PL = {
    "engineering": "inżynieria",
    "transport": "transport",
    "sport": "sport",
    "food and beverage": "gastronomia",
    "entertainment": "rozrywka",
    "family": "rodzina",
    "holidays": "wakacje",
}

# ==== ALIASY (akceptujemy polskie i angielskie wejścia) ====
# klucz = możliwy tekst wejściowy od użytkownika; wartość = kanoniczny klucz
BRANCH_ALIASES = {
    # Arytmetyka / Numbers
    "arytmetyka": "Numbers and operations",
    "arithmetic": "Numbers and operations",
    "arithmetics": "Numbers and operations",
    "numbers and operations": "Numbers and operations",
    "liczby i działania": "Numbers and operations",

    "wyrażenia algebraiczne": "Algebraic expressions",
    "algebraic expressions": "Algebraic expressions",

    "równania i nierówności": "Equations and inequalities",
    "equations and inequalities": "Equations and inequalities",

    "układy równań": "Systems of equations",
    "systems of equations": "Systems of equations",

    "funkcje": "Functions",
    "functions": "Functions",

    "procenty": "Percentages",
    "percentages": "Percentages",

    "ułamki": "Fractions",
    "fractions": "Fractions",

    "potęgi i pierwiastki": "Powers and roots",
    "powers and roots": "Powers and roots",

    "wzory skróconego mnożenia": "Formulas of special products",
    "formulas of special products": "Formulas of special products",

    "geometria płaska": "Plane geometry",
    "plane geometry": "Plane geometry",

    "geometria przestrzenna": "Solid geometry",
    "solid geometry": "Solid geometry",

    "statystyka i prawdopodobieństwo": "Statistics and probability",
    "statistics and probability": "Statistics and probability",

    "kombinatoryka": "Combinatorics",
    "combinatorics": "Combinatorics",

    "równania kwadratowe": "Quadratic equations",
    "quadratic equations": "Quadratic equations",

    "ciągi i szeregi": "Sequences and series",
    "sequences and series": "sequences and series",

    "trygonometria": "Trigonometry",
    "trigonometry": "Trigonometry",

    "logarytmy": "Logarithms",
    "logarithms": "Logarithms",
}

LEVEL_ALIASES = {
    "szkoła podstawowa (klasy 1–5)": "lower elementary school (grades 1-5)",
    "szkoła podstawowa (klasy 1-5)": "lower elementary school (grades 1-5)",
    "lower elementary school (grades 1-5)": "lower elementary school (grades 1-5)",

    "szkoła podstawowa (klasy 6–8)": "higher elementary school / middle school (grades 6-8)",
    "szkoła podstawowa (klasy 6-8)": "higher elementary school / middle school (grades 6-8)",
    "higher elementary school / middle school (grades 6-8)": "higher elementary school / middle school (grades 6-8)",

    "liceum/technikum (klasy 9–12)": "high school (grades 9-12)",
    "liceum/technikum (klasy 9-12)": "high school (grades 9-12)",
    "high school (grades 9-12)": "high school (grades 9-12)",
}

SCENARIO_ALIASES = {
    "inżynieria": "engineering",
    "engineering": "engineering",
    "transport": "transport",
    "sport": "sport",
    "gastronomia": "food and beverage",
    "food and beverage": "food and beverage",
    "rozrywka": "entertainment",
    "entertainment": "entertainment",
    "rodzina": "family",
    "family": "family",
    "wakacje": "holidays",
    "holidays": "holidays",
}

def normalize_branch(v: str) -> str:
    key = (v or "").strip().lower()
    if key in BRANCH_ALIASES:
        return BRANCH_ALIASES[key]
    # bezpośrednie dopasowanie kanoniczne
    if v in CANONICAL_BRANCHES:
        return v
    raise ValueError(f"branch must be one of (PL): {list(BRANCH_PL.values())}")

def normalize_level(v: str) -> str:
    key = (v or "").strip()
    # spróbuj bezwzględnie, potem lower-stripped bez diakrytyków
    if key in CANONICAL_LEVELS:
        return key
    lk = key.lower()
    if lk in LEVEL_ALIASES:
        return LEVEL_ALIASES[lk]
    if key in LEVEL_ALIASES:
        return LEVEL_ALIASES[key]
    raise ValueError(f"school_level must be one of (PL): {list(LEVEL_PL.values())}")

def normalize_scenario(v: str) -> str:
    key = (v or "").strip().lower()
    if key in SCENARIO_ALIASES:
        return SCENARIO_ALIASES[key]
    if v in CANONICAL_SCENARIOS:
        return v
    raise ValueError(f"scenario must be one of (PL): {list(SCENARIO_PL.values())}")

def polish_branch_label(canonical: str) -> str:
    return BRANCH_PL.get(canonical, canonical)

def polish_level_label(canonical: str) -> str:
    return LEVEL_PL.get(canonical, canonical)

def polish_scenario_label(canonical: str) -> str:
    return SCENARIO_PL.get(canonical, canonical)


class GenerateRequest(BaseModel):
    # Przyjmujemy wejścia po polsku LUB po angielsku; zapisujemy kanonicznie.
    branch: str = Field(..., description="Dziedzina (PL lub EN).")
    school_level: str = Field(..., description="Poziom szkoły (PL lub EN).")
    scenario: str = Field(..., description="Scenariusz (PL lub EN).")
    seed: Optional[int] = Field(None, description="Opcjonalne ziarno losowości.")

    @field_validator("branch")
    @classmethod
    def validate_branch(cls, v: str) -> str:
        return normalize_branch(v)

    @field_validator("school_level")
    @classmethod
    def validate_level(cls, v: str) -> str:
        return normalize_level(v)

    @field_validator("scenario")
    @classmethod
    def validate_scenario(cls, v: str) -> str:
        return normalize_scenario(v)


class Challenge(BaseModel):
    id: int
    branch: str  # etykieta PL
    school_level: str  # etykieta PL
    scenario: str  # etykieta PL
    challenge_type: str
    tool: str
    problem: str
    solution_outline: str
    verification: str


class GenerateResponse(BaseModel):
    count: int
    challenges: List[Challenge]
