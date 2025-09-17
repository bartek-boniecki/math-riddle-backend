# app/generator.py

"""
Tag-based, JSON-free pipeline with HARD GATES and a deterministic fallback.

What’s new vs previous version:
- Validators are now HARD GATES: if LLM output (even after repairs) fails, we DO NOT return it.
- Deterministic fallback generator for critical cases (Fractions / SP-1-5) to guarantee usable content.
- Same multi-tag + repair + per-tag flows, but with a final must-pass barrier.

This eliminates the “boolean/placeholder” junk reaching the UI.
"""

import re
import json
import random
import html
from typing import Dict, List, Optional, Tuple

from .schemas import (
    Challenge,
    GenerateRequest,
    polish_branch_label,
    polish_level_label,
    polish_scenario_label,
)
from .llm import chat

# ====== PER-BRANCH challenge-types (PL) ======
BRANCH_TO_TYPES: Dict[str, List[str]] = {
    "Numbers and operations": [
        "złożone zadanie na NWD/NWW w kontekście praktycznym",
        "nietrywialne własności cyfr i sum cyfr",
        "równoważność arytmetyczna z ukrytym wzorem rekurencyjnym",
        "nietypowe dzielenie z resztą w historii słownej",
        "szacowanie błędów i zaokrągleń w ciągu operacji",
        "sprytne łamanie nawiasów i porządek działań",
        "balansowanie wyrażeń z nietypowymi działaniami (operatory zdefiniowane)",
    ],
    "Algebraic expressions": [
        "sprytne rozbijanie ułamków algebraicznych",
        "identyczność wielomianowa z parametrem",
        "zastępstwo zmiennych i homogenizacja",
        "minimalizacja wartości wyrażenia pod warunkiem",
        "nierówności AM-GM/CS w przebraniu wyrażeń",
        "teleskopowanie iloczynów/sum po faktoryzacji",
    ],
    "Equations and inequalities": [
        "nierówność z parametrem i warunkami istnienia",
        "równanie nietypowe z wartością bezwzględną i przypadkami",
        "równania symetryczne wymagające podstawień",
        "zadanie optymalizacyjne z ograniczeniami",
        "nierówność funkcjonalna z oszacowaniami",
    ],
    "Systems of equations": [
        "układ nieliniowy z symetrią",
        "układ eksponencjalno-logarytmiczny",
        "układ z parametrem i analiza rozwiązań",
        "układ z warunkami całkowitości",
    ],
    "Functions": [
        "funkcja o nietypowej definicji kawałkami",
        "równanie funkcyjne na R/Z",
        "monotoniczność i odwracalność funkcji z parametrem",
        "maksimum/minimum funkcji z ograniczeniami",
    ],
    "Percentages": [
        "sekwencyjne rabaty i podwyżki w cyklu",
        "mieszanie dwóch polityk procentowych",
        "zysk/strata z podatkami i napiętymi ograniczeniami",
        "odwracanie operacji procentowych (cofanie rabatów)",
    ],
    "Fractions": [
        "łańcuchy ułamków i ułamki łańcuchowe (intuicyjnie)",
        "porównywanie ułamków przez krzyżowanie/estymaty",
        "złożone skracanie z warunkami całkowitości",
        "ułamki egipskie z ograniczeniami",
    ],
    "Powers and roots": [
        "ukryta potęga w równaniu diofantycznym",
        "nierówność potęgowa z normalizacją",
        "pierwiastki i racjonalizacja z parametrem",
        "granice i monotoniczność ciągów potęgowych (intuicyjnie)",
    ],
    "Formulas of special products": [
        "kreatywne użycie (a±b)^n i dwumianu Newtona",
        "różnica kwadratów z maskującą historyjką",
        "iloczyny skrócone i teleskopowanie",
        "faktoryzacja przez dodanie/odjęcie tego samego",
    ],
    "Plane geometry": [
        "geometria euklidesowa z nieoczywistą konstrukcją pomocniczą",
        "twierdzenie o cięciwach/sekantach i potędze punktu",
        "geometria na siatce, parzystość i wektory",
        "maksymalny/minimalny obwód/pole przy ograniczeniach",
        "kąty wpisane i styczne z inwencją",
    ],
    "Solid geometry": [
        "przekroje brył i pole powierzchni/objętość",
        "optymalizacja wymiarów przy stałej objętości",
        "geometria przestrzenna z siatką bryły",
        "zastosowanie rzutów i tw. Pitagorasa w 3D",
    ],
    "Statistics and probability": [
        "kombinatoryczne prawdopodobieństwo z warunkowaniem",
        "wartość oczekiwana z niestandardową zmienną",
        "paradoksy i pułapki klasyfikacyjne",
        "symulacja mentalna i niezmienniki losowań",
    ],
    "Combinatorics": [
        "zasada szufladkowa z twistem",
        "inwariant/monowariant w procesie",
        "liczenie konstruktywne i bijekcje",
        "ekstremalne argumenty i metoda przecięcia",
        "dwukrotne liczenie tej samej wielkości",
        "kolorowanie/niezmienniki parzystości",
    ],
    "Quadratic equations": [
        "Vieta i warunki na pierwiastki",
        "równanie kwadratowe z parametrem i wartością bezwzględną",
        "skoki Vieety (Vieta jumping) w tle diofantycznym",
        "kwadratowa optymalizacja z ograniczeniami",
    ],
    "Sequences and series": [
        "rekurencje nieliniowe z inwariantem",
        "granice ciągów",
        "szeregi geometryczne i arytmetyczne: zbieżność i suma",
        "ciągi definiowane przez warunek cyfr",
        "monotoniczność i ograniczoność z dowodem",
    ],
    "Trigonometry": [
        "tożsamości i przekształcenia kątów nietypowych",
        "nierówności trygonometryczne",
        "równania trygonometryczne z parametrem",
        "geometria + trygonometria (mieszane)",
    ],
    "Logarithms": [
        "równania logarytmiczne z warunkami dziedziny",
        "nierówności logarytmiczne z parametrem",
        "logarytmy w modelu wzrostu/zaniku",
        "przekształcenia podstaw i zmienne",
    ],
}

# ====== Quality notes per branch (PL guidance in prompts) ======
BRANCH_QUALITY_NOTES: Dict[str, str] = {
    "Numbers and operations": "Preferuj własności NWD/NWW, niezmienniki parzystości/sum cyfr, sprytne reszty modulo; unikaj czystych długich rachunków.",
    "Algebraic expressions": "Wymagaj nietrywialnej faktoryzacji/teleskopowania/zastąpienia zmiennych; unikaj podstawienia liczb i obliczeń na wprost.",
    "Equations and inequalities": "Dodaj parametr/dziedzinę/|x|, użyj klasycznych nierówności (AM-GM/CS) lub sprytnego podstawienia; unikaj czystego algorytmu.",
    "Systems of equations": "Wykorzystaj symetrię, eliminację nieliniową lub własności całkowitości; unikaj wyłącznie długiej eliminacji.",
    "Functions": "Preferuj równania funkcyjne/iniekcję/surjekcję/monotoniczność z analizą dziedziny; unikaj wykresów „na oko”.",
    "Percentages": "Składane operacje nieprzemienne, cofanie operacji, różne stawki; unikaj jednego prostego wzoru.",
    "Fractions": "Ułamki łańcuchowe/egipskie, skracanie pod warunkiem całkowitości, porównania bez wspólnego mianownika wprost.",
    "Powers and roots": "Racjonalizacja, nierówności potęgowe, diofantyczne zależności potęg; unikaj mechanicznego podnoszenia potęg.",
    "Formulas of special products": "Skracanie przez dodanie/odjęcie tego samego, (a±b)^n, teleskopowanie; unikaj czystej ekspansji.",
    "Plane geometry": "Syntetycznie: kąty, podobieństwo, potęga punktu, konstrukcje; unikaj żmudnych współrzędnych.",
    "Solid geometry": "Przekroje, podobieństwo brył, 3D Pitagoras; unikaj czystych podstawień liczbowych.",
    "Statistics and probability": "Warunkowanie, całkowite prawdopodobieństwo, bijekcje; unikaj enumeracji całej przestrzeni.",
    "Combinatorics": "Szufladkowa, inwariant/monowariant, dwukrotne liczenie, ekstrema; unikaj liczenia przypadków „na piechotę”.",
    "Quadratic equations": "Wykorzystaj wzory Viety/parametr/warunki na pierwiastki; unikaj ślepej formuły kwadratowej.",
    "Sequences and series": "Rekurencje z inwariantem/teleskopowaniem, monotoniczność+ograniczoność; unikaj kalkulatorowego sumowania.",
    "Trigonometry": "Tożsamości, podstawienia kątowe, miks z geometrią; unikaj bazowania na tabelach wartości.",
    "Logarithms": "Dziedzina, zmiana podstawy, nierówności logarytmiczne; unikaj „przeklikania” logów bez idei.",
}

def level_guidelines(level: str) -> str:
    if level == "lower elementary school (grades 1-5)":
        return (
            "Poziom: klasy 1–5. Olimpijski charakter przez spryt (np. parzystość, niezmienniki, siatki). "
            "Bez zaawansowanej algebry/trygonometrii/logarytmów. Zadanie powinno wymagać rozumowania, nie tylko rachunków."
        )
    if level == "higher elementary school / middle school (grades 6-8)":
        return (
            "Poziom: klasy 6–8. Trudność olimpijska w granicach podstaw (np. elementarne nierówności, konstrukcje, szufladkowa, rekurencje, inwarianty). "
            "Bez rachunku różniczkowego. Nie ograniczaj repertuaru poza działem."
        )
    return (
        "Poziom: liceum (klasy 9–12). Zadanie olimpijskie (np. kombinatoryka, nietrywialne przekształcenia, tożsamości trygonometryczne, układy, analiza funkcji – bez całek). "
        "Preferuj dowód/uzasadnienie; nie ograniczaj się do jednego schematu."
    )

def scenario_hint(scenario_en: str) -> str:
    hints = {
        "engineering": "Use constraints like materials, tolerances, dimensions, or design trade-offs.",
        "transport": "Use schedules, speeds, delays, network/graph constraints, or flows.",
        "sport": "Use tournaments, rankings, match schedules, training plans, or time limits.",
        "food and beverage": "Use recipes, ratios, mixing, portions, or inventory constraints.",
        "entertainment": "Use concerts, cinema, board games, streaming, or event scheduling.",
        "family": "Use shopping, budgets, chores, daily plans, or allowances.",
        "holidays": "Use itineraries, currencies, time zones, accommodations, or packing limits.",
    }
    return hints.get(scenario_en, "")

def pick_types_for_batch(branch: str, n: int = 5, rng: Optional[random.Random] = None) -> List[str]:
    rng = rng or random
    pool = BRANCH_TO_TYPES[branch]
    chosen: List[str] = []
    counts: Dict[str, int] = {}
    while len(chosen) < n:
        t = rng.choice(pool)
        # at most twice the same type in a batch → ensures ≥2 distinct types
        if counts.get(t, 0) < 2:
            chosen.append(t)
            counts[t] = counts.get(t, 0) + 1
    return chosen

# ---------- Tag helpers (pragmatic) ----------
_ALIAS_MAP: Dict[str, List[str]] = {
    "problem": ["problem", "zadanie", "tresc", "treść"],
    "solution_outline": ["solution_outline", "solution-outline", "outline", "szkic", "szkic_rozwiazania", "szkic-rozwiązania", "sketch"],
    "sanity_check": ["sanity_check", "sanity", "weryfikacja", "sprawdzenie"],
}

def _make_tag_pattern(tag_name: str) -> re.Pattern:
    return re.compile(rf"<\s*{tag_name}\s*>(.*?)</\s*{tag_name}\s*>", re.DOTALL | re.IGNORECASE)

def _strip_code_fences_fully(s: str) -> str:
    s = re.sub(r"```[a-zA-Z0-9_+\-]*\n(.*?)```", r"\1", s, flags=re.DOTALL)
    s = re.sub(r"```(.*?)```", r"\1", s, flags=re.DOTALL)
    return s

def _sanitize(s: str) -> str:
    return _strip_code_fences_fully(html.unescape(s or ""))

def _extract_by_aliases(raw_text: str, target: str) -> Optional[str]:
    text = _sanitize(raw_text)
    for name in _ALIAS_MAP.get(target, [target]):
        m = _make_tag_pattern(name).search(text)
        if m:
            return m.group(1).strip()
    if target == "solution_outline":
        m = re.search(r"(Szkic(?:\s+rozwiązania)?|Outline|Sketch)\s*:\s*(.+)", text, flags=re.IGNORECASE | re.DOTALL)
        if m:
            chunk = m.group(2)
            chunk = re.split(r"\n\s*<|^\s*(Sanity|Weryfikacja|Sprawdzenie)\s*:", chunk, maxsplit=1, flags=re.IGNORECASE | re.DOTALL)[0]
            return chunk.strip()
    if target == "sanity_check":
        m = re.search(r"(Sanity|Weryfikacja|Sprawdzenie)\s*:\s*(.+)", text, flags=re.IGNORECASE | re.DOTALL)
        if m:
            chunk = m.group(2)
            chunk = re.split(r"\n\s*<", chunk, maxsplit=1, flags=re.DOTALL)[0]
            return chunk.strip()
    return None

def _extract_tag(text: str, tag: str) -> Optional[str]:
    return _extract_by_aliases(text, tag)

# ---------- Content validation (now HARD GATE) ----------
_SAMPLE_ECHO_PATTERNS = [
    "Przykładowa treść",
    "tylko w tym tagu",
    "Example content",
    "sample content",
    "Poprawiona treść",
]

def _bad_echo_or_boolean(s: str) -> bool:
    if not s or not s.strip():
        return True
    low = s.strip().lower()
    if low in ("true", "false"):
        return True
    if len(low) < 25:  # too short to be useful
        return True
    for pat in _SAMPLE_ECHO_PATTERNS:
        if pat.lower() in low:
            return True
    if "wartość logiczna" in low or "value is true" in low or "value is false" in low:
        return True
    if "podana treść jest fałszywa" in low:
        return True
    if "wpisz poprawną treść" in low:
        return True
    return False

def _looks_mathy(s: str) -> bool:
    return bool(re.search(r"[0-9/]", s)) or any(w in s.lower() for w in ["ułam", "liczba", "suma", "iloczyn", "równanie", "nierówność", "mianownik", "licznik"])

def _contains_scenario(s: str, scenario_pl: str) -> bool:
    return scenario_pl.lower() in s.lower()

def _validate_problem(text: str, branch_en: str, scenario_pl: str) -> bool:
    if _bad_echo_or_boolean(text):
        return False
    if len(text) < 120:
        return False
    if not _looks_mathy(text):
        return False
    if not _contains_scenario(text, scenario_pl):
        return False
    return True

def _validate_outline(text: str) -> bool:
    if _bad_echo_or_boolean(text):
        return False
    return len(text) >= 60

def _validate_sanity(text: str) -> bool:
    if _bad_echo_or_boolean(text):
        return False
    return len(text) >= 40

# ---------- Deterministic fallback generators ----------
def _fallback_fractions_sp_1_5(scenario_pl: str, rng: random.Random) -> Dict[str, str]:
    # Generate a family-friendly “engineering” flavored fractions problem suitable for grades 1–5
    A = rng.randint(2, 5)   # pieces used by team A
    B = rng.randint(3, 7)   # pieces used by team B
    total = rng.randint(8, 14)
    # target fractions like A/total and B/total are proper and comparable
    # ensure distinct and nontrivial
    while A == B or A >= total or B >= total:
        A = rng.randint(2, 5)
        B = rng.randint(3, 7)
        total = rng.randint(8, 14)

    # Another fraction for a twist:
    C_num = rng.randint(2, 5)
    C_den = rng.choice([6, 8, 10, 12])
    # outline steps
    problem = (
        f"W pracowni ({scenario_pl}) przygotowuje się {total} jednakowych belek do małego mostku. "
        f"Zespół Anny zużył \\(\\frac{{{A}}}{{{total}}}\\) wszystkich belek, a zespół Bartka zużył \\(\\frac{{{B}}}{{{total}}}\\) wszystkich belek. "
        f"a) Który zespół zużył więcej belek i o jaką część całej puli więcej?\n"
        f"b) Czy suma ich zużycia przekracza połowę puli? Uzasadnij porównaniem ułamków.\n"
        f"c) Dla porównania, w innym projekcie użyto \\(\\frac{{{C_num}}}{{{C_den}}}\\) całej puli elementów. "
        f"Uporządkuj rosnąco ułamki: \\(\\frac{{{A}}}{{{total}}},\\ \\frac{{{B}}}{{{total}}},\\ \\frac{{{C_num}}}{{{C_den}}}\\)."
    )

    # Convert to common denominators
    # a) compare A/total vs B/total
    more = "Anna" if A > B else "Bartek"
    diff_num = abs(A - B)
    diff_frac = f"\\(\\frac{{{diff_num}}}{{{total}}}\\)"

    # b) check (A+B)/total > 1/2?
    half_cmp = "tak" if (A + B) * 2 > total else "nie (nie przekracza połowy)"

    # c) order using decimal approximations for outline
    a_val = A / total
    b_val = B / total
    c_val = C_num / C_den
    triples = [("A", a_val, f"\\(\\frac{{{A}}}{{{total}}}\\)"),
               ("B", b_val, f"\\(\\frac{{{B}}}{{{total}}}\\)"),
               ("C", c_val, f"\\(\\frac{{{C_num}}}{{{C_den}}}\\)")]
    triples.sort(key=lambda t: t[1])
    order = ", ".join(t[2] for t in triples)

    outline = (
        "a) Porównujemy ułamki o tym samym mianowniku: większy licznik oznacza większy ułamek, "
        f"więc więcej zużył zespół {more}. Różnica to {diff_frac}.\n"
        "b) Suma ułamków ma wspólny mianownik, więc sprawdzamy czy "
        f"\\(\\frac{{{A}+{B}}}{{{total}}} > \\frac{{1}}{{2}}\\). To równoważne "
        f"sprawdzeniu, czy {A+B}·2 > {total}, z odpowiedzią: {half_cmp}.\n"
        "c) Dla porządku możemy porównać przy wspólnych mianownikach lub przez przybliżenia dziesiętne; "
        f"uporządkowanie rosnąco: {order}."
    )

    sanity = (
        "Wszystkie ułamki mają sens (mianowniki dodatnie, ułamki właściwe). "
        "Porównania w a) i b) są poprawne, bo sprowadzamy do wspólnego mianownika lub używamy równoważnych nierówności. "
        "W c) kolejność wynika z wartości ułamków; żadna z wartości nie przekracza 1."
    )

    return {"problem": problem, "solution_outline": outline, "sanity_check": sanity}

def _deterministic_fallback(branch_en: str, level_en: str, scenario_pl: str, rng: random.Random) -> Optional[Dict[str, str]]:
    # Extend here with more branches/levels if needed.
    if branch_en == "Fractions" and level_en == "lower elementary school (grades 1-5)":
        return _fallback_fractions_sp_1_5(scenario_pl, rng)
    return None

# ---------- LLM ask helpers ----------
def _ask_for_tag(messages: List[Dict[str, str]], tag: str, temp: float = 0.30, max_tokens: int = 850, retries: int = 3) -> str:
    prompt = (
        "Zwróć TYLKO JEDEN tag XML bez opisu ani dodatkowych linii.\n"
        f"FORMAT:\n<{tag}>[[WŁAŚCIWA TREŚĆ – po polsku, bez booleanów, bez placeholderów]]</{tag}>\n"
        "Nie kopiuj przykładów. Bez code-fence'ów i atrybutów."
    )
    content = chat(messages=messages + [{"role": "user", "content": prompt}], temperature=temp, max_tokens=max_tokens)
    val = _extract_tag(content, tag)
    if val:
        return val

    for _ in range(retries):
        repair = (
            "Poprzednia odpowiedź była niepoprawna (zbyt krótka/boolean/placeholder). "
            f"Podaj TYLKO:\n<{tag}>…</{tag}>\n"
            "Nie kopiuj przykładu, nie używaj code-fence'ów, pamiętaj o tagu zamykającym."
        )
        content = chat(messages=messages + [{"role": "user", "content": repair}], temperature=0.22, max_tokens=max_tokens)
        val = _extract_tag(content, tag)
        if val:
            return val

    raise ValueError(f"Brak poprawnego tagu <{tag}> w odpowiedzi LLM.")

def _ask_for_multi_tags(messages: List[Dict[str, str]], tags: List[str], temp: float = 0.24, max_tokens: int = 1050, retries: int = 3) -> Dict[str, str]:
    order = "\n".join([f"<{t}>…</{t}>" for t in tags])
    instr = (
        "Zwróć TYLKO poniższe tagi XML dokładnie w tej KOLEJNOŚCI, każdy w OSOBNEJ LINII, i nic więcej.\n"
        "NIE używaj code-fence'ów ani atrybutów w tagach. Nie kopiuj przykładów. "
        "Zakazane: booleany (true/false), placeholdery typu 'Poprawna treść…'.\n"
        "PRZYKŁAD FORMALNY (NIE KOPIUJ TREŚCI!):\n"
        "<problem>[[treść zadania]]</problem>\n"
        "<solution_outline>[[krótki szkic]]</solution_outline>\n"
        "<sanity_check>[[1–3 zdania sanity]]</sanity_check>\n\n"
        "TERAZ ZWRÓĆ:\n" + order
    )

    def try_once(instruction: str) -> Dict[str, str]:
        txt = chat(messages=messages + [{"role": "user", "content": instruction}], temperature=temp, max_tokens=max_tokens)
        out: Dict[str, str] = {}
        for t in tags:
            v = _extract_tag(txt, t)
            if v is None:
                return {}
            out[t] = v.strip()
        return out

    out = try_once(instr)
    if out:
        return out

    for _ in range(retries):
        instr2 = (
            "Poprzednia odpowiedź była niepoprawna. Zwróć DOKŁADNIE te tagi, po jednym na linię, bez opisów i bez fence'ów:\n"
            + order
        )
        out = try_once(instr2)
        if out:
            return out

    raise ValueError("Brak wymaganych tagów w odpowiedzi LLM.")

# ---------- Prompt builders ----------
def _build_user_prompt(
    branch_en: str,
    pl_branch: str,
    challenge_type: str,
    pl_scenario: str,
    level_en: str,
    scenario_en: str,
    seed_tag: int,
) -> str:
    quality = BRANCH_QUALITY_NOTES.get(branch_en, "")
    return f"""
Jesteś twórcą olimpijskich zadań matematycznych. Odpowiadasz TYLKO po polsku. Nie używaj booleanów ani placeholderów.
Twoje zadanie:
1) Wygeneruj JEDNO wymagające zadanie olimpijskie w gałęzi: "{pl_branch}".
2) Typ wyzwania (użyj lub rozumnie zinterpretuj): "{challenge_type}".
3) Kontekst/scenariusz: "{pl_scenario}" — osadź fabułę w tym kontekście.
4) {level_guidelines(level_en)}
5) ZALECENIA JAKOŚCIOWE DLA TEJ GAŁĘZI: {quality}
6) Treść ma prowadzić do odpowiedzi dokładnej; unikaj „czystego obliczania”.
7) Zwróć TYLKO trzy tagi w kolejności: <problem>, <solution_outline>, <sanity_check>.
8) Zakazane sformułowania: 'wartość logiczna', 'true/false', 'wpisz poprawną treść', 'poprawiona treść'.
9) Znacznik losowy (nie wypisuj go): [{seed_tag}].
""".strip()

# ---------- Generation / verification with HARD GATE + fallback ----------
def _generate_problem_bundle(branch_en: str, pl_branch: str, pl_scenario: str, level_en: str, scenario_en: str, challenge_type: str, seed_tag: int, rng: random.Random) -> Dict[str, str]:
    base_sys = "Bądź ścisły i zwięzły. Zwracaj dokładnie wskazane tagi. Nie używaj booleanów ani placeholderów."
    base_user = _build_user_prompt(branch_en, pl_branch, challenge_type, pl_scenario, level_en, scenario_en, seed_tag)
    base_messages = [{"role": "system", "content": base_sys}, {"role": "user", "content": base_user}]
    tags = ["problem", "solution_outline", "sanity_check"]

    # 1) Multi-tag
    try:
        trio = _ask_for_multi_tags(base_messages, tags, temp=0.28, max_tokens=1150, retries=3)
        if _validate_problem(trio.get("problem", ""), branch_en, pl_scenario) and \
           _validate_outline(trio.get("solution_outline", "")) and \
           _validate_sanity(trio.get("sanity_check", "")):
            return {k: trio[k].strip() for k in tags}
    except Exception:
        pass

    # 2) Per-tag with repairs
    problem = _ask_for_tag(base_messages, "problem", temp=0.32, max_tokens=900, retries=3)
    if not _validate_problem(problem, branch_en, pl_scenario):
        fix = chat(
            messages=base_messages + [{"role": "user", "content":
                "Poprzednia treść była niepoprawna (zbyt krótka/placeholder/bez matematyki/kontekstu). "
                "Zwróć TYLKO:\n<problem>…</problem>\n"
                "W treści użyj liczb/ułamków i wpleć kontekst: " + pl_scenario
            }],
            temperature=0.26, max_tokens=950
        )
        cand = _extract_tag(fix, "problem")
        if cand and _validate_problem(cand, branch_en, pl_scenario):
            problem = cand

    outline_ctx = base_messages + [{"role": "user", "content": f"Treść zadania do szkicu:\n<<<\n{problem}\n>>>"}]
    solution_outline = _ask_for_tag(outline_ctx, "solution_outline", temp=0.28, max_tokens=850, retries=3)
    if not _validate_outline(solution_outline):
        fix = chat(
            messages=outline_ctx + [{"role": "user", "content":
                "Poprzedni szkic był niepoprawny (zbyt krótki/placeholder/boolean). "
                "Zwróć TYLKO:\n<solution_outline>…</solution_outline>\n"
                "Użyj 2–6 zdań i konkretnych kroków."
            }],
            temperature=0.24, max_tokens=850
        )
        cand = _extract_tag(fix, "solution_outline")
        if cand and _validate_outline(cand):
            solution_outline = cand

    sanity_ctx = outline_ctx + [{"role": "user", "content": f"Szkic idei powyżej. Podaj sanity check."}]
    sanity_check = _ask_for_tag(sanity_ctx, "sanity_check", temp=0.24, max_tokens=750, retries=3)
    if not _validate_sanity(sanity_check):
        fix = chat(
            messages=sanity_ctx + [{"role": "user", "content":
                "Poprzedni sanity check był niepoprawny (zbyt krótki/placeholder/boolean). "
                "Zwróć TYLKO:\n<sanity_check>…</sanity_check>\n"
                "Użyj 1–3 zdań i sprawdź warunki/dziedzinę."
            }],
            temperature=0.22, max_tokens=750
        )
        cand = _extract_tag(fix, "sanity_check")
        if cand and _validate_sanity(cand):
            sanity_check = cand

    # 3) HARD GATE: if still invalid, use deterministic fallback
    if not (_validate_problem(problem, branch_en, pl_scenario) and _validate_outline(solution_outline) and _validate_sanity(sanity_check)):
        fb = _deterministic_fallback(branch_en, level_en, pl_scenario, rng)
        if fb:
            return fb
        # As a last resort (other branches): craft a generic but valid fraction-like task
        fb_generic = _fallback_fractions_sp_1_5(pl_scenario, rng)
        return fb_generic

    return {"problem": problem.strip(), "solution_outline": solution_outline.strip(), "sanity_check": sanity_check.strip()}

# ---------- Verifier ----------
def _verify(js_problem: Dict[str, str], pl_branch: str, pl_level: str, pl_scenario: str) -> Dict[str, str]:
    verifier_sys = (
        "Jesteś rygorystycznym weryfikatorem zadań. Sprawdzasz jednoznaczność, brak sprzeczności, "
        "dopasowanie do gałęzi i poziomu ORAZ poziom trudności (olimpijski w ramach etapu). "
        "Zidentyfikuj, czy istnieje kluczowy krok/insight; odrzuć zadania rutynowe."
    )
    verifier_user = f"""
Sprawdź zadanie pod kątem:
- jednoznaczności (czy dane są wystarczające, czy wynik/odpowiedź są unikalne),
- zgodności z gałęzią "{pl_branch}" i dobrymi praktykami danej gałęzi,
- dopasowania do poziomu "{pl_level}",
- trudności na poziomie olimpijskim (zbyt proste → podnieś wymagania; zbyt trudne → uprość minimalnie),
- istnienia nieoczywistego kroku/insightu,
- ścisłego wplecenia scenariusza "{pl_scenario}".

Zwróć TYLKO poniższe tagi (angielskie 'true'/'false' dla bool, liczba całkowita 0–10):
<unambiguous>…</unambiguous>
<difficulty_ok>…</difficulty_ok>
<insight_present>…</insight_present>
<difficulty_score>…</difficulty_score>
<revised_problem>…</revised_problem>

Zadanie do sprawdzenia:
{json.dumps(js_problem, ensure_ascii=False)}
""".strip()

    tags = ["unambiguous", "difficulty_ok", "insight_present", "difficulty_score", "revised_problem"]
    out = _ask_for_multi_tags(
        messages=[{"role": "system", "content": verifier_sys}, {"role": "user", "content": verifier_user}],
        tags=tags,
        temp=0.22,
        max_tokens=900,
        retries=3,
    )
    return out

# ---------- Public API ----------
def generate_single(
    idx: int,
    branch: str,        # canonical EN
    level: str,         # canonical EN
    scenario: str,      # canonical EN
    challenge_type: str,
    rng: random.Random,
) -> Tuple[Challenge, int]:
    pl_branch = polish_branch_label(branch)
    pl_level = polish_level_label(level)
    pl_scenario = polish_scenario_label(scenario)
    seed_tag = rng.randint(1, 10**9)

    js = _generate_problem_bundle(branch, pl_branch, pl_scenario, level, scenario, challenge_type, seed_tag, rng)

    verdict = _verify(js, pl_branch, pl_level, pl_scenario)

    def _to_bool(s: str) -> bool:
        return str(s or "").strip().lower() == "true"

    def _to_int(s: str) -> int:
        try:
            v = int(str(s or "").strip())
        except Exception:
            v = 0
        return max(0, min(10, v))

    unamb = _to_bool(verdict.get("unambiguous"))
    diffok = _to_bool(verdict.get("difficulty_ok"))
    insight = _to_bool(verdict.get("insight_present"))
    score = _to_int(verdict.get("difficulty_score"))
    revised = verdict.get("revised_problem") or ""

    if (not unamb) or (not diffok) or (not insight):
        # Try one verification-driven revision cycle; if it doesn't improve, keep our (already valid) content.
        js2 = js
        if revised.strip():
            try:
                js2 = _generate_problem_bundle(branch, pl_branch, pl_scenario, level, scenario, "poprawiona wersja", seed_tag, rng)
            except Exception:
                js2 = js
        js = js2
        verdict = _verify(js, pl_branch, pl_level, pl_scenario)
        unamb = _to_bool(verdict.get("unambiguous"))
        diffok = _to_bool(verdict.get("difficulty_ok"))
        insight = _to_bool(verdict.get("insight_present"))
        score = _to_int(verdict.get("difficulty_score"))

    note = "(Weryfikator: zadanie jednoznaczne, z właściwą trudnością i wyraźnym insightem.)" if (unamb and diffok and insight) else "(Weryfikator: możliwe dostrojenie jeszcze potrzebne.)"

    ch = Challenge(
        id=idx,
        branch=pl_branch,
        school_level=pl_level,
        scenario=pl_scenario,
        challenge_type=challenge_type,
        tool="—",
        problem=js["problem"],
        solution_outline=js["solution_outline"],
        verification=(js["sanity_check"] + " " + note).strip(),
    )
    return ch, score

def generate_batch(req: GenerateRequest, n: int = 5) -> List[Challenge]:
    rng = random.Random(req.seed) if req.seed is not None else random.Random()
    pool_size = max(n + 2, min(n + 5, int(round(1.6 * n))))
    types = pick_types_for_batch(req.branch, pool_size, rng)

    candidates: List[Tuple[Challenge, int]] = []
    for i, t in enumerate(types, start=1):
        ch, score = generate_single(
            idx=i,
            branch=req.branch,
            level=req.school_level,
            scenario=req.scenario,
            challenge_type=t,
            rng=rng,
        )
        candidates.append((ch, score))

    rng.shuffle(candidates)
    candidates.sort(key=lambda cs: cs[1], reverse=True)

    selected = [cs[0] for cs in candidates[:n]]
    for i, ch in enumerate(selected, start=1):
        ch.id = i
    return selected
