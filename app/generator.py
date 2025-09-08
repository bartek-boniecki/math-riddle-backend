# app/generator.py
import json
import random
import re
from typing import Dict, List, Tuple

from .schemas import Challenge, GenerateRequest
from .llm import chat

# ====== ZBIORY TYPÓW ZADAŃ (charakterystyczne dla gałęzi) ======
# UWAGA: zestawy są szerokie; generator losuje typy i narzędzia zgodnie z ograniczeniami.

BRANCH_TO_TYPES: Dict[str, List[str]] = {
    "Numbers and operations": [
        "sprytne łamanie nawiasów i porządek działań",
        "nietrywialne własności cyfr i sum cyfr",
        "złożone zadanie na NWD/NWW w kontekście praktycznym",
        "równoważność arytmetyczna z ukrytym wzorem rekurencyjnym",
        "szacowanie błędów i zaokrągleń w ciągu operacji",
        "nietrywialne prawa dzielenia z resztą w historii słownej",
        "balansowanie wyrażeń z nietypowymi działaniami (operatory zdefiniowane)",
    ],
    "Algebraic expressions": [
        "sprytne rozbijanie ułamków algebraicznych",
        "identyczność wielomianowa z parametrem",
        "zastępstwo zmiennych i homogenizacja",
        "minimalizacja wartości wyrażenia pod warunkiem",
        "nierówności AM-GM/CS w przebraniu wyrażeń",
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
        "rozsądne rozdzielanie ułamków na sumy egipskie",
        "porównywanie ułamków przez krzyżowanie/estymaty",
        "złożone skracanie z warunkami całkowitości",
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
    "Sequences": [
        "rekurencje nieliniowe z inwariantem",
        "telekopowanie sum",
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

# Typowe narzędzia/techniki – dobierane losowo do typu/gałęzi
TOOLS_POOL = [
    "Zasada szufladkowa",
    "Inwariant/monowariant",
    "Konstrukcja pomocnicza",
    "Podstawienie sprytne",
    "Nierówności klasyczne (AM-GM, Cauchy-Schwarz, Jensen)",
    "Różniczkowanie/analiza monotoniczności (intuicyjnie)",
    "Potęga punktu / podobieństwo trójkątów",
    "Vieta / Vieta jumping",
    "Faktoryzacja / dodaj i odejmij to samo",
    "Dwukrotne liczenie",
    "Bijekcja/kombinatoryka konstruktywna",
    "Równania funkcyjne (metoda stałej/stycznej)",
    "Racjonalizacja / sprytne przekształcenia",
    "Redukcja do absurdu",
    "Zastąpienie zmiennych (homogenizacja)",
    "Telescoping",
    "Normalizacja i skalowanie",
]

# Wytyczne zależne od poziomu szkoły (po polsku)
def level_guidelines(level: str) -> str:
    if level == "lower elementary school (grades 1-5)":
        return (
            "Poziom: klasy 1–5. Zadanie ma być olimpijskie dla tego etapu: bez zaawansowanego rachunku, "
            "może używać sprytu, parzystości, prostych niezmienników, rysunków/siatek, małą liczbę przypadków. "
            "Unikaj rachunku różniczkowego, logarytmów i złożonych równań; dopuszczalne są proste równania/liczenie."
        )
    if level == "higher elementary school / middle school (grades 6-8)":
        return (
            "Poziom: klasy 6–8. Zadanie ambitne, możliwe narzędzia: nierówności elementarne, konstrukcje geometryczne, "
            "zasada szufladkowa, proste rekurencje, ułamki łańcuchowe intuicyjnie. Bez rachunku różniczkowego."
        )
    return (
        "Poziom: szkoła średnia (9–12). Zadanie olimpijskie, może wymagać kombinatoryki na poziomie olimpiady, "
        "nietrywialnych przekształceń algebraicznych, tożsamości trygonometrycznych, sprytnych układów równań, "
        "analizy funkcji bez formalnego całkowania."
    )

def scenario_hint(s: str) -> str:
    hints = {
        "engineering": "Osadź historię w realiach inżynierskich (projekt, ograniczenia materiałowe, parametry).",
        "transport": "Użyj motywu rozkładów jazdy, prędkości, opóźnień, grafów połączeń.",
        "sport": "Wpleć turnieje, ranking, mecze, treningi, limity czasu.",
        "food and beverage": "Wykorzystaj przepisy, proporcje, mieszanki smaków, porcje, kuchnię.",
        "entertainment": "Osadź w koncertach, kinie, grach planszowych, streamingach.",
        "family": "Użyj domowych sytuacji: zakupy, plan dnia, obowiązki, kieszonkowe.",
        "holidays": "Wpleć podróże, plan zwiedzania, waluty, strefy czasowe, noclegi.",
    }
    return hints.get(s, "")

def pick_types_for_batch(branch: str, n: int = 5, rng: random.Random | None = None) -> List[str]:
    rng = rng or random
    pool = BRANCH_TO_TYPES[branch]
    chosen: List[str] = []
    counts: Dict[str, int] = {}
    while len(chosen) < n:
        t = rng.choice(pool)
        if counts.get(t, 0) < 2:  # najwyżej 2 wystąpienia jednego typu
            chosen.append(t)
            counts[t] = counts.get(t, 0) + 1
    return chosen

def pick_tool(rng: random.Random | None = None) -> str:
    rng = rng or random
    return rng.choice(TOOLS_POOL)


def _json_from_text(txt: str) -> Dict:
    """
    Solidne wyciąganie JSON:
    1) Spróbuj bezpośrednio json.loads.
    2) Spróbuj z bloku ```json ... ```.
    3) Ostatnia próba: dopasuj pierwszy poprawnie zbalansowany blok {...} licząc nawiasy,
       z uwzględnieniem cudzysłowów i escapów.
    """
    import json
    import re

    # 1) prosto
    try:
        return json.loads(txt)
    except Exception:
        pass

    # 2) code fence
    m = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", txt, flags=re.DOTALL | re.IGNORECASE)
    if m:
        cand = m.group(1)
        try:
            return json.loads(cand)
        except Exception:
            pass

    # 3) zbalansowane nawiasy
    s = txt
    start = s.find("{")
    while start != -1:
        depth = 0
        in_str = False
        esc = False
        for j in range(start, len(s)):
            ch = s[j]
            if in_str:
                if esc:
                    esc = False
                elif ch == "\\":
                    esc = True
                elif ch == '"':
                    in_str = False
            else:
                if ch == '"':
                    in_str = True
                elif ch == "{":
                    depth += 1
                elif ch == "}":
                    depth -= 1
                    if depth == 0:
                        cand = s[start : j + 1]
                        try:
                            return json.loads(cand)
                        except Exception:
                            break
        start = s.find("{", start + 1)
    raise ValueError("Brak poprawnego JSON w odpowiedzi LLM.")


def generate_single(
    idx: int,
    branch: str,
    level: str,
    scenario: str,
    challenge_type: str,
    tool: str,
    rng: random.Random,
) -> Challenge:
    seed_tag = rng.randint(1, 10**9)
    sys = (
        "Jesteś twórcą olimpijskich zadań matematycznych. Odpowiadaj wyłącznie po polsku. "
        "Zachowuj ścisłość, zwięzłość i brak zbędnej narracji poza treścią zadania."
    )
    user = f"""
Twoje zadanie:
1) Wygeneruj JEDNO wymagające zadanie olimpijskie w gałęzi: "{branch}".
2) Typ wyzwania (koniecznie użyj): "{challenge_type}".
3) Narzędzie/technika, która ma być przydatna/przewodnia: "{tool}".
4) Kontekst/scenariusz: "{scenario}". {scenario_hint(scenario)}
5) {level_guidelines(level)}
6) Sformułuj treść jako realistyczną historię, ale bez zbędnych opisów. 
7) Zapewnij jednoznaczność i możliwość pełnego rozwiązania.
8) Na końcu NIE podawaj pełnego rozwiązania, tylko krótki szkic idei.
9) Użyj tego znacznika losowego WYŁĄCZNIE do zdywersyfikowania treści (nie wypisuj go w odpowiedzi): [{seed_tag}].

Zwróć ściśle JSON w formacie:
{{
  "problem": "treść zadania (1 akapit lub punktowana lista)",
  "solution_outline": "krótki szkic idei rozwiązania (2-6 zdań)",
  "sanity_check": "krótka weryfikacja jednoznaczności i sensowności warunków (1-3 zdania)"
}}
"""
    content = chat(
        messages=[{"role": "system", "content": sys}, {"role": "user", "content": user}],
        temperature=0.85,
        response_format="json_object",
    )
    js = _json_from_text(content)
    # Druga faza: niezależny weryfikator/agent
    verifier_sys = (
        "Jesteś rygorystycznym weryfikatorem zadań. Sprawdzasz jednoznaczność, brak sprzeczności i poziom trudności."
    )
    verifier_user = f"""
Sprawdź zadanie pod kątem:
- jednoznaczności (czy dane są wystarczające, czy wynik jest unikalny),
- zgodności z gałęzią "{branch}",
- dopasowania do poziomu "{level}",
- ścisłego wplecenia scenariusza "{scenario}",
- użyteczności narzędzia "{tool}".

Jeśli trzeba, zaproponuj minimalne poprawki treści (bez zmiany istoty), aby usunąć niejednoznaczność.
Zwróć ściśle JSON:
{{
  "unambiguous": true/false,
  "reason": "krótkie uzasadnienie",
  "revised_problem": "jeśli false, tu podaj poprawioną treść; jeśli true, powtórz oryginalną treść"
}}
Zadanie do sprawdzenia:
{json.dumps(js, ensure_ascii=False)}
"""
    vresp = chat(
        messages=[{"role": "system", "content": verifier_sys}, {"role": "user", "content": verifier_user}],
        temperature=0.3,
        response_format="json_object",
    )
    vjs = _json_from_text(vresp)
    # Jeśli niejednoznaczne, weź poprawioną treść i poproś o szkic na nowo (zachowując ten sam typ)
    if not vjs.get("unambiguous", False):
        fixer_sys = "Jesteś autorem zadań. Odpowiadaj po polsku i trzymaj się podanej treści."
        fixer_user = f"""
Na podstawie poprawionej treści zadania poniżej, wygeneruj krótki szkic idei oraz sanity check.
Zwróć ściśle JSON:
{{
  "problem": "ostateczna treść",
  "solution_outline": "krótki szkic",
  "sanity_check": "krótka weryfikacja jednoznaczności"
}}
Poprawiona treść:
{vjs.get("revised_problem","")}
"""
        fresp = chat(
            messages=[{"role": "system", "content": fixer_sys}, {"role": "user", "content": fixer_user}],
            temperature=0.6,
            response_format="json_object",
        )
        js = _json_from_text(fresp)
        verification_note = f"(Weryfikator: poprawiono treść. Powód: {vjs.get('reason','')})"
    else:
        verification_note = "(Weryfikator: zadanie jednoznaczne.)"

    return Challenge(
        id=idx,
        branch=branch,
        school_level=level,
        scenario=scenario,
        challenge_type=challenge_type,
        tool=tool,
        problem=js["problem"].strip(),
        solution_outline=js["solution_outline"].strip(),
        verification=(js.get("sanity_check","").strip() + " " + verification_note).strip(),
    )

def generate_batch(req: GenerateRequest) -> List[Challenge]:
    rng = random.Random(req.seed) if req.seed is not None else random.Random()
    types = pick_types_for_batch(req.branch, 5, rng)
    # Każde zadanie otrzymuje (być może różne) narzędzie
    challenges: List[Challenge] = []
    for i, t in enumerate(types, start=1):
        tool = pick_tool(rng)
        ch = generate_single(
            idx=i,
            branch=req.branch,
            level=req.school_level,
            scenario=req.scenario,
            challenge_type=t,
            tool=tool,
            rng=rng,
        )
        challenges.append(ch)
    # Ostateczna kontrola: w każdym zbiorze jest dokładnie 5, typy z ograniczeniem <=2 spełnione,
    # wszystkie po polsku (heurystyka: obecność polskich znaków nie jest wymagana – dopuszczamy poprawną polszczyznę bez diakrytyków)
    # Dodatkowe sprawdzenia mogłyby być tu dodane.
    return challenges
