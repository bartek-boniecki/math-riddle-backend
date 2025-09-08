# app/main.py

import os
from typing import List

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse, HTMLResponse
from dotenv import load_dotenv

from .schemas import GenerateRequest, GenerateResponse

load_dotenv()


def _cors_origins_from_env() -> List[str]:
    raw = (os.getenv("CORS_ORIGINS") or "*").strip()
    if raw in ("", "*"):
        return ["*"]
    return [x.strip() for x in raw.split(",") if x.strip()]


app = FastAPI(
    title="Olympiad Math Challenge Generator (PL)",
    description="Backend AI do generowania 5 trudnych zadań matematycznych po polsku.",
    version="1.2.0",
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
    Zwraca polskie listy do pól formularza. Backend akceptuje również dawne angielskie aliasy.
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
    branch: str = Query(..., description="Dziedzina (PL; patrz /meta)"),
    school_level: str = Query(..., description="Poziom szkoły (PL; patrz /meta)"),
    scenario: str = Query(..., description="Scenariusz (PL; patrz /meta)"),
    seed: int | None = Query(None, description="Opcjonalne ziarno losowości"),
):
    from .schemas import GenerateRequest as GR
    from .generator import generate_batch

    try:
        req = GR(branch=branch, school_level=school_level, scenario=scenario, seed=seed)
        challenges = generate_batch(req)
        return GenerateResponse(count=len(challenges), challenges=challenges)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/viewer", response_class=HTMLResponse)
def viewer():
    """
    Prosta strona HTML renderowana po stronie backendu, która pobiera wyniki z /generate
    i wyświetla 5 zadań. Używana przez front (np. Carrd/Wix) jako cel formularza (GET).
    """
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

  function render() {
    if (state.loading) { root.innerHTML = '<div class="loading">⏳ Generuję zestaw 5 zadań…</div>'; return; }
    if (state.error) { root.innerHTML = '<div class="error">Błąd: '+esc(state.error)+'</div>'; return; }
    const items = (state.data && state.data.challenges) || [];
    const meta =
      'Parametry: <b>'+esc(params.branch)+'</b> · '+
      '<b>'+esc(params.school_level)+'</b> · '+
      '<b>'+esc(params.scenario)+'</b>' +
      (params.seed ? ' · seed=<b>'+esc(params.seed)+'</b>' : '');

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
        '<button class="btn" onclick="(function(){ const blob=new Blob([JSON.stringify(state.data||{},null,2)],{type:\\'application/json;charset=utf-8\\'}); const url=URL.createObjectURL(blob); const a=document.createElement(\\'a\\'); a.href=url; a.download=\\'zadania.json\\'; document.body.appendChild(a); a.click(); a.remove(); URL.revokeObjectURL(url); })()">💾 Pobierz JSON</button>'+
      '</div>'+
      '<div class="meta">'+meta+'</div>'+
      (items.length ? '<div class="grid">'+cards+'</div>' : '<div>Brak zadań w odpowiedzi.</div>');
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
      if (!res.ok) throw new Error('Backend ' + res.status);
      state.data = await res.json();
      state.loading = false; render();
    } catch (e) {
      state.loading = false; state.error = (e && e.message) || String(e); render();
    }
  }

  render(); fetchData();
})();
</script>
</body>
</html>
    """


@app.get("/", include_in_schema=False)
def root():
    return RedirectResponse(url="/docs", status_code=302)
