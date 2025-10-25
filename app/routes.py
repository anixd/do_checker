from flask import Blueprint, render_template_string, request, redirect, url_for, Response
from datetime import datetime
from engine.orchestrator import start_run, get_run_state
from config.loader import ConfigStore
from providers.soax import CatalogStore

bp = Blueprint("routes", __name__)

INDEX_HTML = """
<!doctype html>
<html>
<head>
  <meta charset="utf-8" />
  <title>mirror_checker</title>
  <style>
    body { font-family: system-ui, -apple-system, Segoe UI, Roboto, sans-serif; margin: 24px; }
    textarea { width: 100%; height: 140px; }
    .row { display:flex; gap:12px; align-items:center; flex-wrap: wrap; }
    .card { border:1px solid #ddd; border-radius:8px; padding:12px; margin:8px 0; }
    .muted { color:#666; font-size:12px; }
    label { font-size:14px; }
  </style>
</head>
<body>
  <h1>Mirror Checker</h1>

  <form method="post" action="{{ url_for('routes.launch_run') }}">
    <label>URL(s), one per line</label><br/>
    <textarea name="urls" placeholder="somesite.com&#10;othersite.org"></textarea>
    <div class="row">
      <label>Country:
        <select name="country" id="country" required>
          <option value="" disabled selected>-- choose --</option>
          {% for c in countries %}
            <option value="{{c.code}}">{{c.code}} — {{c.name}}</option>
          {% endfor %}
        </select>
      </label>
      <label>Region:
        <select name="region">
          <option value="">(any)</option>
          <!-- будет уточняться на стороне сервера в v0.3; пока простой ввод -->
        </select>
      </label>
      <label>ISP:
        <input name="isp" placeholder="(optional)"/>
      </label>
    </div>
    <div class="row">
      <label>Proxy:
        <select name="proxy_type">
          <option value="http" {% if defaults.proxy_type=='http' %}selected{% endif %}>HTTP</option>
          <option value="socks5" {% if defaults.proxy_type=='socks5' %}selected{% endif %}>SOCKS5</option>
        </select>
      </label>
      <label>DNS:
        <select name="dns_mode">
          <option value="proxy" {% if defaults.dns_mode=='proxy' %}selected{% endif %}>via proxy</option>
          <option value="local" {% if defaults.dns_mode=='local' %}selected{% endif %}>local</option>
        </select>
      </label>
      <label>Sticky:
        <select name="sticky_policy">
          <option value="auto" {% if defaults.sticky_policy=='auto' %}selected{% endif %}>auto</option>
          <option value="on" {% if defaults.sticky_policy=='on' %}selected{% endif %}>on</option>
          <option value="off" {% if defaults.sticky_policy=='off' %}selected{% endif %}>off</option>
        </select>
      </label>
      <label>TTL (sec):
        <input name="sticky_ttl_sec" type="number" min="60" value="{{defaults.sticky_ttl_sec}}"/>
      </label>
      <label>Timeout (sec):
        <input name="timeout_sec" type="number" min="5" value="{{defaults.timeout_sec}}"/>
      </label>
      <label>
        <input type="checkbox" name="make_screenshot" {% if defaults.screenshots_enabled %}checked{% endif %}/> Screenshots
      </label>
    </div>
    <div class="row">
      <button type="submit">Run checks</button>
      <a href="{{ url_for('routes.catalog') }}">Geo catalog</a>
      <a href="{{ url_for('routes.settings') }}">Settings</a>
    </div>
    <p class="muted">Files will be saved under {{ logs_dir }}</p>
  </form>
</body>
</html>
"""

RUN_HTML = """
<!doctype html>
<html>
<head>
  <meta charset="utf-8" />
  <title>Run {{run_id}}</title>
  <style>
    body { font-family: system-ui, -apple-system, Segoe UI, Roboto, sans-serif; margin: 24px; }
    .card { border:1px solid #ddd; border-radius:8px; padding:12px; margin:8px 0; }
    .ok { color: #0a7d00; }
    .err { color: #b00020; }
    code { background:#f6f6f6; padding:2px 6px; border-radius:4px; }
  </style>
</head>
<body>
  <h2>Run: <code>{{run_id}}</code></h2>
  <div id="events"></div>

<script>
const evbox = document.getElementById('events');
const es = new EventSource("{{ url_for('sse.events', run_id=run_id) }}");
es.onmessage = (e) => {
  try {
    const payload = JSON.parse(e.data);
    const div = document.createElement('div');
    div.className = 'card';
    div.textContent = `[${payload.type}] ` + JSON.stringify(payload);
    evbox.prepend(div);
    if (payload.type === 'run_finished') { es.close(); }
  } catch(err) {
    console.error(err);
  }
};
</script>
</body>
</html>
"""

CATALOG_HTML = """
<!doctype html><html><head><meta charset="utf-8"><title>Geo Catalog</title></head>
<body>
  <h2>SOAX Geo Catalog</h2>
  <pre>{{ catalog|tojson(indent=2) }}</pre>
  <form method="post" action="{{ url_for('routes.catalog_refresh') }}">
    <button type="submit">Refresh from SOAX (stub for now)</button>
  </form>
</body></html>
"""

SETTINGS_HTML = """
<!doctype html><html><head><meta charset="utf-8"><title>Settings</title></head>
<body>
  <h2>Settings</h2>
  <form method="post">
    <textarea name="yaml" style="width:100%;height:400px">{{ yaml }}</textarea><br/>
    <button type="submit">Save</button>
  </form>
</body></html>
"""

@bp.get("/")
def index():
    cfg = ConfigStore.get()
    catalog = CatalogStore.load()
    return render_template_string(
        INDEX_HTML,
        countries=catalog.get("countries", []),
        defaults=dict(
            proxy_type=cfg.proxy.type,
            dns_mode=cfg.proxy.dns_mode,
            sticky_policy=cfg.proxy.sticky_policy,
            sticky_ttl_sec=cfg.proxy.sticky_ttl_sec,
            timeout_sec=cfg.execution.timeout_sec,
            screenshots_enabled=cfg.screenshots.enabled_default,
        ),
        logs_dir=cfg.paths.logs_dir,
    )

@bp.post("/run")
def launch_run():
    urls_raw = (request.form.get("urls") or "").strip()
    urls = [u.strip() for u in urls_raw.splitlines() if u.strip()]
    if not urls:
        return Response("No URLs provided", status=400)

    country = request.form.get("country") or ""
    region = request.form.get("region") or None
    isp = request.form.get("isp") or None

    proxy_type = request.form.get("proxy_type") or "http"
    dns_mode = request.form.get("dns_mode") or "proxy"
    sticky_policy = request.form.get("sticky_policy") or "auto"
    sticky_ttl_sec = int(request.form.get("sticky_ttl_sec") or 360)
    timeout_sec = int(request.form.get("timeout_sec") or 60)
    make_screenshot = bool(request.form.get("make_screenshot"))

    run_id = start_run(
        urls=urls,
        country=country,
        region_code=region,
        isp=isp,
        proxy_type=proxy_type,
        dns_mode=dns_mode,
        sticky_policy=sticky_policy,
        sticky_ttl_sec=sticky_ttl_sec,
        timeout_sec=timeout_sec,
        make_screenshot=make_screenshot,
    )
    return redirect(url_for("routes.run_page", run_id=run_id))

@bp.get("/run/<run_id>")
def run_page(run_id: str):
    state = get_run_state(run_id)
    return render_template_string(RUN_HTML, run_id=run_id, state=state)

@bp.get("/catalog")
def catalog():
    return render_template_string(CATALOG_HTML, catalog=CatalogStore.load())

@bp.post("/catalog/refresh")
def catalog_refresh():
    from providers.soax import refresh_catalog
    refresh_catalog()
    return redirect(url_for("routes.catalog"))

@bp.get("/settings")
def settings():
    yaml = ConfigStore.raw_yaml()
    return render_template_string(SETTINGS_HTML, yaml=yaml)

@bp.post("/settings")
def settings_save():
    yaml_text = request.form.get("yaml") or ""
    ConfigStore.save_yaml(yaml_text)
    return redirect(url_for("routes.settings"))

