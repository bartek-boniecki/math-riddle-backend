from fastapi.responses import HTMLResponse

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
      const h = Math.max(
        document.body.scrollHeight,
        document.documentElement.scrollHeight
      );
      // wyślij do rodzica (Carrd)
      parent.postMessage({ type: 'viewerHeight', h: h }, '*');
    } catch (e) {}
  }

  function render() {
    if (state.loading) {
      root.innerHTML = '<div class="loading">⏳ Generuję zestaw 5 zadań…</div>';
      postHeight();
      return;
    }
    if (state.error) {
      root.innerHTML = '<div class="error">Błąd: '+esc(state.error)+'</div>';
      postHeight();
      return;
    }
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
      '</div>'+
      '<div class="meta">'+meta+'</div>'+
      (items.length ? '<div class="grid">'+cards+'</div>' : '<div>Brak zadań w odpowiedzi.</div>');

    postHeight();  // po renderze
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

  // wysyłaj wysokość „na wszelki wypadek” też cyklicznie i po resize
  window.addEventListener('load', postHeight);
  window.addEventListener('resize', postHeight);
  setInterval(postHeight, 800);

  render(); fetchData();
})();
</script>
</body>
</html>
    """
