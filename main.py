import os
import json
import logging
from datetime import datetime
from flask import Flask, request, render_template_string, jsonify, abort
from werkzeug.middleware.proxy_fix import ProxyFix

# Configuration
LOGFILE = os.environ.get("HITS_LOG", "hits.log")
ADMIN_TOKEN = os.environ.get("ADMIN_TOKEN", "changeme")  # change before deploy
TRUST_PROXY = os.environ.get("TRUST_PROXY", "1") == "1"  # set to "0" if not behind proxy

app = Flask(__name__)
if TRUST_PROXY:
    # If you're behind nginx/ELB/Cloudflare, set TRUST_PROXY=1 and ensure proxies set X-Forwarded-For
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1)

# basic file logging
logging.basicConfig(filename=LOGFILE, level=logging.INFO, format='%(asctime)s %(message)s')

# helpers
def normalize_ip(ip: str) -> str:
    if not ip:
        return ip
    # If multiple IPs (X-Forwarded-For), take the left-most
    if ',' in ip:
        ip = ip.split(',')[0].strip()
    # strip IPv4-mapped IPv6 prefix
    if ip.startswith("::ffff:"):
        ip = ip.split("::ffff:")[-1]
    return ip

def client_ip_from_request() -> str:
    # Prefer X-Forwarded-For (ProxyFix will adjust request.remote_addr when TRUST_PROXY used)
    xff = request.headers.get('X-Forwarded-For', '')
    if xff:
        candidate = xff.split(',')[0].strip()
    else:
        candidate = request.remote_addr
    return normalize_ip(candidate)

# Routes
INDEX_HTML = """
<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <title>IP Reporter (Consent Required)</title>
  <style>
    body { font-family: system-ui, -apple-system, "Segoe UI", Roboto, Arial; margin: 0; padding: 1.25rem; background:#f7f7fb; color:#111; }
    .banner { position: fixed; left:0; right:0; top:0; background:white; border-bottom: 1px solid #eee; padding: 1rem; display:flex; gap:1rem; align-items:center; z-index:100;}
    .content { margin-top:5.25rem; }
    button { padding: .5rem .9rem; border-radius:8px; border:1px solid #ddd; background:#fff; cursor:pointer; }
    button.primary { background:#0b66ff; color:#fff; border-color: #0b66ff; }
    .box { background:#fff; padding:1rem; border-radius:10px; box-shadow: 0 1px 3px rgba(0,0,0,.06); max-width:720px; }
    pre { background:#f4f6fb; padding: .75rem; border-radius:6px; overflow:auto; }
    .muted { color:#666; font-size:.95rem; }
  </style>
</head>
<body>
  <div class="banner" id="consentBanner">
    <div style="flex:1;">
      <strong>Requesting permission:</strong>
      <div class="muted">This page will detect your public IPv4 address and send it to the server for troubleshooting. We will only collect this after you explicitly consent.</div>
    </div>
    <div>
      <button id="declineBtn">Decline</button>
      <button id="consentBtn" class="primary">I consent</button>
    </div>
  </div>

  <div class="content">
    <div class="box">
      <h2>IP Reporter</h2>
      <p class="muted">After you click <strong>I consent</strong> the page will detect your public IPv4 and send it to the server. The server will also record the address it sees for your request. You can revoke consent by closing this page.</p>

      <div id="status">
        <p><em>Waiting for consent...</em></p>
      </div>

      <hr/>
      <h3>Last recorded values</h3>
      <div id="results">
        <p class="muted">No data yet.</p>
      </div>

      <hr/>
      <p class="muted">Logs are retained in server file: <code>{{ logfile }}</code></p>
    </div>
  </div>

<script>
const outStatus = document.getElementById('status');
const results = document.getElementById('results');
const consentBtn = document.getElementById('consentBtn');
const declineBtn = document.getElementById('declineBtn');
const banner = document.getElementById('consentBanner');

const ipv4Regex = /^(25[0-5]|2[0-4]\\d|1?\\d{1,2})(\\.(25[0-5]|2[0-4]\\d|1?\\d{1,2})){3}$/;

function showStatus(msg) {
  outStatus.innerHTML = '<p>' + msg + '</p>';
}

function showResults(server, client, ua) {
  results.innerHTML = `
    <p><strong>Server-observed IP:</strong> <code>${server || '-'}</code></p>
    <p><strong>Client-reported public IPv4:</strong> <code>${client || '-'}</code></p>
    <p class="muted"><strong>User agent:</strong> ${ua || '-'}</p>
  `;
}

consentBtn.addEventListener('click', async () => {
  banner.style.display = 'none'; // hide banner after consent
  showStatus('Detecting public IPv4…');

  try {
    // 1) Get public IPv4 from a public service (ipify)
    const r = await fetch('https://api.ipify.org?format=json', {cache: 'no-store'});
    if (!r.ok) throw new Error('Failed to contact ipify');
    const j = await r.json();
    const client_ip = j && j.ip ? j.ip : null;
    if (!client_ip || !ipv4Regex.test(client_ip)) {
      throw new Error('No IPv4 returned by ipify');
    }

    showStatus('Reporting to server…');

    // 2) POST to our server /report endpoint
    const resp = await fetch('/report', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({
        client_reported_ip: client_ip,
        ts: new Date().toISOString(),
        ua: navigator.userAgent
      })
    });

    if (!resp.ok) {
      const txt = await resp.text();
      throw new Error('Server error: ' + txt);
    }

    const data = await resp.json();
    showStatus('Report recorded. See values below.');
    showResults(data.server_observed_ip, data.client_reported_ip, data.client_ua);
  } catch (err) {
    showStatus('Error: ' + (err && err.message ? err.message : err));
  }
});

declineBtn.addEventListener('click', () => {
  banner.style.display = 'none';
  showStatus('You declined. Nothing was collected.');
});
</script>
</body>
</html>
"""

@app.route('/')
def index():
    return render_template_string(INDEX_HTML, logfile=LOGFILE)

@app.route('/report', methods=['POST'])
def report():
    payload = request.get_json(silent=True)
    if not payload:
        return "Bad request: expected JSON", 400

    # require the client-side to indicate consent (client code only sends after consent)
    client_reported_ip = payload.get('client_reported_ip') or ''
    client_ua = payload.get('ua') or request.headers.get('User-Agent', '-')
    ts = payload.get('ts') or datetime.utcnow().isoformat()

    server_ip = client_ip_from_request()
    client_reported_ip = normalize_ip(str(client_reported_ip).strip())

    line = {
        'ts': ts,
        'server_observed_ip': server_ip,
        'client_reported_ip': client_reported_ip,
        'client_ua': client_ua,
        'referer': request.referrer or '-',
        'headers': {k:v for k,v in request.headers.items()}
    }
    # Append a single-line JSON record to logfile for easy parsing
    logging.info(json.dumps(line, ensure_ascii=False))
    return jsonify({
        'status': 'ok',
        'server_observed_ip': server_ip,
        'client_reported_ip': client_reported_ip,
        'client_ua': client_ua
    })

@app.route('/logs')
def view_logs():
    token = request.args.get('token', '')
    if not ADMIN_TOKEN or token != ADMIN_TOKEN:
        abort(403)
    # Return last 200 lines for convenience
    try:
        with open(LOGFILE, 'r', encoding='utf-8') as f:
            lines = f.readlines()
    except FileNotFoundError:
        return "<pre>No logs yet.</pre>", 200
    last = lines[-200:]
    # show as preformatted JSON lines
    safe = "".join(last)
    return "<pre>" + safe + "</pre>", 200

if __name__ == '__main__':
    # Development server. For production, use gunicorn behind a reverse proxy with TLS.
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)), debug=False)
