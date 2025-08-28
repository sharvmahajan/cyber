const express = require('express');
const fs = require('fs');
const app = express();

// trust proxy so req.ip uses X-Forwarded-For when present (useful behind proxies)
app.set('trust proxy', true);

app.get('/track', (req, res) => {
  const ip = req.ip || req.headers['x-forwarded-for'] || req.connection.remoteAddress;
  const ua = req.get('User-Agent') || '-';
  const referer = req.get('Referer') || '-';
  const line = `${new Date().toISOString()} IP=${ip} UA="${ua}" Referer="${referer}"\n`;
  fs.appendFileSync('hits.log', line);
  res.send(`Thanks — your IP was recorded as: <strong>${ip}</strong>`);
});

app.get('/', (req, res) => {
  res.send('<a href="/track">Click to share your IP (consent required)</a>');
});

app.listen(3000, () => console.log('Listening on port 3000'));





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