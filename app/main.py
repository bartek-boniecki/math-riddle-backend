# app/main.py
import os
from typing import List, Optional

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, HTMLResponse, RedirectResponse

# --- opcjonalnie: limiter (działa, jeśli masz app/rate_limit.py) ---
try:
    from .rate_limit import SlidingWindowLimiter  # type: ignore
    RL_PER_MIN = int(os.getenv("RL_MAX_PER_MINUTE", "5"))
    RL_PER_DAY = int(os.getenv("RL_MAX_PER_DAY", "50"))
    _limiter = SlidingWindowLimiter(max_per_minute=RL_PER_MIN, max_per_day=RL_PER_DAY)

    def _client_ip(req: Request) -> str:
        xff = req.headers.get("x-forwarded-for")
        if xff:
            return xff.split(",")[0].strip()
        cf = req.headers.get("cf-connecting-ip")
        if cf:
            return cf.strip()
        real = req.headers.get("x-real-ip")
        if real:
            return real.strip()
        return req.client.host if req.client else "unknown"

    def enforce_rate_limit(req: Request):
        ok, msg, retry = _limiter.allow(_client_ip(req))
        if not ok:
            headers = {"Retry-After": str(retry or 60)}
            raise HTTPException(status_code=429, detail=msg, headers=headers)

except Exception:
    _limiter = None

    def enforce_rate_limit(req: Request):
        return  # limiter nieaktywny


# ------------------- APP -------------------
app = FastAPI(
    title="Olympiad Math Challenge Generator (PL)",
    description="Backend AI do generowania 5 trudnych zadań matematycznych po polsku.",
    version="1.4.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # ew. zawęź do swojej domeny
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ------------------- ROOT & HEALTH -------------------
@app.get("/", include_in_schema=False)
def root():
    return RedirectResponse(url="/docs", status_code=302)


@app.get("/health")
def health():
    return {
        "status": "ok",
        "model": os.getenv("LLM_MODEL", "gpt-4o-mini"),
        "limits": {
            "per_minute": int(os.getenv("RL_MAX_PER_MINUTE", "0") or 0),
            "per_day": int(os.getenv("RL_MAX_PER_DAY", "0") or 0),
        },
    }


# ------------------- META -------------------
@app.get("/meta", response_class=JSONResponse)
def meta():
    try:
        from .schemas import BRANCH_PL, LEVEL_PL, SCENARIO_PL
        return {
            "branches": list(BRANCH_PL.values()),
            "levels": list(LEVEL_PL.values()),
            "scenarios": list(SCENARIO_PL.values()),
            "example": {
                "branch": "Kombinatoryka",
                "school_level": "liceum/technikum (klasy 9–12)",
                "scenario": "sport",
                "seed": 42,
            },
        }
    except Exception:
        # fallback – serwer nadal działa
        return {
            "branches": [],
            "levels": [],
            "scenarios": [],
            "example": {},
        }


# ------------------- GENERATE (POST) -------------------
@app.post("/generate", response_class=JSONResponse)
def generate_post(req: Request, body: dict):
    enforce_rate_limit(req)
    try:
        # Lazy imports -> bezpieczniej przy starcie
        from .schemas import GenerateRequest, GenerateResponse
        from .generator import generate_batch

        parsed = GenerateRequest(**body)
        challenges = generate_batch(parsed)
        if not challenges:
            raise HTTPException(
                status_code=502,
                detail="Generator zwrócił pusty wynik (LLM). Spróbuj ponownie lub zmień parametry.",
            )
        resp = GenerateResponse(count=len(challenges), challenges=challenges)
        return JSONResponse(content=resp.model_dump())
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ------------------- GENERATE (GET) -------------------
@app.get("/generate", response_class=JSONResponse)
def generate_get(
    req: Request,
    branch: str = Query(..., description="Dział (PL; patrz /meta)"),
    school_level: str = Query(..., description="Poziom szkoły (PL; patrz /meta)"),
    scenario: str = Query(..., description="Scenariusz (PL; patrz /meta)"),
    seed: Optional[int] = Query(None, description="Opcjonalne ziarno losowości"),
    n: Optional[int] = Query(5, description="Liczba zadań (domyślnie 5)"),
):
    enforce_rate_limit(req)
    try:
        from .schemas import GenerateRequest, GenerateResponse
        from .generator import generate_batch

        parsed = GenerateRequest(
            branch=branch,
            school_level=school_level,
            scenario=scenario,
            seed=seed,
            n=n or 5,
        )
        challenges = generate_batch(parsed)

        if not challenges:
            # świadomie sygnalizujemy błąd upstream, zamiast 200 z pustką
            raise HTTPException(
                status_code=502,
                detail="Generator zwrócił pusty wynik (LLM). Spróbuj ponownie lub zmień parametry.",
            )

        resp = GenerateResponse(count=len(challenges), challenges=challenges)
        return JSONResponse(content=resp.model_dump())

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ------------------- VIEWER (SSR HTML) -------------------
@app.get("/viewer", response_class=HTMLResponse)
def viewer():
    return """
<!doctype html>
<html lang="pl">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>Zestaw zadań</title>
<style>
  :root { color-scheme: light; }
  body { font-family: system-ui, -apple-system, Segoe UI, Roboto, Arial, sans-serif; background:#f6f7fb; margin:0; }
  .wrap { max-width: 1100px; margin: 24px auto; padding: 16px; }
  .actions { display:flex; gap:8px; flex-wrap:wrap; margin-bottom:16px; }
  .btn { padding: 10px 12px; border-radius: 10px; border:1px solid #ddd; background:#fff; cursor:pointer; }
  .meta { font-size:14px; opacity:.85; margin-bottom:16px; }
  .grid { display:grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap:16px; }
  .card { background:#fff; border:1px solid #e5e7eb; border-radius:12px; padding:16px; }
  .muted { color:#666; font-size:12px; margin-bottom:6px; }
  .label { font-weight:600; margin-top:12px; }
  .loading { padding:16px; font-size:18px; }
  .error { color:crimson; margin:16px; }
</style>
</head>
<body>
<div id="root" class="wrap"><div class="loading">⏳ Generuję zestaw 5 zadań…</div></div>
<script>
(function () {
  const root = document.getElementById('root');
  const qs = new URLSearchParams(location.search);
  const params = {
    branch: qs.get('branch') || '',
    school_level: qs.get('school_level') || '',
    scenario: qs.get('scenario') || '',
    seed: qs.get('seed') || ''
  };
  const state = { loading:true, error:null, data:null };

  const esc = s => String(s).replace(/[&<>\"']/g, m => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m]));

  function postHeight() {
    try {
      const h = Math.max(document.body.scrollHeight, document.documentElement.scrollHeight);
      parent.postMessage({ type: 'viewerHeight', h: h }, '*');
    } catch (e) {}
  }

  function render() {
    if (state.loading) {
      root.innerHTML = '<div class="loading">⏳ Generuję zestaw 5 zadań…</div>'; postHeight(); return;
    }
    if (state.error) {
      root.innerHTML = '<div class="error">Błąd: '+esc(state.error)+'</div>'; postHeight(); return;
    }

    // 👇 NEW: tolerancja na różne kształty odpowiedzi
    let items = [];
    if (Array.isArray(state.data)) {
      items = state.data;
    } else if (state.data && Array.isArray(state.data.challenges)) {
      items = state.data.challenges;
    }

    const meta =
      'Parametry: <b>'+esc(params.branch)+'</b> · '+
      '<b>'+esc(params.school_level)+'</b> · '+
      '<b>'+esc(params.scenario)+'</b>' +
      (params.seed ? ' · seed=<b>'+esc(params.seed)+'</b>' : '');

    if (!items.length) {
      root.innerHTML =
        '<div class="actions">'+
          '<button class="btn" onclick="(function(){ const q=new URLSearchParams(location.search); q.set(\\'seed\\', String(Math.floor(Math.random()*1e9))); location.search=q.toString(); })()">🔄 Wygeneruj ponownie</button>'+
        '</div>'+
        '<div class="meta">'+meta+'</div>'+
        '<div>Brak zadań w odpowiedzi.</div>';
      postHeight();
      return;
    }

    const cards = items.map(c =>
      '<div class="card">'+
        '<div class="muted"><b>#'+esc(c.id)+'</b> · '+esc(c.branch)+' · '+esc(c.school_level)+' · '+esc(c.scenario)+'</div>'+
        '<div class="muted">Typ: <i>'+esc(c.challenge_type)+'</i> · Narzędzie: <i>'+esc(c.tool)+'</i></div>'+
        '<div class="label" style="margin-top:8px;">Treść zadania</div>'+
        '<div>'+esc(c.problem).replace(/\\n/g,"<br>")+'</div>'+
        '<div class="label">Szkic rozwiązania</div>'+
        '<div>'+esc(c.solution_outline).replace(/\\n/g,"<br>")+'</div>'+
        '<div class="label">Weryfikacja</div>'+
        '<div>'+esc(c.verification).replace(/\\n/g,"<br>")+'</div>'+
      '</div>'
    ).join('');

    root.innerHTML =
      '<div class="actions">'+
        '<button class="btn" onclick="(function(){ const q=new URLSearchParams(location.search); q.set(\\'seed\\', String(Math.floor(Math.random()*1e9))); location.search=q.toString(); })()">🔄 Wygeneruj ponownie</button>'+
        '<button class="btn" onclick="(function(){ const txt=JSON.stringify(state.data||{},null,2); navigator.clipboard.writeText(txt); alert(\\'Skopiowano JSON.\\'); })()">📋 Kopiuj JSON</button>'+
      '</div>'+
      '<div class="meta">'+meta+'</div>'+
      '<div class="grid">'+cards+'</div>';

    postHeight();
  }

  async function fetchData() {
    const url = new URL('/generate', location.origin);
    url.searchParams.set('branch', params.branch);
    url.searchParams.set('school_level', params.school_level);
    url.searchParams.set('scenario', params.scenario);
    if (params.seed) url.searchParams.set('seed', params.seed);

    state.loading = true; state.error = null; render();
    try {
      const res = await fetch(url.toString(), { method: 'GET' });
      if (!res.ok) {
        let detail = 'Backend ' + res.status;
        try { const j = await res.json(); if (j && j.detail) detail = j.detail; } catch(e){}
        throw new Error(detail);
      }
      state.data = await res.json();
      state.loading = false; render();
    } catch (e) {
      state.loading = false; state.error = (e && e.message) || String(e); render();
    }
  }

  window.addEventListener('load', postHeight);
  window.addEventListener('resize', postHeight);
  setInterval(postHeight, 800);

  render(); fetchData();
})();
</script>
</body>
</html>
    """
