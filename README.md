# 🇵🇱 Math Riddle Generator (Backend)

Backend FastAPI, który generuje **5 polskich zadań** (każde z zagadką logiczną) dla wybranego działu matematyki
i poziomu ucznia, a następnie **weryfikuje jednoznaczność rozwiązania** przy użyciu ograniczeń w formacie SymPy.

## Funkcje
- Endpoint `POST /generate` – przyjmuje `{ "math_branch": "...", "student_class": 6 }`
  i zwraca 5 zweryfikowanych zadań na poziomie **+2 klasy**.
- Wymusza polski tekst zadań, podaje zakresy zmiennych i ograniczenia w postaci wyrażeń SymPy.
- Sprawdza jednoznaczność rozwiązania i zgodność odpowiedzi (`unique == true` i `consistent_with_llm_answer == true`).
- Przygotowany do lokalnych testów i wdrożenia w chmurze (Dockerfile).
- CORS włączony – łatwa integracja z frontendem TeleportHQ.

## Szybki start (lokalnie)
1. Zainstaluj wymagania:
   ```bash
   pip install -r requirements.txt
   ```
2. Ustaw zmienne środowiskowe (przynajmniej klucz modeli):
   ```bash
   export OPENAI_API_KEY=sk-...           # Twój klucz
   export OPENAI_MODEL=gpt-4o-mini        # lub inny dostępny model czatu
   ```
3. Uruchom serwer:
   ```bash
   uvicorn app.main:app --reload --port 8000
   ```
4. Przetestuj:
   ```bash
   curl -X POST http://localhost:8000/generate \
     -H "Content-Type: application/json" \
     -d '{"math_branch":"algebra","student_class":6}'
   ```

## Wdrożenie w chmurze
- **Docker**:
  ```bash
  docker build -t math-riddle-backend .
  docker run -e OPENAI_API_KEY=sk-... -e OPENAI_MODEL=gpt-4o-mini -p 8000:8000 math-riddle-backend
  ```
- Nadaje się do uruchomienia na Render/Fly.io/Heroku/Cloud Run.

## Integracja z TeleportHQ
- Skonfiguruj w TeleportHQ zapytanie HTTP do `POST /generate`.
- Przykładowe body:
  ```json
  { "math_branch": "geometria", "student_class": 5 }
  ```
- Odbierzesz listę 5 zadań z polskimi polami: `riddle_pl`, `question_pl`, `computed_variables`, `computed_answer`.

## Jak działa weryfikacja
Model generuje JSON zawierający:
- `variables` z dziedzinami (`Z`, `N`, `R`) i przedziałami dla całkowitych,
- `constraints_sympy` – warunki zapisane w notacji SymPy,
- `final_expression_sympy` i `answer` – do sprawdzenia obliczeniowego.

Następnie `app/solver.py`:
- Dla zmiennych całkowitych – **enumeracja w skończonych przedziałach** (limit 200k).
- Dla zmiennych rzeczywistych – próba rozwiązania układu (linsolve / solveset) i filtrowanie nierówności.
- Sprawdza, że istnieje **dokładnie jedno rozwiązanie** oraz że `computed_answer == answer`.

## Uwagi projektowe
- Pilnujemy, aby generator używał tylko funkcji SymPy wskazanych w promptach – to ułatwia niezawodną weryfikację.
- Jeśli chcesz zaostrzyć wymagania (np. zawsze dziedzina całkowita), doprecyzuj `SYSTEM_PROMPT_PL` w `app/prompts.py`.
- Logikę „naprawiania” zadań (ponowne dopytanie LLM w razie niezgodności) można dodać jako pętlę retry.
- W razie potrzeby można dodać wersjonowanie modeli i telemetrię.

## Testy
```bash
pytest -q
```

## Licencja
MIT – używaj i modyfikuj według potrzeb.
