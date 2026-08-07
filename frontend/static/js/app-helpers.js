// Helpers

async function api(path, opts = {}) {
  const res = await fetch(path, opts);
  const contentType = String(res.headers.get('content-type') || '').toLowerCase();
  if (!res.ok) {
    const rawText = await res.text().catch(() => '');
    let body = null;
    if (rawText && contentType.includes('application/json')) {
      try {
        body = JSON.parse(rawText);
      } catch {
        body = null;
      }
    }
    const fallback = `HTTP ${res.status}${res.statusText ? ` ${res.statusText}` : ''}`.trim();
    throw new Error(_extractApiErrorMessage(body, fallback, rawText));
  }

  // Some successful endpoints intentionally return no body (e.g., 204 delete).
  if (res.status === 204 || res.status === 205) return null;

  if (contentType.includes('application/json')) {
    return res.json();
  }

  const text = await res.text();
  if (!text) return null;
  try {
    return JSON.parse(text);
  } catch {
    return text;
  }
}

function _isTransientFetchError(error) {
  const msg = String(error?.message || error || '');
  return /Failed to fetch|NetworkError|Load failed/i.test(msg);
}

function _waitMs(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

async function _loadMapAndConfigWithRetry(mapName, maxRetries = 2) {
  let attempt = 0;
  while (true) {
    try {
      const encoded = encodeURIComponent(mapName);
      return await Promise.all([
        api(`/api/maps/${encoded}`),
        api('/api/config/'),
      ]);
    } catch (error) {
      if (!_isTransientFetchError(error) || attempt >= maxRetries) {
        throw error;
      }
      attempt += 1;
      await _waitMs(250 * attempt);
    }
  }
}

function _extractApiErrorMessage(body, fallback = 'Request failed', rawText = '') {
  if (!body || typeof body !== 'object') return String(fallback || 'Request failed');

  const detail = body.detail;
  if (typeof detail === 'string' && detail.trim()) return detail;

  if (Array.isArray(detail) && detail.length) {
    const first = detail[0];
    if (typeof first === 'string' && first.trim()) return first;
    if (first && typeof first === 'object') {
      const msg = typeof first.msg === 'string' ? first.msg : null;
      const loc = Array.isArray(first.loc) ? first.loc.join('.') : null;
      if (msg && loc) return `${loc}: ${msg}`;
      if (msg) return msg;
      try {
        return JSON.stringify(first);
      } catch {
        return String(fallback || 'Request failed');
      }
    }
  }

  if (detail && typeof detail === 'object') {
    const msg = typeof detail.message === 'string' ? detail.message : null;
    if (msg) return msg;
    try {
      return JSON.stringify(detail);
    } catch {
      return String(fallback || 'Request failed');
    }
  }

  const trimmedText = String(rawText || '').replace(/\s+/g, ' ').trim();
  if (trimmedText) {
    const noTags = trimmedText.replace(/<[^>]+>/g, ' ').replace(/\s+/g, ' ').trim();
    if (noTags) return `${String(fallback || 'Request failed')}: ${noTags.slice(0, 220)}`;
  }

  return String(fallback || 'Request failed');
}

function status(msg, type = 'info') {
  const el = document.getElementById('run-status');
  el.textContent = msg;
  el.className = 'status ' + type;
}

function clearStatus() {
  const el = document.getElementById('run-status');
  if (!el) return;
  el.textContent = '';
  el.className = 'status';
}

function ensureRunProgressUi() {
  let box = document.getElementById('run-progress');
  let fill = document.getElementById('run-progress-fill');
  let label = document.getElementById('run-progress-pct');
  if (box && fill && label) return { box, fill, label };

  const statusEl = document.getElementById('run-status');
  if (!statusEl || !statusEl.parentElement) return null;

  box = document.createElement('div');
  box.id = 'run-progress';
  box.className = 'run-progress';
  box.setAttribute('aria-live', 'polite');
  box.style.display = 'none';

  label = document.createElement('div');
  label.id = 'run-progress-pct';
  label.className = 'run-progress-pct';
  label.textContent = '0%';

  const track = document.createElement('div');
  track.className = 'run-progress-track';

  fill = document.createElement('div');
  fill.id = 'run-progress-fill';
  fill.className = 'run-progress-fill';
  fill.style.width = '0%';

  track.appendChild(fill);
  box.appendChild(label);
  box.appendChild(track);
  statusEl.parentElement.insertBefore(box, statusEl);

  return { box, fill, label };
}

function setRunProgress(pct) {
  const refs = ensureRunProgressUi();
  if (!refs) return;
  const { box, fill, label } = refs;
  const clamped = Math.max(0, Math.min(100, Math.round(Number(pct) || 0)));
  box.style.display = 'block';
  fill.style.width = `${clamped}%`;
  label.textContent = `${clamped}%`;
}

function hideRunProgress() {
  const refs = ensureRunProgressUi();
  const box = refs?.box;
  if (!box) return;
  box.style.display = 'none';
}

function fmt(v, digits = 2) {
  return v != null ? Number(v).toFixed(digits) : '—';
}

function fmtCelsiusFromKelvin(v, digits = 2) {
  if (v == null) return '—';
  const n = Number(v);
  if (!Number.isFinite(n)) return '—';
  return (n - 273.15).toFixed(digits);
}

