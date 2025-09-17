# app/generator.py

"""
Tag-based, JSON-free pipeline for robust LLM interaction.

HARDENED:
- Multi-tag generation for problem+solution_outline+sanity_check in one shot (fewer fragile hops)
- Sanitization: strip code fences, unescape HTML entities, tolerate spaces in tags
- Fuzzy parsing: accept common tag aliases (<outline>, <solution>, <szkic>…) and hyphen/underscore variants
- More retries and tokens for format-critical calls
- Fallback to single-tag flow if multi-tag still fails
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

# ---------- Tag helpers (hardened) ----------
_ALIAS_MAP: Dict[str, List[str]] = {
    "problem": ["problem", "task", "zadanie", "tresc", "treść"],
    "solution_outline": [
        "solution_outline", "solution-outline", "outline", "solution",
        "szkic", "szkic_rozwiazania", "szkic-rozwiązania", "sketch"
    ],
    "sanity_check": ["sanity_check", "sanity", "check", "weryfikacja", "sprawdzenie"],
}

_TAG_RE_CACHE: Dict[str, re.Pattern] = {}

def _make_tag_pattern(tag_name: str) -> re.Pattern:
    # allow optional whitespace around tag name; DOTALL + IGNORECASE
    return re.compile(rf"<\s*{tag_name}\s*>(.*?)</\s*{tag_name}\s*>", re.DOTALL | re.IGNORECASE)

def _get_tag_re(tag: str) -> re.Pattern:
    if tag not in _TAG_RE_CACHE:
        _TAG_RE_CACHE[tag] = _make_tag_pattern(tag)
    return _TAG_RE_CACHE[tag]

def _strip_code_fences(s: str) -> str:
    # remove any ```...``` blocks (any language), but keep inner text (we'll try tags first)
    # Actually: first try raw, then try unescaped/no-fence variants
    return re.sub(r"```.*?```", lambda m: m.group(0).strip("`"), s, flags=re.DOTALL)

def _sanitize(s: str) -> str:
    # 1) unescape html, 2) drop code fences, 3) normalize spaces in brackets
    s2 = html.unescape(s or "")
    s3 = _strip_code_fences(s2)
    return s3

def _extract_by_aliases(raw_text: str, target: str) -> Optional[str]:
    text = _sanitize(raw_text)
    # 1) exact tag
    for name in _ALIAS_MAP.get(target, [target]):
        m = _make_tag_pattern(name).search(text)
        if m:
            return m.group(1).strip()
    # 2) heuristic: look for heading-like cues if tags absent
    if target == "solution_outline":
        # find "Szkic", "Szkic rozwiązania", "Outline", capture until next tag or end
        m = re.search(r"(Szkic(?:\s+rozwiązania)?|Outline|Sketch)\s*:\s*(.+)", text, flags=re.IGNORECASE | re.DOTALL)
        if m:
            chunk = m.group(2)
            # stop at next opening tag or common section header
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
    # Try sanitized + alias patterns + heuristics
    got = _extract_by_aliases(text, tag)
    return got

def _ask_for_tag(messages: List[Dict[str, str]], tag: str, temp: float = 0.4, max_tokens: int = 700, retries: int = 3) -> str:
    """Request a single tagged field; retry with stricter instruction and example; fuzzy-parse."""
    example = f"<{tag}>Przykładowa treść – tylko w tym tagu.</{tag}>"
    prompt = (
        "Zwróć TYLKO JEDEN tag XML bez opisu ani dodatkowych linii.\n"
        f"FORMAT:\n{example}\n"
        "Bez code-fence'ów, bez atrybutów, bez komentarzy."
    )
    content = chat(messages=messages + [{"role": "user", "content": prompt}], temperature=temp, max_tokens=max_tokens)
    val = _extract_tag(content, tag)
    if val:
        return val

    for k in range(retries):
        repair = (
            "Twoja poprzednia odpowiedź była niepoprawna.\n"
            f"Podaj TYLKO:\n<{tag}>…</{tag}>\n"
            "Bez niczego więcej. Pamiętaj o zamykającym tagu."
        )
        content = chat(messages=messages + [{"role": "user", "content": repair}], temperature=0.2, max_tokens=max_tokens)
        val = _extract_tag(content, tag)
        if val:
            return val

    raise ValueError(f"Brak poprawnego tagu <{tag}> w odpowiedzi LLM.")

def _ask_for_multi_tags(messages: List[Dict[str, str]], tags: List[str], temp: float = 0.2, max_tokens: int = 900, retries: int = 3) -> Dict[str, str]:
    """Ask for multiple tags in a fixed order; retry if any missing. Fuzzy-parse results."""
    order = "\n".join([f"<{t}>…</{t}>" for t in tags])
    instr = (
        "Zwróć TYLKO poniższe tagi XML dokładnie w tej KOLEJNOŚCI i nic więcej.\n"
        "NIE używaj code-fence'ów ani atrybutów w tagach. Zachowaj każdy tag w osobnej linii.\n"
        "PRZYKŁAD:\n"
        "<problem>Treść…</problem>\n"
        "<solution_outline>Krótki szkic…</solution_outline>\n"
        "<sanity_check>Bardzo krótki sanity check…</sanity_check>\n\n"
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
    level: str,
    scenario_en: str,
    seed_tag: int,
) -> str:
    hint = scenario_hint(scenario_en)
    quality = BRANCH_QUALITY_NOTES.get(branch_en, "")
    return f"""
Twoje zadanie:
1) Wygeneruj JEDNO wymagające zadanie olimpijskie w gałęzi: "{pl_branch}".
2) Typ wyzwania (użyj lub rozumnie zinterpretuj): "{challenge_type}".
3) Dobierz metodę rozwiązania naturalnie (np. szufladkowa, inwariant/monowariant, konstrukcja, faktoryzacja, teleskopowanie – ale nie ograniczaj się do nich). 
   Zadanie ma wymagać przynajmniej jednego nieoczywistego kroku/idei.
4) Kontekst/scenariusz: "{pl_scenario}". (Hint: {hint})
5) {level_guidelines(level)}
6) ZALECENIA JAKOŚCIOWE DLA TEJ GAŁĘZI: {quality}
7) Treść ma prowadzić do odpowiedzi dokładnej (np. w postaci ułamka, pierwiastka, zbioru rozwiązań). Unikaj zadań „czysto obliczeniowych”.
8) Zapewnij jednoznaczność i możliwość pełnego rozwiązania; nie używaj rachunku różniczkowego, unikaj koordynat/„bashingu”, jeśli to niekonieczne.
9) Na końcu NIE podawaj pełnego rozwiązania, tylko krótki szkic idei (2–6 zdań).
10) Wyzwania mają być w języku polskim i dopasowane do poziomu.
11) Znacznik losowy (nie wypisuj go): [{seed_tag}].
""".strip()

# ---------- Generation / verification ----------
def _generate_problem_bundle(branch_en: str, pl_branch: str, pl_scenario: str, level: str, scenario_en: str, challenge_type: str, seed_tag: int) -> Dict[str, str]:
    """
    Preferred path: multi-tag generation for <problem>, <solution_outline>, <sanity_check>.
    Fallback: single-tag requests if needed.
    """
    base_sys = (
        "Jesteś twórcą olimpijskich zadań matematycznych. Odpowiadaj po polsku."
        " Bądź ścisły i zwięzły."
    )
    base_user = _build_user_prompt(branch_en, pl_branch, challenge_type, pl_scenario, level, scenario_en, seed_tag)
    base_messages = [{"role": "system", "content": base_sys}, {"role": "user", "content": base_user}]

    tags = ["problem", "solution_outline", "sanity_check"]

    # Attempt 1: all three at once
    try:
        trio = _ask_for_multi_tags(base_messages, tags, temp=0.2, max_tokens=1000, retries=3)
        return {k: trio[k].strip() for k in tags}
    except Exception:
        pass

    # Attempt 2: per-tag with robust parser
    problem = _ask_for_tag(base_messages, "problem", temp=0.4, max_tokens=800, retries=3)
    outline_ctx = base_messages + [{"role": "user", "content": f"Treść zadania do szkicu:\n<<<\n{problem}\n>>>"}]
    solution_outline = _ask_for_tag(outline_ctx, "solution_outline", temp=0.35, max_tokens=800, retries=3)
    sanity_ctx = outline_ctx + [{"role": "user", "content": f"Szkic idei powyżej. Podaj sanity check."}]
    sanity_check = _ask_for_tag(sanity_ctx, "sanity_check", temp=0.3, max_tokens=700, retries=3)

    return {
        "problem": problem.strip(),
        "solution_outline": solution_outline.strip(),
        "sanity_check": sanity_check.strip(),
    }

def _verify(js_problem: Dict[str, str], pl_branch: str, pl_level: str, pl_scenario: str) -> Dict[str, str]:
    """Ask verifier to return 5 tags and parse them."""
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
- istnienia nieoczywistego kroku/insightu (jeśli brak – wprowadź go minimalną zmianą treści),
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
        temp=0.2,
        max_tokens=900,
        retries=3,
    )
    return out

def _fix_problem(revised_text: str) -> Dict[str, str]:
    """Regenerate final trio from the revised text (multi-tag first, then fallback)."""
    fixer_sys = "Jesteś autorem zadań. Odpowiadaj po polsku i trzymaj się podanej treści."
    fixer_user = f"Poprawiona treść:\n<<<\n{revised_text}\n>>>"
    base = [{"role": "system", "content": fixer_sys}, {"role": "user", "content": fixer_user}]

    tags = ["problem", "solution_outline", "sanity_check"]
    try:
        trio = _ask_for_multi_tags(base, tags, temp=0.2, max_tokens=1000, retries=3)
        return {k: trio[k].strip() for k in tags}
    except Exception:
        pass

    problem = _ask_for_tag(base, "problem", temp=0.35, max_tokens=800, retries=3)
    outline = _ask_for_tag(base + [{"role": "user", "content": "Podaj szkic idei dla powyższego."}], "solution_outline", temp=0.3, max_tokens=800, retries=3)
    sanity = _ask_for_tag(base + [{"role": "user", "content": "Podaj krótki sanity check dla powyższego."}], "sanity_check", temp=0.3, max_tokens=700, retries=3)

    return {"problem": problem.strip(), "solution_outline": outline.strip(), "sanity_check": sanity.strip()}

# ---------- Single generation ----------
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

    js = _generate_problem_bundle(branch, pl_branch, pl_scenario, level, scenario, challenge_type, seed_tag)

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
        js = _fix_problem(revised if revised.strip() else js["problem"])
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

# ---------- Batch with ranking ----------
def generate_batch(req: GenerateRequest, n: int = 5) -> List[Challenge]:
    """Generate a pool (> n), rank by difficulty_score, keep top n (5 by design)."""
    rng = random.Random(req.seed) if req.seed is not None else random.Random()
    # Make a small over-sampled pool, but still snappy.
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

    rng.shuffle(candidates)  # deterministic if seed provided
    candidates.sort(key=lambda cs: cs[1], reverse=True)

    selected = [cs[0] for cs in candidates[:n]]
    for i, ch in enumerate(selected, start=1):
        ch.id = i
    return selected
