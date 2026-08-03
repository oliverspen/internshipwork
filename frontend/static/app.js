// Helpers

async function api(path, opts = {}) {
  const res = await fetch(path, opts);
  if (!res.ok) {
    const body = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(_extractApiErrorMessage(body, res.statusText));
  }
  return res.json();
}

function _extractApiErrorMessage(body, fallback = 'Request failed') {
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

// Load maps

async function loadMaps() {
  try {
    const maps = await api('/api/maps/');
    const sel = document.getElementById('map-sel');
    const previousSelection = sel.value;

    sel.innerHTML = maps.length
      ? maps.map(m => `<option value="${m.name}">${m.name}</option>`).join('')
      : '<option value="">No maps saved</option>';

    if (maps.length) {
      if (previousSelection && maps.some(m => m.name === previousSelection)) {
        sel.value = previousSelection;
      }
      await previewSelectedMap();
    } else {
      showMapPreviewMessage('No saved maps yet. Create one to preview it here.');
    }
  } catch {
    showMapPreviewMessage('Could not load saved maps.');
  }
}

function _plantLabelByIndex(plantInputs, plantIndex) {
  const idx = Number(plantIndex);
  if (!Number.isFinite(idx) || idx < 0) return `Plant ${plantIndex}`;
  const plant = Array.isArray(plantInputs) ? plantInputs[idx] : null;
  const configuredName = String(plant?.name || '').trim();
  return configuredName || `Plant ${idx + 1}`;
}

let _currentPlantInputs = [];

function _displaySourceName(row, plantInputs = _currentPlantInputs) {
  const srcType = String(row?.source_type || '').trim();
  const srcName = row?.source_name ?? row?.merge_name;
  if (srcType !== 'plant') return srcName ?? '—';
  return _plantLabelByIndex(plantInputs, srcName);
}

function _normalizePhase(rawPhase) {
  return String(rawPhase || '').trim().toLowerCase();
}

function _validateSinglePhasePlants(plantInputs, plantIndexes = null) {
  const indexes = Array.isArray(plantIndexes)
    ? plantIndexes
    : (plantInputs || []).map((_, idx) => idx);

  const usedPhases = new Set();
  const usedPlants = [];

  indexes.forEach(idx => {
    const plant = Array.isArray(plantInputs) ? plantInputs[Number(idx)] : null;
    if (!plant) return;
    const phase = _normalizePhase(plant.stream_phase);
    if (!phase) return;
    usedPhases.add(phase);
    usedPlants.push(`${plant.name || `Plant ${Number(idx) + 1}`} (${phase})`);
  });

  if (usedPhases.size <= 1) return { ok: true };
  return {
    ok: false,
    message: `Only single-phase systems are allowed. Mixed phases detected: ${usedPlants.join(', ')}`,
  };
}

function _extractPlantIndexesFromMap(mapData, fallbackPlantCount = 0) {
  const defs = Array.isArray(mapData?.merge_definitions) ? mapData.merge_definitions : [];
  const indexes = new Set();

  defs.forEach(def => {
    (def?.sources || []).forEach(source => {
      const srcType = Array.isArray(source) ? source[0] : null;
      const srcValue = Array.isArray(source) ? source[1] : null;
      if (srcType !== 'plant') return;
      const idx = Number(srcValue);
      if (Number.isFinite(idx) && idx >= 0) indexes.add(idx);
    });
  });

  // If a map has no merge definitions, treat all plants as participating.
  if (!indexes.size && Number.isFinite(fallbackPlantCount) && fallbackPlantCount > 0) {
    for (let i = 0; i < fallbackPlantCount; i += 1) indexes.add(i);
  }

  return Array.from(indexes).sort((a, b) => a - b);
}

function renderMapVariablesPopup(mapName, mapData, plantInputs = []) {
  const content = document.getElementById('map-vars-content');
  const defs = Array.isArray(mapData?.merge_definitions) ? mapData.merge_definitions : [];
  const pipeInputs = mapData?.merge_pipe_inputs || {};
  const storageName = String(mapData?.storage_name || 'Storage').trim() || 'Storage';

  const mergeDefsHtml = defs.length
    ? `<ul class="map-vars-list">${defs.map(def => {
      const sources = (def.sources || [])
        .map(([srcType, srcVal]) => srcType === 'plant' ? `plant:${_plantLabelByIndex(plantInputs, srcVal)}` : `merge:${srcVal}`)
        .join(', ');
      return `<li><strong>${_esc(def.merge_name)}</strong> ← ${_esc(sources)}</li>`;
    }).join('')}</ul>`
    : '<div class="empty" style="padding:.5rem 0">No merge definitions in this map.</div>';

  const mergeVars = Object.entries(pipeInputs);
  const mergeVarsHtml = mergeVars.length
    ? `<ul class="map-vars-list">${mergeVars.map(([name, val]) => {
      const length = val?.pipelength ?? '—';
      const diameter = val?.pipediameter ?? '—';
      return `<li><strong>${_esc(name)}</strong>: length=${_esc(length)}, diameter=${_esc(diameter)}</li>`;
    }).join('')}</ul>`
    : '<div class="empty" style="padding:.5rem 0">No merge pipe inputs in this map.</div>';

  content.innerHTML = `
    <div class="map-vars-title">Map: ${_esc(mapName)}</div>
    <div class="map-vars-section">
      <h3>Storage</h3>
      <ul class="map-vars-list"><li><strong>Name</strong>: ${_esc(storageName)}</li></ul>
    </div>
    <div class="map-vars-section">
      <h3>Merge Definitions</h3>
      ${mergeDefsHtml}
    </div>
    <div class="map-vars-section">
      <h3>Merge Pipe Inputs</h3>
      ${mergeVarsHtml}
    </div>
  `;
}

async function onMapSelectionChange() {
  const mapName = document.getElementById('map-sel').value;
  if (!mapName) {
    showMapPreviewMessage('Select a pipeline map to preview it here.');
    return;
  }

  try {
    const [mapData, cfg] = await Promise.all([
      api(`/api/maps/${encodeURIComponent(mapName)}`),
      api('/api/config/'),
    ]);
    const plantInputs = Array.isArray(cfg?.plant_inputs) ? cfg.plant_inputs : [];
    _currentPlantInputs = plantInputs;
    renderMapPreview(mapName, mapData, plantInputs, null, 'Previewing saved map', { interactive: true });
    renderMapVariablesPopup(mapName, mapData, plantInputs);
    openModal('map-vars-modal');
  } catch (e) {
    showMapPreviewMessage(`Could not load map preview: ${e.message}`);
  }
}

// Load recent sessions

async function loadSessions() {
  const list = document.getElementById('results-links-list');
  if (!list) return;
  try {
    const selectedModel = document.getElementById('model-sel')?.value || 'tocomo';
    const sessions = await api(`/api/results/${selectedModel}`).catch(() => []);
    const modelLabelById = {
      tocomo: 'TOCOMO',
      phpitz: 'PH_PITZ Reactive',
      tocomo_dynamic: 'TOCOMO Dynamic',
      phpitz_dynamic: 'PH_PITZ Dynamic',
    };

    const sortedSessions = [...sessions]
      .sort((a, b) => String(b.session_id || '').localeCompare(String(a.session_id || '')));

    list.innerHTML = sortedSessions.slice(0, 12).map(s => `
        <div class="results-link-item">
          <div class="results-link-title">${_esc((s.pipeline_map_name || '').trim() || s.session_id)}</div>
          <div class="results-link-id">model: ${_esc(modelLabelById[String(s.model)] || String(s.model || 'unknown'))}</div>
          <div class="results-link-actions">
            ${s.summary_excel_url
              ? `<a class="btn btn-sm link" href="${s.summary_excel_url}" target="_blank">Excel</a>`
              : ''}
            ${Array.isArray(s.graph_urls) && s.graph_urls.length
              ? `<a class="btn btn-sm link" href="${s.graph_urls[0]}" target="_blank">Graph</a>`
              : ''}
            ${s.html_url
              ? `<a class="btn btn-sm link" href="${s.html_url}" download>Download Interactive Map</a>`
              : ''}
          </div>
        </div>`).join('')
      || '<div class="empty">No saved results yet.</div>';
  } catch {
    list.innerHTML = '<div class="empty">Could not load saved results.</div>';
  }
}

// Run

async function runSimulation() {
  const model = document.getElementById('model-sel').value;
  const mapName = document.getElementById('map-sel').value;
  if (!mapName) { status('Select a pipeline map first.', 'error'); return; }

  try {
    const [mapData, cfg] = await Promise.all([
      api(`/api/maps/${encodeURIComponent(mapName)}`),
      api('/api/config/'),
    ]);
    const plantInputs = Array.isArray(cfg?.plant_inputs) ? cfg.plant_inputs : [];
    const mapPlantIndexes = _extractPlantIndexesFromMap(mapData, plantInputs.length);
    const phaseCheck = _validateSinglePhasePlants(plantInputs, mapPlantIndexes);
    if (!phaseCheck.ok) {
      alert(phaseCheck.message);
      status('Simulation blocked: mixed-phase system detected.', 'error');
      return;
    }
  } catch (e) {
    status(`Could not validate map phases before run: ${e.message}`, 'error');
    return;
  }

  await _run(model, mapName);
}

function _isDynamicModel(model) {
  return model === 'tocomo_dynamic' || model === 'phpitz_dynamic';
}

const _TOCOMO_INLET_SPECIES = ['O2', 'H2O', 'H2S', 'SO2', 'NO2'];
const _PHPITZ_BASE_INLET_SPECIES = ['O2', 'H2O', 'H2S', 'SO2', 'NO2'];
const _PHPITZ_SUGGESTED_EXTRA_SPECIES = [
  'NO',
  'N2',
  'H2SO4',
  'HNO3',
  'S8',
  'NH3',
  'N2O',
  'N2O4',
  'NH4HSO4',
  'HCHO',
  'CH3CHO',
  'CH3COCH3',
  'HCOOH',
  'CH3COOH',
];

function _selectedModelId() {
  return String(document.getElementById('model-sel')?.value || 'tocomo').trim();
}

function _isTocomoModelId(modelId) {
  return modelId === 'tocomo' || modelId === 'tocomo_dynamic';
}

function _isPhpitzModelId(modelId) {
  return modelId === 'phpitz' || modelId === 'phpitz_dynamic';
}

function _normalizeSpeciesToken(raw) {
  const cleaned = String(raw || '').trim();
  if (!cleaned) return '';
  return cleaned.replace(/\s+/g, '').toUpperCase();
}

function _getDynamicExtraSpecies() {
  const base = new Set(_PHPITZ_BASE_INLET_SPECIES);
  const extras = new Set();
  (_dynamicPlantInputs || []).forEach(plant => {
    const inlet = plant?.inlet_conc;
    if (!inlet || typeof inlet !== 'object') return;
    Object.keys(inlet).forEach(species => {
      const normalized = _normalizeSpeciesToken(species);
      if (!normalized || base.has(normalized)) return;
      extras.add(normalized);
    });
  });
  return Array.from(extras).sort();
}

function _getDynamicVarOptions() {
  const modelId = _selectedModelId();
  const inletSpecies = _isTocomoModelId(modelId)
    ? _TOCOMO_INLET_SPECIES
    : [..._PHPITZ_BASE_INLET_SPECIES, ..._getDynamicExtraSpecies()];

  return [
    { value: 'flowrate', label: 'Flowrate (kg/hr)' },
    { value: 'temperature_celsius', label: 'Temperature (C)' },
    ...inletSpecies.map(species => ({ value: `inlet:${species}`, label: `Inlet ${species}` })),
  ];
}

let _dynamicChangeRows = [];
let _dynamicPlantNames = [];
let _dynamicPlantInputs = [];

function _dynamicVarOptionsHtml(selected) {
  return _getDynamicVarOptions()
    .map(opt => `<option value="${_esc(opt.value)}" ${opt.value === selected ? 'selected' : ''}>${_esc(opt.label)}</option>`)
    .join('');
}

function updateDynamicChangeSummary() {
  const summary = document.getElementById('dynamic-change-summary');
  if (!summary) return;
  const count = _dynamicChangeRows.length;
  summary.textContent = count ? `${count} change${count === 1 ? '' : 's'} configured` : 'No dynamic changes configured';
}

function addDynamicChangeForPlant(plantName, variable = 'flowrate') {
  if (!plantName) return;
  _dynamicChangeRows.push({
    plant_name: plantName,
    variable,
    initial_value: '',
    day: 0,
    value: '',
  });
  renderDynamicChangesEditor();
}

function addDynamicChangeForPlantIndex(plantIndex, variable = 'flowrate') {
  const idx = Number(plantIndex);
  if (!Number.isFinite(idx) || idx < 0 || idx >= _dynamicPlantNames.length) return;
  addDynamicChangeForPlant(_dynamicPlantNames[idx], variable);
}

function clearDynamicChangeRows() {
  _dynamicChangeRows = [];
  renderDynamicChangesEditor();
}

function removeDynamicChangeRow(index) {
  _dynamicChangeRows.splice(index, 1);
  renderDynamicChangesEditor();
}

function setDynamicChangeRow(index, field, value) {
  if (!_dynamicChangeRows[index]) return;
  _dynamicChangeRows[index][field] = value;
}

function renderDynamicChangesEditor() {
  const host = document.getElementById('dynamic-vars-rows');
  if (!host) return;

  const allowedVars = new Set(_getDynamicVarOptions().map(opt => opt.value));
  _dynamicChangeRows = _dynamicChangeRows.map(row => (
    allowedVars.has(row.variable)
      ? ({ ...row, initial_value: row.initial_value ?? '' })
      : { ...row, variable: 'flowrate', initial_value: row.initial_value ?? '', value: row.value }
  ));

  if (!_dynamicPlantNames.length) {
    host.innerHTML = '<div class="empty" style="padding:.65rem 0">No plants are available in current configuration.</div>';
    updateDynamicChangeSummary();
    return;
  }

  host.innerHTML = _dynamicPlantNames.map((plantName, plantIndex) => {
    const escapedPlant = _esc(plantName);
    const rowsForPlant = _dynamicChangeRows
      .map((row, index) => ({ row, index }))
      .filter(item => String(item.row.plant_name || '').trim() === plantName);

    const rowsHtml = rowsForPlant.length
      ? rowsForPlant.map(({ row, index }) => `
          <div class="field-row" style="margin:.35rem 0;padding:.45rem;border:1px solid #e2e8f0;border-radius:8px;background:#fff;">
            <label><span>Variable</span>
              <select onchange="setDynamicChangeRow(${index}, 'variable', this.value); renderDynamicChangesEditor();">${_dynamicVarOptionsHtml(row.variable)}</select>
            </label>
            <label><span>Initial value</span>
              <input type="number" step="any" value="${_esc(row.initial_value ?? '')}" oninput="setDynamicChangeRow(${index}, 'initial_value', this.value)">
            </label>
            <label><span>Day</span>
              <input type="number" step="any" min="0" value="${_esc(row.day)}" oninput="setDynamicChangeRow(${index}, 'day', this.value)">
            </label>
            <label><span>New value</span>
              <input type="number" step="any" value="${_esc(row.value)}" oninput="setDynamicChangeRow(${index}, 'value', this.value)">
            </label>
            <button class="btn btn-sm" type="button" style="background:#fff5f5;color:#c53030" onclick="removeDynamicChangeRow(${index})">Remove</button>
          </div>
        `).join('')
      : '<div class="empty" style="padding:.5rem 0">No variable changes added for this plant yet.</div>';

    return `
      <div style="margin:.6rem 0;padding:.55rem;border:1px solid #cbd5e0;border-radius:10px;background:#f7fafc;">
        <div style="font-weight:600;color:#2d3748;margin-bottom:.45rem;">${escapedPlant}</div>
        ${rowsHtml}
        <div style="display:flex;gap:.45rem;flex-wrap:wrap;">
          <button class="btn btn-sm" type="button" onclick="addDynamicChangeForPlantIndex(${plantIndex})">&#43; Add a variable change</button>
          <button class="btn btn-sm" type="button" onclick="loadDynamicInitialValuesForPlantIndex(${plantIndex})">Load From Static Variables</button>
        </div>
      </div>
    `;
  }).join('');
  updateDynamicChangeSummary();
}

function _buildDynamicProfilePayload() {
  if (!_dynamicChangeRows.length) return null;
  const profile = { plant_profiles: {} };

  const appendPoint = (plantProfile, variable, day, value) => {
    if (variable.startsWith('inlet:')) {
      const species = variable.split(':')[1];
      if (!species) return;
      if (!plantProfile.inlet_conc) plantProfile.inlet_conc = {};
      if (!Array.isArray(plantProfile.inlet_conc[species])) plantProfile.inlet_conc[species] = [];
      plantProfile.inlet_conc[species].push([day, value]);
      return;
    }

    if (!Array.isArray(plantProfile[variable])) plantProfile[variable] = [];
    plantProfile[variable].push([day, value]);
  };

  _dynamicChangeRows.forEach(row => {
    const plantName = String(row.plant_name || '').trim();
    const variable = String(row.variable || '').trim();
    if (!plantName || !variable) return;

    if (!profile.plant_profiles[plantName]) profile.plant_profiles[plantName] = {};
    const plantProfile = profile.plant_profiles[plantName];

    const initialValue = Number(row.initial_value);
    if (Number.isFinite(initialValue)) {
      appendPoint(plantProfile, variable, 0, initialValue);
    }

    const day = Number(row.day);
    if (!Number.isFinite(day) || day < 0) return;

    const numericValue = Number(row.value);
    if (!Number.isFinite(numericValue)) return;
    appendPoint(plantProfile, variable, day, numericValue);
  });

  Object.values(profile.plant_profiles).forEach(plantProfile => {
    ['flowrate', 'temperature_celsius'].forEach(key => {
      if (Array.isArray(plantProfile[key])) {
        plantProfile[key].sort((a, b) => Number(a[0]) - Number(b[0]));
      }
    });
    if (plantProfile.inlet_conc) {
      Object.values(plantProfile.inlet_conc).forEach(points => {
        if (Array.isArray(points)) points.sort((a, b) => Number(a[0]) - Number(b[0]));
      });
    }
  });

  if (!Object.keys(profile.plant_profiles).length) return null;
  return profile;
}

function _lookupStaticValue(plantName, variable) {
  const plant = _dynamicPlantInputs.find(p => String(p?.name || '').trim() === plantName);
  if (!plant) return '';

  if (variable === 'flowrate') {
    const value = Number(plant.flowrate);
    return Number.isFinite(value) ? value : '';
  }

  if (variable === 'temperature_celsius') {
    const value = Number(plant.temperature_celsius);
    return Number.isFinite(value) ? value : '';
  }

  if (variable.startsWith('inlet:')) {
    const species = variable.split(':')[1];
    if (!species) return '';
    const value = Number((plant.inlet_conc || {})[species]);
    return Number.isFinite(value) ? value : '';
  }

  return '';
}

function loadDynamicInitialValuesFromConfig() {
  if (!_dynamicChangeRows.length) return;
  _dynamicChangeRows = _dynamicChangeRows.map(row => ({
    ...row,
    initial_value: _lookupStaticValue(String(row.plant_name || '').trim(), String(row.variable || '').trim()),
  }));
  renderDynamicChangesEditor();
}

function loadDynamicInitialValuesForPlantIndex(plantIndex) {
  const idx = Number(plantIndex);
  if (!Number.isFinite(idx) || idx < 0 || idx >= _dynamicPlantNames.length) return;
  const plantName = _dynamicPlantNames[idx];
  _dynamicChangeRows = _dynamicChangeRows.map(row => {
    if (String(row.plant_name || '').trim() !== plantName) return row;
    return {
      ...row,
      initial_value: _lookupStaticValue(plantName, String(row.variable || '').trim()),
    };
  });
  renderDynamicChangesEditor();
}

async function openDynamicChangesEditor() {
  try {
    const cfg = await api('/api/config/');
    _dynamicPlantInputs = Array.isArray(cfg?.plant_inputs) ? cfg.plant_inputs : [];
    _dynamicPlantNames = (cfg?.plant_inputs || []).map((p, idx) => String(p?.name || `Plant ${idx + 1}`));
    const allowedPlants = new Set(_dynamicPlantNames);
    _dynamicChangeRows = _dynamicChangeRows.filter(row => allowedPlants.has(String(row.plant_name || '')));
    renderDynamicChangesEditor();
    openModal('dynamic-vars-modal');
  } catch (e) {
    alert(`Could not load plants for dynamic changes: ${e.message}`);
  }
}

function saveDynamicChanges() {
  renderDynamicChangesEditor();
  closeModal('dynamic-vars-modal');
}

function updateDynamicRunSettingsVisibility() {
  const model = document.getElementById('model-sel')?.value;
  const box = document.getElementById('dynamic-run-settings');
  if (!box) return;
  box.style.display = _isDynamicModel(model) ? 'block' : 'none';
}

async function quickRun(mapName) {
  document.getElementById('map-sel').value = mapName;
  await _run(document.getElementById('model-sel').value, mapName);
}

async function _run(model, mapName) {
  const btn = document.getElementById('run-btn');
  btn.disabled = true;
  btn.innerHTML = '<span class="spinner"></span> Starting…';
  clearStatus();
  setRunProgress(0);

  try {
    const body = { map_name: mapName };
    if (_isDynamicModel(model)) {
      const dtInput = Number(document.getElementById('dynamic-dt-days')?.value);
      const durationInput = Number(document.getElementById('dynamic-duration-days')?.value);
      if (!Number.isFinite(dtInput) || dtInput <= 0) {
        throw new Error('Time step (days) must be a positive number.');
      }
      if (!Number.isFinite(durationInput) || durationInput <= 0) {
        throw new Error('Total duration (days) must be a positive number.');
      }
      body.dt_days = dtInput;
      body.duration_days = durationInput;
      const dynamicProfile = _buildDynamicProfilePayload();
      if (dynamicProfile) body.dynamic_profile = dynamicProfile;
    }

    // POST returns immediately with a job_id.
    const job = await api(`/api/simulate/${model}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });

    btn.innerHTML = '<span class="spinner"></span> Running…';
    setRunProgress(0);

    // Poll every 2 s until the job finishes.
    const result = await pollJob(job.job_id, (runningJob) => {
      const pct = Number.isFinite(Number(runningJob?.progress_pct)) ? Number(runningJob.progress_pct) : 0;
      setRunProgress(pct);
    });

    const isDynamicModel = _isDynamicModel(model);
    if (isDynamicModel) {
      renderDynamicGraphs(result.graph_urls || [], mapName);
      hideResultsSummary();
    } else {
      const [mapData, cfg] = await Promise.all([
        api(`/api/maps/${encodeURIComponent(mapName)}`),
        api('/api/config/'),
      ]);
      const plantInputs = Array.isArray(cfg?.plant_inputs) ? cfg.plant_inputs : [];
      _currentPlantInputs = plantInputs;
      renderMapPreview(
        mapName,
        mapData,
        plantInputs,
        result.results || [],
        'Simulation result map',
        { interactive: true },
      );
      setMapPanelTitle('Interactive Pipeline Map');
      showTable(result.results);
    }

    const statusEl = document.getElementById('run-status');
    statusEl.className = 'status success';
    setRunProgress(100);
    const completionTextByModel = {
      tocomo: 'TOCOMO model complete',
      phpitz: 'PH_PITZ Reactive model complete',
      tocomo_dynamic: 'TOCOMO Dynamic model complete',
      phpitz_dynamic: 'PH_PITZ Dynamic model complete',
    };
    const completionText = completionTextByModel[model] || `${model} model complete`;
    statusEl.textContent = completionText;

    loadSessions();
  } catch (e) {
    status('Error: ' + e.message, 'error');
  } finally {
    btn.disabled = false;
    btn.innerHTML = '▶ Run';
  }
}

async function pollJob(jobId, onProgress = null) {
  while (true) {
    await new Promise(r => setTimeout(r, 2000));
    const job = await api(`/api/simulate/jobs/${jobId}`);
    if (job.status === 'running' && typeof onProgress === 'function') onProgress(job);
    if (job.status === 'done') return job;
    if (job.status === 'error') throw new Error(job.error || 'Simulation failed');
    // status === 'running' -> keep polling
  }
}

// Display

function showMap(url) {
  document.getElementById('map-frame').src = url;
  document.getElementById('map-frame').style.display = 'block';
  document.getElementById('map-placeholder').style.display = 'none';
}

function setMapPanelTitle(title) {
  const titleEl = document.getElementById('map-panel-title');
  if (!titleEl) return;
  titleEl.textContent = title;
}

function _graphLabelFromUrl(url, index) {
  const fallback = `Graph ${index + 1}`;
  if (!url) return fallback;
  const parts = String(url).split('/');
  const fileName = parts[parts.length - 1] || '';
  if (!fileName) return fallback;
  const base = fileName.replace(/\.png$/i, '').replace(/[_-]+/g, ' ').trim();
  return base ? base.replace(/\b\w/g, c => c.toUpperCase()) : fallback;
}

function renderDynamicGraphs(graphUrls, mapName) {
  const uniqueUrls = Array.isArray(graphUrls)
    ? Array.from(new Set(graphUrls.filter(Boolean).map(String)))
    : [];

  const placeholder = document.getElementById('map-placeholder');
  const frame = document.getElementById('map-frame');
  frame.style.display = 'none';
  frame.src = 'about:blank';

  if (!uniqueUrls.length) {
    setMapPanelTitle('Dynamic Graphs');
    showMapPreviewMessage('Dynamic run completed, but no graph images were found for this session.');
    return;
  }

  const options = uniqueUrls
    .map((url, idx) => `<option value="${_esc(url)}">${_esc(_graphLabelFromUrl(url, idx))}</option>`)
    .join('');
  const initialUrl = uniqueUrls[0];

  setMapPanelTitle('Dynamic Graphs');
  placeholder.className = '';
  placeholder.innerHTML = `
    <div class="map-preview-wrap dynamic-graphs-wrap">
      <div class="dynamic-graphs-header">
        <div class="map-preview-title">Graphs for <strong>${_esc(mapName)}</strong></div>
        <div class="dynamic-graphs-controls">
          <label for="dynamic-graph-select">Graph</label>
          <select id="dynamic-graph-select" onchange="switchDynamicGraph()">${options}</select>
          <a id="dynamic-graph-open" class="btn btn-sm link" href="${_esc(initialUrl)}" target="_blank">Open full size</a>
        </div>
      </div>
      <div class="dynamic-graph-stage">
        <img id="dynamic-graph-image" class="dynamic-graph-image" src="${_esc(initialUrl)}" alt="Dynamic simulation graph">
      </div>
    </div>
  `;
  placeholder.style.display = 'block';
}

function switchDynamicGraph() {
  const select = document.getElementById('dynamic-graph-select');
  const img = document.getElementById('dynamic-graph-image');
  const link = document.getElementById('dynamic-graph-open');
  const selectedUrl = String(select?.value || '');
  if (!selectedUrl || !img || !link) return;
  img.src = selectedUrl;
  link.href = selectedUrl;
}

function hideResultsSummary() {
  const card = document.getElementById('results-card');
  const controls = document.getElementById('results-controls');
  const toggleBtn = document.getElementById('results-filter-toggle');
  const thead = document.getElementById('results-thead');
  const tbody = document.getElementById('results-tbody');
  if (thead) thead.innerHTML = '';
  if (tbody) tbody.innerHTML = '';
  if (controls) {
    controls.style.display = 'none';
    controls.classList.remove('open');
  }
  if (toggleBtn) toggleBtn.setAttribute('aria-expanded', 'false');
  if (card) card.style.display = 'none';
}

function showMapPreviewMessage(message) {
  const placeholder = document.getElementById('map-placeholder');
  const frame = document.getElementById('map-frame');
  frame.style.display = 'none';
  frame.src = 'about:blank';
  placeholder.className = 'empty';
  placeholder.textContent = message;
  placeholder.style.display = 'block';
}

function _esc(text) {
  return String(text)
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#39;');
}

function _formatTooltipRows(title, values) {
  const lines = [title];
  Object.entries(values || {}).forEach(([k, v]) => {
    const num = Number(v);
    if (!Number.isFinite(num) || num === 0) return;
    lines.push(`${k}: ${num.toFixed(1)}`);
  });
  return lines.join('\n');
}

function _escAttrMultiline(text) {
  return _esc(String(text ?? '')).replaceAll('\n', '&#10;');
}

const _savedMapLastLayoutByMap = new Map();

function _topoSortNodes(nodeIds, edges) {
  const incoming = new Map(nodeIds.map(id => [id, 0]));
  const outgoing = new Map(nodeIds.map(id => [id, []]));

  edges.forEach(([src, dst]) => {
    if (!incoming.has(src) || !incoming.has(dst)) return;
    incoming.set(dst, incoming.get(dst) + 1);
    outgoing.get(src).push(dst);
  });

  const queue = nodeIds.filter(id => incoming.get(id) === 0);
  const order = [];
  while (queue.length) {
    const id = queue.shift();
    order.push(id);
    (outgoing.get(id) || []).forEach(next => {
      incoming.set(next, incoming.get(next) - 1);
      if (incoming.get(next) === 0) queue.push(next);
    });
  }

  if (order.length < nodeIds.length) {
    nodeIds.forEach(id => {
      if (!order.includes(id)) order.push(id);
    });
  }
  return order;
}

function _computeOverlapAwareLayout(nodes, edges, previousPositions = null) {
  const nodeById = new Map(nodes.map(n => [n.id, n]));
  const nodeIds = nodes.map(n => n.id);
  if (!nodeIds.length) return {};

  const predsByNode = new Map(nodeIds.map(id => [id, []]));
  edges.forEach(([src, dst]) => {
    if (predsByNode.has(dst) && nodeById.has(src)) predsByNode.get(dst).push(src);
  });

  const order = _topoSortNodes(nodeIds, edges);

  const depth = {};
  order.forEach(id => {
    const preds = predsByNode.get(id) || [];
    depth[id] = preds.length ? Math.max(...preds.map(p => (depth[p] ?? 0) + 1)) : 0;
  });

  const grouped = {};
  nodeIds.forEach(id => {
    const d = depth[id] ?? 0;
    if (!grouped[d]) grouped[d] = [];
    grouped[d].push(id);
  });

  const typeRank = { plant: 0, merge: 1, storage: 2 };
  const baseRank = (id) => {
    const n = nodeById.get(id);
    const rank = typeRank[n?.type] ?? 3;
    if (n?.type === 'plant') {
      return [rank, Number(n?.plantIndex ?? Number.MAX_SAFE_INTEGER), String(n?.label || id)];
    }
    if (n?.type === 'merge') {
      return [rank, Number(n?.mergeOrder ?? Number.MAX_SAFE_INTEGER), String(n?.label || id)];
    }
    return [rank, Number.MAX_SAFE_INTEGER, String(n?.label || id)];
  };

  const compareRank = (ra, rb) => {
    for (let i = 0; i < Math.max(ra.length, rb.length); i += 1) {
      const av = ra[i];
      const bv = rb[i];
      if (av === bv) continue;
      if (typeof av === 'string' || typeof bv === 'string') return String(av).localeCompare(String(bv));
      return Number(av) - Number(bv);
    }
    return 0;
  };

  const levelNumbers = Object.keys(grouped).map(Number).sort((a, b) => a - b);
  levelNumbers.forEach(level => {
    const ids = grouped[level];
    ids.sort((a, b) => {
      if (previousPositions?.[a] && previousPositions?.[b]) {
        return previousPositions[b].y - previousPositions[a].y;
      }
      return compareRank(baseRank(a), baseRank(b));
    });
  });

  for (let i = 1; i < levelNumbers.length; i += 1) {
    const level = levelNumbers[i];
    const ids = grouped[level];
    const orderedBefore = levelNumbers.slice(0, i).flatMap(lv => grouped[lv] || []);
    const prevIndex = new Map(orderedBefore.map((id, idx) => [id, idx]));

    ids.sort((a, b) => {
      const apreds = predsByNode.get(a) || [];
      const bpreds = predsByNode.get(b) || [];
      const abar = apreds.length
        ? apreds.reduce((acc, p) => acc + (prevIndex.get(p) ?? orderedBefore.length + 999), 0) / apreds.length
        : Number.MAX_SAFE_INTEGER;
      const bbar = bpreds.length
        ? bpreds.reduce((acc, p) => acc + (prevIndex.get(p) ?? orderedBefore.length + 999), 0) / bpreds.length
        : Number.MAX_SAFE_INTEGER;
      if (abar !== bbar) return abar - bbar;
      return compareRank(baseRank(a), baseRank(b));
    });
  }

  const buildPositions = (horizontalGap, verticalGap) => {
    const p = {};
    levelNumbers.forEach(level => {
      const ids = grouped[level];
      const count = ids.length;
      const spread = verticalGap * (count - 1);
      const start = spread / 2;
      ids.forEach((id, idx) => {
        p[id] = {
          x: level * horizontalGap,
          y: count === 1 ? 0 : (start - idx * verticalGap),
        };
      });
    });
    return p;
  };

  const hasOverlap = p => {
    const ids = Object.keys(p);
    const xMin = 1.05;
    const yMin = 1.05;
    for (let i = 0; i < ids.length; i += 1) {
      const a = p[ids[i]];
      for (let j = i + 1; j < ids.length; j += 1) {
        const b = p[ids[j]];
        if (Math.abs(a.x - b.x) < xMin && Math.abs(a.y - b.y) < yMin) return true;
      }
    }
    return false;
  };

  let positions = buildPositions(1.0, 1.0);
  if (hasOverlap(positions)) positions = buildPositions(1.5, 1.35);
  return positions;
}

function _inflateRect(rect, pad) {
  return {
    left: rect.left - pad,
    right: rect.right + pad,
    top: rect.top - pad,
    bottom: rect.bottom + pad,
  };
}

function _pointInRect(point, rect) {
  return point.x >= rect.left && point.x <= rect.right && point.y >= rect.top && point.y <= rect.bottom;
}

function _segmentIntersectsRect(a, b, rect) {
  // Router emits orthogonal paths. Check horizontal/vertical segment collision.
  if (a.x === b.x) {
    const x = a.x;
    if (x < rect.left || x > rect.right) return false;
    const minY = Math.min(a.y, b.y);
    const maxY = Math.max(a.y, b.y);
    return maxY >= rect.top && minY <= rect.bottom;
  }
  if (a.y === b.y) {
    const y = a.y;
    if (y < rect.top || y > rect.bottom) return false;
    const minX = Math.min(a.x, b.x);
    const maxX = Math.max(a.x, b.x);
    return maxX >= rect.left && minX <= rect.right;
  }

  // Safety fallback for diagonal fallback segments.
  const minX = Math.min(a.x, b.x);
  const maxX = Math.max(a.x, b.x);
  const minY = Math.min(a.y, b.y);
  const maxY = Math.max(a.y, b.y);
  return !(maxX < rect.left || minX > rect.right || maxY < rect.top || minY > rect.bottom);
}

function _polylineIntersectsRect(points, rect) {
  for (let i = 0; i < points.length - 1; i += 1) {
    if (_segmentIntersectsRect(points[i], points[i + 1], rect)) return true;
  }
  return false;
}

function _simplifyOrthogonalPolyline(points) {
  if (points.length <= 2) return points;
  const out = [points[0]];
  for (let i = 1; i < points.length - 1; i += 1) {
    const a = out[out.length - 1];
    const b = points[i];
    const c = points[i + 1];
    const sameVertical = a.x === b.x && b.x === c.x;
    const sameHorizontal = a.y === b.y && b.y === c.y;
    if (sameVertical || sameHorizontal) continue;
    out.push(b);
  }
  out.push(points[points.length - 1]);
  return out;
}

function _gridRouteOrthogonal(start, end, obstacles, bounds, step = 10) {
  const pad = step * 2;
  const minX = Math.floor((Math.min(start.x, end.x, bounds.minX) - pad) / step) * step;
  const maxX = Math.ceil((Math.max(start.x, end.x, bounds.maxX) + pad) / step) * step;
  const minY = Math.floor((Math.min(start.y, end.y, bounds.minY) - pad) / step) * step;
  const maxY = Math.ceil((Math.max(start.y, end.y, bounds.maxY) + pad) / step) * step;

  const toCell = (p) => ({
    x: Math.round((p.x - minX) / step),
    y: Math.round((p.y - minY) / step),
  });
  const toPoint = (c) => ({ x: minX + c.x * step, y: minY + c.y * step });
  const key = (c) => `${c.x},${c.y}`;

  const startCell = toCell(start);
  const endCell = toCell(end);

  const isBlocked = (cell) => {
    const p = toPoint(cell);
    return obstacles.some(rect => _pointInRect(p, rect));
  };

  const h = (a, b) => Math.abs(a.x - b.x) + Math.abs(a.y - b.y);
  const open = [{ cell: startCell, f: h(startCell, endCell), g: 0 }];
  const cameFrom = new Map();
  const gScore = new Map([[key(startCell), 0]]);
  const closed = new Set();

  while (open.length) {
    open.sort((a, b) => a.f - b.f);
    const current = open.shift();
    const ck = key(current.cell);
    if (closed.has(ck)) continue;
    closed.add(ck);

    if (current.cell.x === endCell.x && current.cell.y === endCell.y) {
      const cells = [current.cell];
      let k = ck;
      while (cameFrom.has(k)) {
        const prev = cameFrom.get(k);
        cells.push(prev);
        k = key(prev);
      }
      cells.reverse();
      return cells.map(toPoint);
    }

    const neighbors = [
      { x: current.cell.x + 1, y: current.cell.y },
      { x: current.cell.x - 1, y: current.cell.y },
      { x: current.cell.x, y: current.cell.y + 1 },
      { x: current.cell.x, y: current.cell.y - 1 },
    ];

    neighbors.forEach(next => {
      const p = toPoint(next);
      if (p.x < minX || p.x > maxX || p.y < minY || p.y > maxY) return;
      if (isBlocked(next)) return;

      const nk = key(next);
      const tentativeG = current.g + 1;
      const prevG = gScore.get(nk);
      if (prevG != null && tentativeG >= prevG) return;

      cameFrom.set(nk, current.cell);
      gScore.set(nk, tentativeG);
      open.push({ cell: next, g: tentativeG, f: tentativeG + h(next, endCell) });
    });
  }

  return null;
}

function _buildOrthogonalEdgeRoute({
  sourceRect,
  targetRect,
  srcSlot,
  srcCount,
  dstSlot,
  dstCount,
  obstacleRects,
  bounds,
}) {
  const slotOffset = (slot, total, step) => (total <= 1 ? 0 : (slot - (total - 1) / 2) * step);
  const yStart = sourceRect.cy + slotOffset(srcSlot, srcCount, 10);
  const yEnd = targetRect.cy + slotOffset(dstSlot, dstCount, 12);

  const start = { x: sourceRect.right + 2, y: yStart };
  const end = { x: targetRect.left - 2, y: yEnd };

  const mainRoute = _gridRouteOrthogonal(start, end, obstacleRects, bounds, 10);
  if (mainRoute?.length) {
    const route = _simplifyOrthogonalPolyline([start, ...mainRoute, end]);
    if (!obstacleRects.some(rect => _polylineIntersectsRect(route, rect))) return route;
  }

  // Fallback corridor routing above or below all nodes.
  const yTop = bounds.minY - 24;
  const yBottom = bounds.maxY + 24;
  const topRoute = _simplifyOrthogonalPolyline([
    start,
    { x: start.x + 20, y: start.y },
    { x: start.x + 20, y: yTop },
    { x: end.x - 20, y: yTop },
    { x: end.x - 20, y: end.y },
    end,
  ]);
  if (!obstacleRects.some(rect => _polylineIntersectsRect(topRoute, rect))) return topRoute;

  const bottomRoute = _simplifyOrthogonalPolyline([
    start,
    { x: start.x + 20, y: start.y },
    { x: start.x + 20, y: yBottom },
    { x: end.x - 20, y: yBottom },
    { x: end.x - 20, y: end.y },
    end,
  ]);
  return bottomRoute;
}

function _polylineToPathD(points) {
  if (!points.length) return '';
  return points.map((p, idx) => `${idx === 0 ? 'M' : 'L'} ${p.x} ${p.y}`).join(' ');
}

function _buildClassicEdgePath({ sourceRect, targetRect, srcSlot, srcCount, dstSlot, dstCount }) {
  const slotOffset = (slot, total, step) => (total <= 1 ? 0 : (slot - (total - 1) / 2) * step);
  const startX = sourceRect.right + 2;
  const startY = sourceRect.cy + slotOffset(srcSlot, srcCount, 9);
  const endX = targetRect.left - 2;
  const endY = targetRect.cy + slotOffset(dstSlot, dstCount, 10);
  return `M ${startX} ${startY} L ${endX} ${endY}`;
}

let _mapPreviewPanX = 0;
let _mapPreviewPanY = 0;
let _mapPreviewZoom = 1;
let _mapPreviewGraphState = null;

function _renderEdgePathsFromState(state) {
  if (!state) return '';
  const { nodes, edges, positions, edgeTooltipBySourceId, nodeWidth, nodeHeight } = state;
  const halfW = nodeWidth / 2;
  const halfH = nodeHeight / 2;

  const outgoingByNode = new Map();
  const incomingByNode = new Map();
  edges.forEach(([src, dst], idx) => {
    if (!outgoingByNode.has(src)) outgoingByNode.set(src, []);
    if (!incomingByNode.has(dst)) incomingByNode.set(dst, []);
    outgoingByNode.get(src).push(idx);
    incomingByNode.get(dst).push(idx);
  });

  const nodeRects = new Map();
  Array.from(nodes.values()).forEach(node => {
    const p = positions[node.id];
    nodeRects.set(node.id, {
      left: p.x - halfW,
      right: p.x + halfW,
      top: p.y - halfH,
      bottom: p.y + halfH,
      cx: p.x,
      cy: p.y,
    });
  });

  return edges.map(([src, dst], edgeIdx) => {
    const sourceRect = nodeRects.get(src);
    const targetRect = nodeRects.get(dst);
    if (!sourceRect || !targetRect) return '';

    const srcEdges = outgoingByNode.get(src) || [edgeIdx];
    const dstEdges = incomingByNode.get(dst) || [edgeIdx];
    const srcSlot = srcEdges.indexOf(edgeIdx);
    const dstSlot = dstEdges.indexOf(edgeIdx);

    const pathD = _buildClassicEdgePath({
      sourceRect,
      targetRect,
      srcSlot,
      srcCount: srcEdges.length,
      dstSlot,
      dstCount: dstEdges.length,
    });

    const tip = edgeTooltipBySourceId.get(src);
    const encodedTip = tip ? _escAttrMultiline(tip) : '';
    return `
      <path d="${pathD}" fill="none" stroke="#4a5568" stroke-width="2" marker-end="url(#arrow)">${tip ? `<title>${_esc(tip)}</title>` : ''}</path>
      <path d="${pathD}" fill="none" stroke="transparent" stroke-width="14" data-tip="${encodedTip}"></path>
    `;
  }).join('');
}

function _renderInteractiveMapEdges() {
  if (!_mapPreviewGraphState) return;
  const edgesGroup = document.getElementById('map-preview-edges');
  if (!edgesGroup) return;
  edgesGroup.innerHTML = _renderEdgePathsFromState(_mapPreviewGraphState);
}

function _renderInteractiveMapNodesIntoDom() {
  if (!_mapPreviewGraphState) return;
  const nodesGroup = document.getElementById('map-preview-nodes');
  if (!nodesGroup) return;
  nodesGroup.innerHTML = _renderInteractiveMapNodes();
}

function _renderInteractiveMapNodes() {
  if (!_mapPreviewGraphState) return '';
  const { nodes, positions, nodeTooltipById, nodeWidth, nodeHeight } = _mapPreviewGraphState;
  const halfW = nodeWidth / 2;
  const halfH = nodeHeight / 2;
  return Array.from(nodes.values()).map(node => {
    const p = positions[node.id];
    const fill = node.type === 'plant' ? '#c6f6d5' : (node.type === 'storage' ? '#bee3f8' : '#feebc8');
    const stroke = node.type === 'plant' ? '#276749' : (node.type === 'storage' ? '#2c5282' : '#c05621');
    const tip = nodeTooltipById.get(node.id);
    const encodedTip = tip ? _escAttrMultiline(tip) : '';
    return `
      <g data-node-id="${_esc(node.id)}" transform="translate(${p.x} ${p.y})" style="cursor:move">
        <rect x="${-halfW}" y="${-halfH}" rx="8" ry="8" width="${nodeWidth}" height="${nodeHeight}" fill="${fill}" stroke="${stroke}" stroke-width="2" ${tip ? `data-tip="${encodedTip}"` : ''}>${tip ? `<title>${_esc(tip)}</title>` : ''}</rect>
        <text x="0" y="5" text-anchor="middle" font-size="12" fill="#2d3748" style="pointer-events:none">${_esc(node.label)}</text>
      </g>
    `;
  }).join('');
}

function _applyMapPreviewTransform() {
  const viewport = document.getElementById('map-preview-viewport');
  if (!viewport) return;
  viewport.setAttribute('transform', `translate(${_mapPreviewPanX} ${_mapPreviewPanY}) scale(${_mapPreviewZoom})`);
}

function resetMapPreviewView() {
  _mapPreviewPanX = 0;
  _mapPreviewPanY = 0;
  _mapPreviewZoom = 1;
  _applyMapPreviewTransform();
}

function resetMapPreviewNodes() {
  if (!_mapPreviewGraphState?.originalPositions) return;
  _mapPreviewGraphState.positions = Object.fromEntries(
    Object.entries(_mapPreviewGraphState.originalPositions).map(([id, p]) => [id, { x: p.x, y: p.y }]),
  );
  _renderInteractiveMapNodesIntoDom();
  _renderInteractiveMapEdges();
}

function enableMapPreviewInteractions() {
  const stage = document.getElementById('map-preview-stage');
  const svg = document.getElementById('map-preview-svg');
  const tooltip = document.getElementById('map-hover-tooltip');
  if (!stage || !svg || !tooltip) return;

  resetMapPreviewView();

  let dragging = false;
  let startClientX = 0;
  let startClientY = 0;
  let startPanX = 0;
  let startPanY = 0;
  let nodeDragging = null;

  svg.addEventListener('wheel', (event) => {
    event.preventDefault();
    const factor = event.deltaY < 0 ? 1.1 : 0.9;
    _mapPreviewZoom = Math.max(0.6, Math.min(3.0, _mapPreviewZoom * factor));
    _applyMapPreviewTransform();
  }, { passive: false });

  svg.addEventListener('mousedown', (event) => {
    if (event.button !== 0) return;

    const nodeGroup = event.target?.closest?.('[data-node-id]');
    if (nodeGroup) {
      const nodeId = nodeGroup.getAttribute('data-node-id');
      if (_mapPreviewGraphState?.positions?.[nodeId]) {
        nodeDragging = {
          nodeId,
          startClientX: event.clientX,
          startClientY: event.clientY,
          startX: _mapPreviewGraphState.positions[nodeId].x,
          startY: _mapPreviewGraphState.positions[nodeId].y,
        };
        svg.style.cursor = 'grabbing';
        event.preventDefault();
        return;
      }
    }

    dragging = true;
    startClientX = event.clientX;
    startClientY = event.clientY;
    startPanX = _mapPreviewPanX;
    startPanY = _mapPreviewPanY;
    svg.style.cursor = 'grabbing';
  });

  window.addEventListener('mousemove', (event) => {
    const hit = event.target?.closest?.('[data-tip]');
    if (hit && stage.contains(hit)) {
      const tip = hit.getAttribute('data-tip') || '';
      tooltip.textContent = tip;
      tooltip.style.display = 'block';
      const rect = stage.getBoundingClientRect();
      tooltip.style.left = `${Math.min(rect.width - 16, event.clientX - rect.left + 12)}px`;
      tooltip.style.top = `${Math.min(rect.height - 16, event.clientY - rect.top + 12)}px`;
    } else {
      tooltip.style.display = 'none';
    }

    if (nodeDragging) {
      const vb = svg.viewBox?.baseVal;
      if (!vb || !svg.clientWidth || !svg.clientHeight) return;
      const dx = event.clientX - nodeDragging.startClientX;
      const dy = event.clientY - nodeDragging.startClientY;
      const scaleX = vb.width / svg.clientWidth;
      const scaleY = vb.height / svg.clientHeight;
      const nx = nodeDragging.startX + (dx * scaleX) / _mapPreviewZoom;
      const ny = nodeDragging.startY + (dy * scaleY) / _mapPreviewZoom;

      _mapPreviewGraphState.positions[nodeDragging.nodeId] = { x: nx, y: ny };

      const nodeEl = svg.querySelector(`[data-node-id="${CSS.escape(nodeDragging.nodeId)}"]`);
      if (nodeEl) nodeEl.setAttribute('transform', `translate(${nx} ${ny})`);
      _renderInteractiveMapEdges();
      return;
    }

    if (!dragging) return;
    const vb = svg.viewBox?.baseVal;
    if (!vb || !svg.clientWidth || !svg.clientHeight) return;
    const dx = event.clientX - startClientX;
    const dy = event.clientY - startClientY;
    const scaleX = vb.width / svg.clientWidth;
    const scaleY = vb.height / svg.clientHeight;
    _mapPreviewPanX = startPanX + (dx * scaleX) / _mapPreviewZoom;
    _mapPreviewPanY = startPanY + (dy * scaleY) / _mapPreviewZoom;
    _applyMapPreviewTransform();
  });

  window.addEventListener('mouseup', () => {
    nodeDragging = null;
    dragging = false;
    svg.style.cursor = 'grab';
  });

  stage.addEventListener('mouseleave', () => {
    tooltip.style.display = 'none';
  });

  svg.style.cursor = 'grab';
}

function renderMapPreview(
  mapName,
  mapData,
  plantInputs = [],
  simulationRows = null,
  titlePrefix = 'Previewing saved map',
  options = {},
) {
  setMapPanelTitle('Interactive Pipeline Map');
  const interactive = Boolean(options?.interactive);
  const placeholder = document.getElementById('map-placeholder');
  const frame = document.getElementById('map-frame');
  frame.style.display = 'none';
  frame.src = 'about:blank';

  const defs = Array.isArray(mapData?.merge_definitions) ? mapData.merge_definitions : [];

  const nodes = new Map();
  const edges = [];
  const addNode = (id, label, type, meta = {}) => {
    if (!nodes.has(id)) {
      nodes.set(id, { id, label, type, ...meta });
      return;
    }
    Object.assign(nodes.get(id), meta);
  };

  defs.forEach((def, mergeIdx) => {
    const mergeId = `merge:${def.merge_name}`;
    addNode(mergeId, def.merge_name, 'merge', { mergeOrder: mergeIdx });
    (def.sources || []).forEach(src => {
      const [srcType, srcValue] = src;
      if (srcType === 'plant') {
        const id = `plant:${srcValue}`;
        addNode(id, _plantLabelByIndex(plantInputs, srcValue), 'plant', { plantIndex: Number(srcValue) });
        edges.push([id, mergeId]);
      } else {
        const id = `merge:${srcValue}`;
        addNode(id, String(srcValue), 'merge');
        edges.push([id, mergeId]);
      }
    });
  });

  const storageName = String(mapData?.storage_name || 'Storage').trim() || 'Storage';
  const storageId = `storage:${storageName}`;
  addNode(storageId, storageName, 'storage');

  const nodeTooltipById = new Map();
  const edgeTooltipBySourceId = new Map();
  if (Array.isArray(simulationRows)) {
    simulationRows.forEach(row => {
      const srcType = String(row?.source_type || '');
      const srcName = row?.source_name;
      let nodeId = null;
      if (srcType === 'plant') nodeId = `plant:${srcName}`;
      else if (srcType === 'merge') nodeId = `merge:${srcName}`;
      else if (srcType === 'storage') nodeId = `storage:${srcName}`;
      if (!nodeId) return;

      const metaLines = [
        `${srcType}: ${String(_displaySourceName(row, plantInputs))}`,
        `phase: ${row?.stream_phase ?? '—'}`,
        `temperature (°C): ${fmtCelsiusFromKelvin(row?.temperature_kelvin)}`,
        `flow (kg/hr): ${row?.total_massflow ?? '—'}`,
      ];
      const inLines = _formatTooltipRows('Inlet concentration', row?.tocomo_input || {});
      nodeTooltipById.set(nodeId, `${metaLines.join('\n')}\n\n${inLines}`);

      const edgeTooltip = _formatTooltipRows('Formation of corrosive contaminants', row?.final || {});
      if (edgeTooltip && edgeTooltip !== 'Formation of corrosive contaminants') {
        edgeTooltipBySourceId.set(nodeId, edgeTooltip);
      }
    });
  }

  // Connect storage from all terminal nodes (nodes with no outgoing edge),
  // so storage is always represented even in edge-case map definitions.
  const outgoing = new Set(edges.map(([src]) => src));
  Array.from(nodes.values())
    .filter(node => node.type !== 'storage' && !outgoing.has(node.id))
    .forEach(node => edges.push([node.id, storageId]));

  const previousLayout = _savedMapLastLayoutByMap.get(mapName) || null;
  const layoutUnits = _computeOverlapAwareLayout(
    Array.from(nodes.values()),
    edges,
    previousLayout,
  );
  _savedMapLastLayoutByMap.set(mapName, layoutUnits);

  const xs = Object.values(layoutUnits).map(p => p.x);
  const ys = Object.values(layoutUnits).map(p => p.y);
  const minX = xs.length ? Math.min(...xs) : 0;
  const maxX = xs.length ? Math.max(...xs) : 0;
  const maxAbsY = ys.length ? Math.max(...ys.map(y => Math.abs(y))) : 0;

  const xScale = 180;
  const yScale = 110;
  const xPad = 120;
  const yPad = 80;
  const width = Math.max(780, (maxX - minX) * xScale + xPad * 2 + 80);
  const height = Math.max(520, (maxAbsY * 2) * yScale + yPad * 2 + 80);
  const positions = {};

  Object.entries(layoutUnits).forEach(([id, p]) => {
    positions[id] = {
      x: xPad + (p.x - minX) * xScale,
      y: (height / 2) - p.y * yScale,
    };
  });

  _mapPreviewGraphState = {
    mapName,
    nodes,
    edges,
    positions,
    originalPositions: Object.fromEntries(Object.entries(positions).map(([id, p]) => [id, { x: p.x, y: p.y }])),
    nodeTooltipById,
    edgeTooltipBySourceId,
    nodeWidth: 76,
    nodeHeight: 40,
  };

  const edgeSvg = _renderEdgePathsFromState(_mapPreviewGraphState);
  const nodeSvg = _renderInteractiveMapNodes();

  placeholder.className = '';
  const svgContent = interactive
    ? `
      <div class="map-preview-controls">
        <button class="btn btn-sm" type="button" onclick="resetMapPreviewView()">Reset View</button>
        <button class="btn btn-sm" type="button" onclick="resetMapPreviewNodes()">Reset Nodes</button>
      </div>
      <div class="map-preview-stage" id="map-preview-stage">
        <svg class="map-preview-svg" id="map-preview-svg" viewBox="0 0 ${width} ${height}" role="img" aria-label="Pipeline map preview">
          <defs>
            <marker id="arrow" markerWidth="10" markerHeight="8" refX="9" refY="4" orient="auto" markerUnits="strokeWidth">
              <path d="M0,0 L10,4 L0,8 z" fill="#4a5568"></path>
            </marker>
          </defs>
          <g id="map-preview-viewport">
            <g id="map-preview-edges">${edgeSvg}</g>
            <g id="map-preview-nodes">${nodeSvg}</g>
          </g>
        </svg>
        <div class="map-hover-tooltip" id="map-hover-tooltip"></div>
      </div>
    `
    : `
      <svg class="map-preview-svg" viewBox="0 0 ${width} ${height}" role="img" aria-label="Pipeline map preview">
        <defs>
          <marker id="arrow" markerWidth="10" markerHeight="8" refX="9" refY="4" orient="auto" markerUnits="strokeWidth">
            <path d="M0,0 L10,4 L0,8 z" fill="#4a5568"></path>
          </marker>
        </defs>
        ${edgeSvg}
        ${nodeSvg}
      </svg>
    `;

  placeholder.innerHTML = `
    <div class="map-preview-wrap">
      <div class="map-preview-title">${_esc(titlePrefix)}: <strong>${_esc(mapName)}</strong></div>
      ${svgContent}
    </div>
  `;
  placeholder.style.display = 'block';
  if (interactive) enableMapPreviewInteractions();
}

async function previewSelectedMap() {
  const mapName = document.getElementById('map-sel').value;
  if (!mapName) {
    showMapPreviewMessage('Select a pipeline map to preview it here.');
    return;
  }
  try {
    const [mapData, cfg] = await Promise.all([
      api(`/api/maps/${encodeURIComponent(mapName)}`),
      api('/api/config/'),
    ]);
    const plantInputs = Array.isArray(cfg?.plant_inputs) ? cfg.plant_inputs : [];
    _currentPlantInputs = plantInputs;
    renderMapPreview(mapName, mapData, plantInputs, null, 'Previewing saved map', { interactive: true });
  } catch (e) {
    showMapPreviewMessage(`Could not load map preview: ${e.message}`);
  }
}

const _RESULT_COLUMN_DEFS = [
  {
    key: 'source_name',
    label: 'source name',
    defaultSelected: true,
    getter: (row) => _displaySourceName(row),
  },
  {
    key: 'source_type',
    label: 'source type',
    defaultSelected: true,
    render: (row) => {
      const type = row.source_type ?? (row.merge_name ? 'merge' : '—');
      return `<span class="tag tag-${_esc(type)}">${_esc(type)}</span>`;
    },
  },
  {
    key: 'stream_phase',
    label: 'stream phase',
    defaultSelected: true,
  },
  {
    key: 'total_massflow',
    label: 'massflow (kg/hr)',
    defaultSelected: true,
    getter: (row) => row.total_massflow ?? row.flow_kg_per_h ?? null,
  },
  {
    key: 'temperature_kelvin',
    label: 'temperature (C)',
    defaultSelected: true,
    getter: (row) => {
      if (row.temperature_kelvin != null) return fmtCelsiusFromKelvin(row.temperature_kelvin);
      if (row.temperature_celsius != null) return Number(row.temperature_celsius).toFixed(2);
      return '—';
    },
  },
  {
    key: 'density_kg_per_m3',
    label: 'density (kg/m3)',
    defaultSelected: false,
  },
];

const _RESULT_COLUMN_LABEL_ALIASES = {
  source_name: 'source name',
  source_type: 'source type',
  stream_phase: 'stream phase',
  total_massflow: 'massflow (kg/hr)',
  flow_kg_per_h: 'massflow (kg/hr)',
  temperature_kelvin: 'temperature (C)',
  temperature_celsius: 'temperature (C)',
  density_kg_per_m3: 'density (kg/m3)',
};

const _RESULT_ALIAS_KEYS_TO_HIDE = new Set([
  'flow_kg_per_h',
  'temperature_celsius',
]);

let _resultsSelectedColumns = [];
let _resultsAvailableColumns = [];
let _latestResultRows = [];

function _isPlainObject(value) {
  return Object.prototype.toString.call(value) === '[object Object]';
}

function _flattenResultKeys(obj, prefix = '') {
  const keys = [];
  Object.entries(obj || {}).forEach(([rawKey, value]) => {
    const key = prefix ? `${prefix}.${rawKey}` : rawKey;
    if (_isPlainObject(value)) {
      keys.push(..._flattenResultKeys(value, key));
      return;
    }
    keys.push(key);
  });
  return keys;
}

function _getResultPathValue(obj, path) {
  return String(path || '').split('.').reduce((acc, part) => {
    if (acc == null) return undefined;
    return acc[part];
  }, obj);
}

function _humanizeResultKey(key) {
  const rawKey = String(key || '');
  if (_RESULT_COLUMN_LABEL_ALIASES[rawKey]) return _RESULT_COLUMN_LABEL_ALIASES[rawKey];
  if (rawKey.startsWith('tocomo_input.')) {
    const species = rawKey.slice('tocomo_input.'.length);
    return `inlet ${species} (molar ppm)`;
  }
  if (rawKey.startsWith('final.')) {
    const species = rawKey.slice('final.'.length);
    return `predicted ${species} (molar ppm)`;
  }

  return rawKey.replaceAll('_', ' ').replaceAll('.', ' / ');
}

function _formatNumericCell(value) {
  const n = Number(value);
  if (!Number.isFinite(n)) return _esc(String(value));
  const abs = Math.abs(n);
  if (abs === 0) return '0';
  if (abs >= 1000) return n.toFixed(1);
  if (abs >= 1) return n.toFixed(3).replace(/\.0+$/, '').replace(/(\.\d*?)0+$/, '$1');

  // Keep small values in plain decimal form for readability in the table.
  for (const digits of [3, 4, 5, 6, 8, 10, 12]) {
    const text = n.toFixed(digits).replace(/\.0+$/, '').replace(/(\.\d*?)0+$/, '$1');
    if (text !== '0' && text !== '-0') return text;
  }
  return n.toString();
}

function _renderResultCell(col, row) {
  if (typeof col.render === 'function') return col.render(row);
  const raw = typeof col.getter === 'function' ? col.getter(row) : _getResultPathValue(row, col.key);
  if (raw == null || raw === '') return '—';
  if (typeof raw === 'string') return _esc(raw);
  if (typeof raw === 'number') {
    const key = String(col.key || '');
    if (key.startsWith('tocomo_input.') || key.startsWith('final.')) {
      return Number.isFinite(raw) ? raw.toFixed(2) : _esc(String(raw));
    }
    return _formatNumericCell(raw);
  }
  if (typeof raw === 'boolean') return raw ? 'true' : 'false';
  if (Array.isArray(raw) || _isPlainObject(raw)) return _esc(JSON.stringify(raw));
  return _esc(String(raw));
}

function _buildResultColumns(rows) {
  const discoveredKeys = new Set();
  rows.forEach(row => {
    _flattenResultKeys(row).forEach(key => discoveredKeys.add(key));
  });

  const defByKey = new Map(_RESULT_COLUMN_DEFS.map(def => [def.key, def]));
  const columns = [];

  _RESULT_COLUMN_DEFS.forEach(def => {
    const hasData = rows.some(row => {
      const value = typeof def.getter === 'function' ? def.getter(row) : _getResultPathValue(row, def.key);
      return value != null && value !== '' && value !== '—';
    });
    if (hasData || def.defaultSelected) columns.push(def);
  });

  Array.from(discoveredKeys)
    .filter(key => !defByKey.has(key) && !_RESULT_ALIAS_KEYS_TO_HIDE.has(key))
    .sort((a, b) => a.localeCompare(b))
    .forEach(key => {
      columns.push({ key, label: _humanizeResultKey(key), defaultSelected: false });
    });

  return columns;
}

function _renderResultColumnPicker(columns) {
  const controls = document.getElementById('results-controls');
  const picker = document.getElementById('results-column-picker');
  const toggleBtn = document.getElementById('results-filter-toggle');
  if (!controls || !picker) return;
  if (!columns.length) {
    controls.style.display = 'none';
    controls.classList.remove('open');
    if (toggleBtn) toggleBtn.setAttribute('aria-expanded', 'false');
    picker.innerHTML = '';
    return;
  }

  const selected = new Set(_resultsSelectedColumns);
  picker.innerHTML = columns.map(col => `
    <label class="result-col-option">
      <input
        type="checkbox"
        data-col-key="${_esc(col.key)}"
        ${selected.has(col.key) ? 'checked' : ''}
        onchange="toggleResultColumn('${_esc(col.key)}', this.checked)">
      <span>${_esc(col.label)}</span>
    </label>
  `).join('');
  const isOpen = controls.classList.contains('open');
  controls.style.display = isOpen ? 'block' : 'none';
  if (toggleBtn) toggleBtn.setAttribute('aria-expanded', isOpen ? 'true' : 'false');
}

function toggleResultsFilterPanel() {
  const controls = document.getElementById('results-controls');
  const toggleBtn = document.getElementById('results-filter-toggle');
  if (!controls || !_resultsAvailableColumns.length) return;
  const nextOpen = !controls.classList.contains('open');
  controls.classList.toggle('open', nextOpen);
  controls.style.display = nextOpen ? 'block' : 'none';
  if (toggleBtn) {
    toggleBtn.setAttribute('aria-expanded', nextOpen ? 'true' : 'false');
  }
}

function toggleResultColumn(columnKey, checked) {
  const key = String(columnKey || '');
  if (!key) return;
  const availableKeys = new Set(_resultsAvailableColumns.map(col => col.key));
  const selected = new Set(_resultsSelectedColumns.filter(k => availableKeys.has(k)));
  if (checked) selected.add(key);
  else selected.delete(key);

  if (!selected.size) {
    selected.add(key);
    status('At least one parameter must stay visible in Results Summary.', 'info');
  }

  _resultsSelectedColumns = Array.from(selected);
  _renderResultColumnPicker(_resultsAvailableColumns);
  _renderResultTable(_latestResultRows);
}

function _renderResultTable(rows) {
  const thead = document.getElementById('results-thead');
  const tbody = document.getElementById('results-tbody');
  if (!thead || !tbody) return;

  const selectedColumns = _resultsAvailableColumns.filter(col => _resultsSelectedColumns.includes(col.key));
  if (!selectedColumns.length) {
    thead.innerHTML = '';
    tbody.innerHTML = '<tr><td>No parameters selected.</td></tr>';
    return;
  }

  thead.innerHTML = `<tr>${selectedColumns.map(col => `<th>${_esc(col.label)}</th>`).join('')}</tr>`;
  tbody.innerHTML = rows.map(row => `
    <tr>
      ${selectedColumns.map(col => `<td>${_renderResultCell(col, row)}</td>`).join('')}
    </tr>
  `).join('');
}

function showTable(rows) {
  if (!rows?.length) return;
  _latestResultRows = rows;
  document.getElementById('results-card').style.display = 'block';

  _resultsAvailableColumns = _buildResultColumns(rows);
  const availableKeys = new Set(_resultsAvailableColumns.map(col => col.key));
  const retainedSelection = _resultsSelectedColumns.filter(key => availableKeys.has(key));
  if (retainedSelection.length) {
    _resultsSelectedColumns = retainedSelection;
  } else {
    const defaults = _resultsAvailableColumns
      .filter(col => col.defaultSelected)
      .map(col => col.key);
    _resultsSelectedColumns = defaults.length ? defaults : (_resultsAvailableColumns[0] ? [_resultsAvailableColumns[0].key] : []);
  }

  _renderResultColumnPicker(_resultsAvailableColumns);
  _renderResultTable(rows);
}

// Init

document.getElementById('model-sel').addEventListener('change', () => {
  updateDynamicRunSettingsVisibility();
  if (_isDynamicModel(document.getElementById('model-sel').value)) {
    hideResultsSummary();
  }
  if (_cfg && document.getElementById('config-modal')?.classList.contains('open')) {
    renderConfigEditor();
  }
  loadSessions();
});
document.getElementById('map-sel').addEventListener('change', onMapSelectionChange);
loadMaps();
updateDynamicRunSettingsVisibility();
loadSessions();

// Modal helpers

function openModal(id) { document.getElementById(id).classList.add('open'); }
function closeModal(id) { document.getElementById(id).classList.remove('open'); }

// CONFIG EDITOR

let _cfg = null;

function _collectExistingExtraContaminants() {
  const base = new Set(_PHPITZ_BASE_INLET_SPECIES);
  const extras = new Set();
  (_cfg?.plant_inputs || []).forEach(plant => {
    const inlet = plant?.inlet_conc;
    if (!inlet || typeof inlet !== 'object') return;
    Object.keys(inlet).forEach(species => {
      const normalized = _normalizeSpeciesToken(species);
      if (!normalized || base.has(normalized)) return;
      const rawValue = inlet[species];
      const numericValue = Number(rawValue);
      const hasEnteredValue = Number.isFinite(numericValue)
        ? numericValue !== 0
        : String(rawValue ?? '').trim() !== '';
      if (!hasEnteredValue) return;
      extras.add(normalized);
    });
  });
  return Array.from(extras).sort();
}

function _getAvailablePhpitzContaminantsForAdd() {
  const base = new Set(_PHPITZ_BASE_INLET_SPECIES);
  _ensureConfigExtraContaminants();
  const alreadyAdded = new Set((_cfg?._extraContaminants || []).map(_normalizeSpeciesToken));

  const candidates = new Set(_PHPITZ_SUGGESTED_EXTRA_SPECIES.map(_normalizeSpeciesToken));
  (_cfg?.plant_inputs || []).forEach(plant => {
    const inlet = plant?.inlet_conc;
    if (!inlet || typeof inlet !== 'object') return;
    Object.keys(inlet).forEach(species => {
      const normalized = _normalizeSpeciesToken(species);
      if (normalized) candidates.add(normalized);
    });
  });

  return Array.from(candidates)
    .filter(species => species && !base.has(species) && !alreadyAdded.has(species))
    .sort();
}

function _ensureConfigExtraContaminants() {
  if (!_cfg) return;
  if (!Array.isArray(_cfg._extraContaminants)) {
    _cfg._extraContaminants = _collectExistingExtraContaminants();
  }
  _cfg._extraContaminants = Array.from(
    new Set(_cfg._extraContaminants.map(_normalizeSpeciesToken).filter(Boolean))
  ).sort();
}

function _getConfigInletSpeciesForModel() {
  const modelId = _selectedModelId();
  if (_isTocomoModelId(modelId)) {
    return {
      baseSpecies: _TOCOMO_INLET_SPECIES,
      extraSpecies: [],
      allowExtras: false,
    };
  }

  _ensureConfigExtraContaminants();
  return {
    baseSpecies: _PHPITZ_BASE_INLET_SPECIES,
    extraSpecies: _cfg?._extraContaminants || [],
    allowExtras: _isPhpitzModelId(modelId),
  };
}

function addConfigExtraContaminant(selectedSpecies = '') {
  if (!_cfg) return;
  const modelId = _selectedModelId();
  if (!_isPhpitzModelId(modelId)) return;

  _ensureConfigExtraContaminants();
  const species = _normalizeSpeciesToken(selectedSpecies);
  if (!species) return;
  if (!/^[A-Z0-9_]+$/.test(species)) {
    alert('Use letters, numbers, and underscore only (for example: NO or HNO3).');
    return;
  }

  const base = new Set(_PHPITZ_BASE_INLET_SPECIES);
  if (base.has(species)) {
    alert(`${species} is already part of the default PH_PITZ inlet set.`);
    return;
  }
  if (_cfg._extraContaminants.includes(species)) {
    if (input) input.value = '';
    return;
  }

  _cfg._extraContaminants.push(species);
  _cfg._extraContaminants.sort();

  (_cfg.plant_inputs || []).forEach(plant => {
    if (!plant.inlet_conc || typeof plant.inlet_conc !== 'object') plant.inlet_conc = {};
    if (plant.inlet_conc[species] == null) plant.inlet_conc[species] = 0;
  });
  renderConfigEditor();
}

function toggleConfigContaminantPicker(index) {
  const row = document.getElementById(`cfg-add-contaminant-row-${index}`);
  if (!row) return;
  row.style.display = row.style.display === 'none' ? 'flex' : 'none';
}

function addConfigExtraContaminantFromPicker(index) {
  const select = document.getElementById(`cfg-add-contaminant-select-${index}`);
  const species = String(select?.value || '').trim();
  if (!species) return;
  addConfigExtraContaminant(species);
}

function removeConfigExtraContaminant(species) {
  if (!_cfg) return;
  _ensureConfigExtraContaminants();
  const normalized = _normalizeSpeciesToken(species);
  _cfg._extraContaminants = _cfg._extraContaminants.filter(s => s !== normalized);
  (_cfg.plant_inputs || []).forEach(plant => {
    if (plant?.inlet_conc && typeof plant.inlet_conc === 'object') {
      delete plant.inlet_conc[normalized];
    }
  });
  renderConfigEditor();
}

async function openConfigEditor() {
  _cfg = await api('/api/config/');
  _ensureConfigExtraContaminants();
  renderConfigEditor();
  openModal('config-modal');
}

function renderConfigEditor() {
  document.getElementById('cfg-p-bara').value = _cfg.p_bara ?? '';
  document.getElementById('cfg-storage-name').value = _cfg.storage_name ?? 'Storage';

  const { baseSpecies, extraSpecies, allowExtras } = _getConfigInletSpeciesForModel();
  const activeSpecies = [...baseSpecies, ...extraSpecies];
  const availableToAdd = allowExtras ? _getAvailablePhpitzContaminantsForAdd() : [];

  const extraControlsHtml = allowExtras
    ? `<div style="font-size:.78rem;color:#4a5568;margin:.1rem 0 .8rem;">PH_PITZ is active. You can add contaminants from each plant inlet section.</div>`
    : `<div style="font-size:.78rem;color:#4a5568;margin:.1rem 0 .8rem;">Inlet concentrations shown here are limited to O2, H2O, H2S, SO2, and NO2.</div>`;

  // Plants
  document.getElementById('cfg-plants').innerHTML = _cfg.plant_inputs.map((p, i) => `
    <div class="plant-card">
      <div class="plant-card-header" onclick="togglePlant(${i})">
        <span>${p.name || 'Plant ' + (i + 1)}</span>
        <div style="display:flex;align-items:center;gap:.6rem;">
          <button class="btn btn-sm" style="background:#fff5f5;color:#c53030" onclick="removePlant(${i}, event)">Remove</button>
          <span>&#9660;</span>
        </div>
      </div>
      <div class="plant-card-body" id="plant-body-${i}">
        <div class="field-row">
          <label><span>Name</span><input data-pi="${i}" data-f="name" value="${p.name ?? ''}"></label>
          <label><span>Phase</span>
            <select data-pi="${i}" data-f="stream_phase">
              <option ${p.stream_phase==='liquid'?'selected':''}>liquid</option>
              <option ${p.stream_phase==='gas'?'selected':''}>gas</option>
            </select></label>
          <label><span>Flowrate (kg/hr)</span><input type="number" data-pi="${i}" data-f="flowrate" value="${p.flowrate ?? ''}"></label>
          <label><span>Temp (°C)</span><input type="number" data-pi="${i}" data-f="temperature_celsius" value="${p.temperature_celsius ?? ''}"></label>
          <label><span>Pipe length (m)</span><input type="number" data-pi="${i}" data-f="pipelength" value="${p.pipelength ?? ''}"></label>
          <label><span>Pipe diameter (m)</span><input type="number" step="any" data-pi="${i}" data-f="pipediameter" value="${p.pipediameter ?? ''}"></label>
        </div>
        <div class="section-label">Inlet concentrations (molar ppm)</div>
        <div class="conc-grid">
          ${activeSpecies.map(s => `
            <label><span>${s}</span>
              <input type="number" step="any" data-pi="${i}" data-conc="${s}" value="${(p.inlet_conc??{})[s] ?? 0}">
            </label>`).join('')}
        </div>
        ${allowExtras ? `
          <div style="display:flex;justify-content:flex-end;margin-top:.5rem;">
            <button class="btn btn-sm" type="button" onclick="toggleConfigContaminantPicker(${i})">Add Contaminant</button>
          </div>
          <div id="cfg-add-contaminant-row-${i}" style="display:none;gap:.4rem;align-items:center;justify-content:flex-end;margin-top:.4rem;">
            <select id="cfg-add-contaminant-select-${i}" style="max-width:220px;margin:0;">
              ${availableToAdd.length
                ? availableToAdd.map(species => `<option value="${_esc(species)}">${_esc(species)}</option>`).join('')
                : '<option value="">No additional contaminants</option>'}
            </select>
            <button class="btn btn-sm" type="button" onclick="addConfigExtraContaminantFromPicker(${i})" ${availableToAdd.length ? '' : 'disabled'}>Add</button>
          </div>
        ` : ''}
      </div>
    </div>`).join('');

  const controlsEl = document.getElementById('cfg-contaminant-controls');
  if (controlsEl) controlsEl.innerHTML = extraControlsHtml;

  // Merge options
  renderMergeOptions();
}

function addPlant() {
  if (!_cfg) return;

  // Preserve unsaved edits from existing inputs before re-rendering the editor.
  collectConfig();

  const { baseSpecies, extraSpecies } = _getConfigInletSpeciesForModel();
  const activeSpecies = [...baseSpecies, ...extraSpecies];

  const inletConc = {};
  activeSpecies.forEach(species => {
    inletConc[species] = 0;
  });

  _cfg.plant_inputs.push({
    name: `Plant ${_cfg.plant_inputs.length + 1}`,
    stream_phase: 'gas',
    flowrate: 1000,
    temperature_celsius: 25,
    pipelength: 1000,
    pipediameter: 0.5,
    inlet_conc: inletConc,
  });

  renderConfigEditor();
}

function removePlant(index, event) {
  if (event) event.stopPropagation();
  if (!_cfg) return;
  _cfg.plant_inputs.splice(index, 1);
  renderConfigEditor();
}

function renderMergeOptions() {
  const merges = _cfg.merge_pipe_inputs ?? {};
  document.getElementById('cfg-merges').innerHTML = Object.entries(merges).map(([name, m], i) => `
    <div class="plant-card">
      <div class="plant-card-header" onclick="toggleMerge(${i})">
        <span>${name}</span>
        <div style="display:flex;align-items:center;gap:.6rem;">
          <button class="btn btn-sm" style="background:#fff5f5;color:#c53030" onclick="removeMergeOption('${name}', event)">Remove</button>
          <span>&#9660;</span>
        </div>
      </div>
      <div class="plant-card-body" id="merge-body-${i}">
        <div class="field-row">
          <label><span>Name</span><input class="merge-name" data-mkey="${name}" data-f="name" value="${name}" placeholder="Name"></label>
          <label><span>Pipe length (m)</span><input type="number" step="any" data-mkey="${name}" data-f="pipelength" value="${m.pipelength}" placeholder="Length (m)"></label>
          <label><span>Pipe diameter (m)</span><input type="number" step="any" data-mkey="${name}" data-f="pipediameter" value="${m.pipediameter}" placeholder="Diameter (m)"></label>
        </div>
      </div>
    </div>`).join('');
}

function togglePlant(i) {
  document.getElementById('plant-body-' + i).classList.toggle('open');
}

function toggleMerge(i) {
  document.getElementById('merge-body-' + i).classList.toggle('open');
}

function addMergeOption() {
  if (!_cfg) return;
  // Preserve unsaved edits from existing inputs before re-rendering the editor.
  collectConfig();

  const name = prompt('Merge name (e.g. "Brussels"):');
  if (!name?.trim()) return;
  _cfg.merge_pipe_inputs[name.trim()] = { pipelength: 10000, pipediameter: 0.5 };
  renderMergeOptions();
}

function removeMergeOption(key, event) {
  if (event) event.stopPropagation();
  delete _cfg.merge_pipe_inputs[key];
  renderMergeOptions();
}

function collectConfig() {
  // Collect p_bara
  _cfg.p_bara = parseFloat(document.getElementById('cfg-p-bara').value);
  _cfg.storage_name = (document.getElementById('cfg-storage-name').value || 'Storage').trim() || 'Storage';

  // Collect plant fields
  document.querySelectorAll('[data-pi][data-f]').forEach(el => {
    const i = +el.dataset.pi;
    const f = el.dataset.f;
    const v = el.tagName === 'SELECT' ? el.value : (el.type === 'number' ? +el.value : el.value);
    _cfg.plant_inputs[i][f] = v;
  });
  // Collect concentrations
  document.querySelectorAll('[data-pi][data-conc]').forEach(el => {
    const i = +el.dataset.pi;
    const s = el.dataset.conc;
    if (!_cfg.plant_inputs[i].inlet_conc) _cfg.plant_inputs[i].inlet_conc = {};
    _cfg.plant_inputs[i].inlet_conc[s] = +el.value;
  });

  const { baseSpecies, extraSpecies, allowExtras } = _getConfigInletSpeciesForModel();
  const allowedSpecies = new Set(allowExtras ? [...baseSpecies, ...extraSpecies] : baseSpecies);
  _cfg.plant_inputs.forEach(plant => {
    const inlet = plant.inlet_conc && typeof plant.inlet_conc === 'object' ? plant.inlet_conc : {};
    const nextInlet = {};
    allowedSpecies.forEach(species => {
      const numeric = Number(inlet[species]);
      nextInlet[species] = Number.isFinite(numeric) ? numeric : 0;
    });
    plant.inlet_conc = nextInlet;
  });
  // Collect merge options (pick up any inline edits to name/specs)
  const newMerges = {};
  document.querySelectorAll('[data-mkey]').forEach(el => {
    const key = el.dataset.mkey;
    const f = el.dataset.f;
    if (!newMerges[key]) newMerges[key] = { ..._cfg.merge_pipe_inputs[key] };
    if (f === 'name') {
      const newKey = el.value.trim() || key;
      if (newKey !== key) { newMerges[newKey] = newMerges[key]; delete newMerges[key]; }
    } else {
      newMerges[key][f] = +el.value;
    }
  });
  _cfg.merge_pipe_inputs = newMerges;
}

async function saveConfig() {
  collectConfig();

  const phaseCheck = _validateSinglePhasePlants(_cfg?.plant_inputs || []);
  if (!phaseCheck.ok) {
    alert(phaseCheck.message);
    return;
  }

  try {
    await api('/api/config/', {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(_cfg),
    });
    closeModal('config-modal');
    loadMaps();
  } catch (e) {
    alert('Save failed: ' + e.message);
  }
}

// MAP BUILDER

const MB = {
  step: 1,
  name: '',
  plants: [],
  merges: [],
  availableNodes: [],
  storageName: 'Storage',
  _manualNodePositions: {},
  _draftGraphState: null,
};

async function openMapBuilder() {
  const cfg = await api('/api/config/');
  MB._plants = cfg.plant_inputs;
  MB._mergePipeInputs = cfg.merge_pipe_inputs || {};
  MB.storageName = (cfg.storage_name || 'Storage').trim() || 'Storage';
  MB.step = 1;
  MB.name = '';
  MB.plants = [];
  MB.merges = [];
  MB.availableNodes = [];
  MB._lastLayout = null;
  MB._manualNodePositions = {};
  MB._draftGraphState = null;
  renderMBStep1();
  renderMBDraftReview();
  openModal('map-modal');
}

function updateMBPlantsFromStep1() {
  MB.plants = Array.from(document.querySelectorAll('#mb-step1 input[type=checkbox]:checked')).map(e => +e.value);
  renderMBDraftReview();
}

function updateMBStorageName() {
  MB.storageName = (document.getElementById('mb-storage-name')?.value || MB.storageName || 'Storage').trim() || 'Storage';
  renderMBDraftReview();
}

function renderMBStep1() {
  setWizardStep(1);
  document.getElementById('mb-step1').innerHTML = `
    <div class="section-label">Select active plants</div>
    ${MB._plants.map((p, i) => `
      <label style="display:flex;align-items:center;gap:.5rem;padding:.35rem 0;cursor:pointer">
        <input type="checkbox" value="${i}" ${MB.plants.includes(i)?'checked':''}
          onchange="updateMBPlantsFromStep1()">
        <span>${p.name}</span>
        <span style="font-size:.75rem;color:#718096">${p.stream_phase} · ${p.flowrate} kg/hr · ${p.temperature_celsius}°C</span>
      </label>`).join('')}`;

  renderMBDraftReview();
}

function renderMBStep3() {
  setWizardStep(3);
  document.getElementById('mb-step3').innerHTML = `
    <div class="section-label" style="margin-top:0">Finalize map</div>
    <div class="field-row" style="margin-bottom:1rem">
      <label style="max-width:420px"><span>Map name</span>
        <input id="mb-name" placeholder="e.g. my_pipeline" value="${_esc(MB.name)}" oninput="MB.name = this.value.trim()">
      </label>
    </div>
    <div class="section-label" style="margin-top:0">Storage</div>
    <div class="field-row" style="margin-bottom:1rem">
      <label style="max-width:360px"><span>Storage node name</span>
        <input id="mb-storage-name" placeholder="e.g. Terminal Tank" value="${_esc(MB.storageName || 'Storage')}" oninput="updateMBStorageName()">
      </label>
    </div>
    <div class="empty" style="text-align:left;padding:0;color:#4a5568">
      Storage is connected from all terminal nodes in your map.
    </div>
  `;

  renderMBDraftReview();
}

function goMBNext() {
  if (MB.step === 1) {
    renderMBStep2();
    return;
  }
  if (MB.step === 2) {
    renderMBStep3();
  }
}

function goMBBack() {
  if (MB.step === 3) {
    renderMBStep2();
    return;
  }
  if (MB.step === 2) {
    renderMBStep1();
  }
}

function renderMBStep2() {
  setWizardStep(2);
  // Available nodes = selected plants + already-added merges
  MB.availableNodes = [
    ...MB.plants.map(i => ({ id: MB._plants[i].name, type: 'plant' })),
    ...MB.merges.map(m => ({ id: m.merge_name, type: 'merge' })),
  ];

  const configuredMergeNames = Object.keys(MB._mergePipeInputs || {}).filter(
    name => String(name).toLowerCase() !== 'default'
  );
  const usedMergeNames = new Set(MB.merges.map(m => m.merge_name));
  const unusedMergeNames = configuredMergeNames.filter(name => !usedMergeNames.has(name));

  const nodeChips = MB.availableNodes.map(n =>
    `<span class="chip chip-${n.type}">${n.id}</span>`).join('');

  const mergeList = MB.merges.length
    ? MB.merges.map((m, i) => `
        <div class="merge-def-row">
          <div>
            <span class="merge-def-name">${m.merge_name}</span>
            <span class="merge-def-meta"> ← ${m.sources.map(s=>s[1]).join(', ')} · ${m.pipelength} m · ⌀${m.pipediameter} m</span>
          </div>
          <button class="btn btn-sm" style="background:#fff5f5;color:#c53030" onclick="removeMBMerge(${i})">✕</button>
        </div>`).join('')
    : '<p style="color:#a0aec0;font-size:.85rem">No merges added yet - click "Add Merge" or skip to save without merges.</p>';

  document.getElementById('mb-step2').innerHTML = `
    <div class="section-label">Current nodes</div>
    <div class="node-chips">${nodeChips}</div>

    <div class="section-label">Added merges</div>
    <div id="mb-merge-list">${mergeList}</div>

    <details style="margin-top:1rem">
      <summary style="cursor:pointer;font-weight:600;color:#2b6cb0;font-size:.9rem">&#43; Add Merge</summary>
      <div style="padding:1rem;background:#f7fafc;border-radius:8px;margin-top:.5rem">
        <div class="field-row">
          <label><span>Merge name (from config)</span>
            <select id="mb-mname" onchange="syncMBMergePipeDefaults()">
              ${unusedMergeNames.length
                ? unusedMergeNames.map(name => `<option value="${_esc(name)}">${_esc(name)}</option>`).join('')
                : '<option value="">No configured merges left</option>'}
            </select>
          </label>
          <label><span>Pipe length (m)</span><input id="mb-mlen" type="number" value="${unusedMergeNames.length ? Number(MB._mergePipeInputs[unusedMergeNames[0]]?.pipelength ?? 10000) : ''}" ${unusedMergeNames.length ? '' : 'disabled'}></label>
          <label><span>Pipe diameter (m)</span><input id="mb-mdiam" type="number" step="any" value="${unusedMergeNames.length ? Number(MB._mergePipeInputs[unusedMergeNames[0]]?.pipediameter ?? 0.5) : ''}" ${unusedMergeNames.length ? '' : 'disabled'}></label>
        </div>
        <div class="section-label">Source nodes (select >= 2)</div>
        ${MB.availableNodes.map(n => `
          <label style="display:flex;align-items:center;gap:.5rem;padding:.25rem 0;cursor:pointer">
            <input type="checkbox" name="mb-src" value="${n.id}" data-type="${n.type}">
            <span class="chip chip-${n.type}" style="pointer-events:none">${n.id}</span>
          </label>`).join('')}
        <button class="btn btn-primary" style="margin-top:.75rem;width:auto;padding:.45rem 1.2rem" onclick="addMBMerge()" ${unusedMergeNames.length ? '' : 'disabled'}>Add</button>
      </div>
    </details>`;

  renderMBDraftReview();
}

function syncMBMergePipeDefaults() {
  const mergeName = document.getElementById('mb-mname')?.value;
  const mergeCfg = MB._mergePipeInputs?.[mergeName];
  const lenInput = document.getElementById('mb-mlen');
  const diamInput = document.getElementById('mb-mdiam');
  if (!lenInput || !diamInput) return;
  if (!mergeCfg) {
    lenInput.value = '';
    diamInput.value = '';
    return;
  }
  lenInput.value = Number(mergeCfg.pipelength ?? 10000);
  diamInput.value = Number(mergeCfg.pipediameter ?? 0.5);
}

function addMBMerge() {
  const name = document.getElementById('mb-mname').value.trim();
  const len = +document.getElementById('mb-mlen').value;
  const diam = +document.getElementById('mb-mdiam').value;
  const srcs = Array.from(document.querySelectorAll('input[name="mb-src"]:checked')).map(e => ({
    id: e.value,
    type: e.dataset.type,
  }));
  if (!name) { alert('Select a merge name from config.'); return; }
  if (srcs.length < 2) { alert('Select at least 2 source nodes.'); return; }
  if (MB.merges.some(m => m.merge_name === name)) { alert('That merge has already been added.'); return; }

  // Build sources as [["plant"|"merge", index/name]] matching backend format.
  const sources = srcs.map(src => {
    if (src.type === 'plant') {
      const plantIdx = MB._plants.findIndex(p => p.name === src.id);
      if (plantIdx !== -1 && MB.plants.includes(plantIdx)) return ['plant', plantIdx];
    }
    return ['merge', src.id];
  });

  MB.merges.push({ merge_name: name, sources, pipelength: len, pipediameter: diam });
  renderMBStep2();
}

function removeMBMerge(i) {
  MB.merges.splice(i, 1);
  renderMBStep2();
}

function renderMBDraftReview() {
  const host = document.getElementById('mb-review');
  if (!host || !MB._plants) return;
  MB.storageName = (document.getElementById('mb-storage-name')?.value || MB.storageName || 'Storage').trim() || 'Storage';

  const nodes = new Map();
  const edges = [];
  const addNode = (id, label, type) => {
    if (!nodes.has(id)) nodes.set(id, { id, label, type });
  };

  MB.plants.forEach(plantIdx => {
    const plant = MB._plants[plantIdx];
    if (!plant) return;
    addNode(`plant:${plantIdx}`, plant.name || `Plant ${plantIdx + 1}`, 'plant');
  });

  MB.merges.forEach(merge => {
    const mergeId = `merge:${merge.merge_name}`;
    addNode(mergeId, merge.merge_name, 'merge');

    (merge.sources || []).forEach(([srcType, srcValue]) => {
      if (srcType === 'plant') {
        const idx = Number(srcValue);
        const plant = MB._plants[idx];
        const pid = `plant:${idx}`;
        addNode(pid, plant?.name || `Plant ${idx + 1}`, 'plant');
        edges.push([pid, mergeId]);
      } else {
        const mid = `merge:${srcValue}`;
        addNode(mid, String(srcValue), 'merge');
        edges.push([mid, mergeId]);
      }
    });
  });

  // Storage should appear at the end of map building (storage step), not during plants/merges editing.
  if (nodes.size && MB.step === 3) {
    const storageId = `storage:${MB.storageName}`;
    addNode(storageId, MB.storageName, 'storage');

    const outgoing = new Set(edges.map(([src]) => src));
    Array.from(nodes.values())
      .filter(node => node.type !== 'storage' && !outgoing.has(node.id))
      .forEach(node => edges.push([node.id, storageId]));
  }

  if (!nodes.size) {
    MB._draftGraphState = null;
    host.innerHTML = '<div class="empty" style="padding:1rem 0">Select plants to start the map review.</div>';
    return;
  }

  const layoutUnits = _computeOverlapAwareLayout(
    Array.from(nodes.values()),
    edges,
    MB._lastLayout || null,
  );
  MB._lastLayout = layoutUnits;

  const xs = Object.values(layoutUnits).map(p => p.x);
  const ys = Object.values(layoutUnits).map(p => p.y);
  const minX = xs.length ? Math.min(...xs) : 0;
  const maxX = xs.length ? Math.max(...xs) : 0;
  const maxAbsY = ys.length ? Math.max(...ys.map(y => Math.abs(y))) : 0;

  const xScale = 180;
  const yScale = 105;
  const xPad = 120;
  const yPad = 100;
  const width = Math.max(1200, (maxX - minX) * xScale + xPad * 2 + 100);
  const height = Math.max(760, (maxAbsY * 2) * yScale + yPad * 2 + 100);
  const positions = {};

  Object.entries(layoutUnits).forEach(([id, p]) => {
    positions[id] = {
      x: xPad + (p.x - minX) * xScale,
      y: (height / 2) - p.y * yScale,
    };
  });

  const activeNodeIds = new Set(Object.keys(positions));
  const nextManualPositions = {};
  Object.entries(MB._manualNodePositions || {}).forEach(([id, p]) => {
    if (!activeNodeIds.has(id) || !p) return;
    positions[id] = { x: Number(p.x), y: Number(p.y) };
    nextManualPositions[id] = { x: Number(p.x), y: Number(p.y) };
  });
  MB._manualNodePositions = nextManualPositions;

  const outgoingByNode = new Map();
  const incomingByNode = new Map();
  edges.forEach(([src, dst], idx) => {
    if (!outgoingByNode.has(src)) outgoingByNode.set(src, []);
    if (!incomingByNode.has(dst)) incomingByNode.set(dst, []);
    outgoingByNode.get(src).push(idx);
    incomingByNode.get(dst).push(idx);
  });

  MB._draftGraphState = {
    edges,
    positions,
    outgoingByNode,
    incomingByNode,
    nodes: Array.from(nodes.values()),
    nodeWidth: 56,
    nodeHeight: 32,
  };

  const edgeSvg = _renderMBDraftEdgePaths();
  const nodeSvg = _renderMBDraftNodes();

  host.innerHTML = `
    <div style="display:flex;justify-content:space-between;align-items:center;gap:.6rem;margin-bottom:.4rem;flex-wrap:wrap;">
      <div style="font-size:.78rem;color:#4a5568">Drag nodes to tune the layout while you build.</div>
      <button class="btn btn-sm" type="button" onclick="resetMBDraftNodePositions()">Reset node positions</button>
    </div>
    <svg class="map-preview-svg" id="mb-review-svg" viewBox="0 0 ${width} ${height}" role="img" aria-label="Draft pipeline map review">
      <defs>
        <marker id="mb-arrow" markerWidth="10" markerHeight="8" refX="9" refY="4" orient="auto" markerUnits="strokeWidth">
          <path d="M0,0 L10,4 L0,8 z" fill="#4a5568"></path>
        </marker>
      </defs>
      <g id="mb-review-edges">${edgeSvg}</g>
      <g id="mb-review-nodes">${nodeSvg}</g>
    </svg>
  `;

  enableMBDraftReviewInteractions();
}

function _mbDraftNodeRect(nodeId) {
  const state = MB._draftGraphState;
  if (!state) return null;
  const p = state.positions[nodeId];
  if (!p) return null;
  const hw = state.nodeWidth / 2;
  const hh = state.nodeHeight / 2;
  return {
    left: p.x - hw,
    right: p.x + hw,
    top: p.y - hh,
    bottom: p.y + hh,
    cx: p.x,
    cy: p.y,
  };
}

function _renderMBDraftEdgePaths() {
  const state = MB._draftGraphState;
  if (!state) return '';
  return state.edges.map(([src, dst], edgeIdx) => {
    const sourceRect = _mbDraftNodeRect(src);
    const targetRect = _mbDraftNodeRect(dst);
    if (!sourceRect || !targetRect) return '';

    const srcEdges = state.outgoingByNode.get(src) || [edgeIdx];
    const dstEdges = state.incomingByNode.get(dst) || [edgeIdx];
    const srcSlot = srcEdges.indexOf(edgeIdx);
    const dstSlot = dstEdges.indexOf(edgeIdx);

    const pathD = _buildClassicEdgePath({
      sourceRect,
      targetRect,
      srcSlot,
      srcCount: srcEdges.length,
      dstSlot,
      dstCount: dstEdges.length,
    });
    return `<path d="${pathD}" fill="none" stroke="#4a5568" stroke-width="2" marker-end="url(#mb-arrow)" />`;
  }).join('');
}

function _renderMBDraftNodes() {
  const state = MB._draftGraphState;
  if (!state) return '';
  const hw = state.nodeWidth / 2;
  const hh = state.nodeHeight / 2;
  return state.nodes.map(node => {
    const p = state.positions[node.id];
    const fill = node.type === 'plant' ? '#c6f6d5' : (node.type === 'storage' ? '#bee3f8' : '#feebc8');
    const stroke = node.type === 'plant' ? '#276749' : (node.type === 'storage' ? '#2c5282' : '#c05621');
    return `
      <g class="mb-node" data-node-id="${_esc(node.id)}" transform="translate(${p.x} ${p.y})">
        <rect x="${-hw}" y="${-hh}" rx="7" ry="7" width="${state.nodeWidth}" height="${state.nodeHeight}" fill="${fill}" stroke="${stroke}" stroke-width="1.8" />
        <text x="0" y="3.5" text-anchor="middle" font-size="10.5" fill="#2d3748">${_esc(node.label)}</text>
      </g>
    `;
  }).join('');
}

function _syncMBDraftSvg() {
  const state = MB._draftGraphState;
  if (!state) return;
  const edgesGroup = document.getElementById('mb-review-edges');
  const nodesGroup = document.getElementById('mb-review-nodes');
  if (!edgesGroup || !nodesGroup) return;
  edgesGroup.innerHTML = _renderMBDraftEdgePaths();
  nodesGroup.innerHTML = _renderMBDraftNodes();
}

function resetMBDraftNodePositions() {
  MB._manualNodePositions = {};
  renderMBDraftReview();
}

function enableMBDraftReviewInteractions() {
  const svg = document.getElementById('mb-review-svg');
  if (!svg) return;

  let nodeDragging = null;

  const pointFromEvent = (event) => {
    const rect = svg.getBoundingClientRect();
    const viewBox = svg.viewBox.baseVal;
    const sx = viewBox.width / rect.width;
    const sy = viewBox.height / rect.height;
    return {
      x: viewBox.x + (event.clientX - rect.left) * sx,
      y: viewBox.y + (event.clientY - rect.top) * sy,
    };
  };

  svg.style.touchAction = 'none';

  svg.onpointerdown = (event) => {
    const nodeEl = event.target.closest('.mb-node');
    if (!nodeEl || !MB._draftGraphState) return;
    const nodeId = nodeEl.getAttribute('data-node-id');
    const pos = MB._draftGraphState.positions[nodeId];
    if (!pos) return;

    const p = pointFromEvent(event);
    nodeDragging = {
      pointerId: event.pointerId,
      nodeId,
      dx: pos.x - p.x,
      dy: pos.y - p.y,
    };
    svg.setPointerCapture(event.pointerId);
    event.preventDefault();
  };

  svg.onpointermove = (event) => {
    if (!nodeDragging || !MB._draftGraphState) return;
    if (event.pointerId !== nodeDragging.pointerId) return;

    const p = pointFromEvent(event);
    const nx = p.x + nodeDragging.dx;
    const ny = p.y + nodeDragging.dy;

    MB._draftGraphState.positions[nodeDragging.nodeId] = { x: nx, y: ny };
    MB._manualNodePositions[nodeDragging.nodeId] = { x: nx, y: ny };
    _syncMBDraftSvg();
  };

  svg.onpointerup = (event) => {
    if (!nodeDragging) return;
    if (event.pointerId === nodeDragging.pointerId) {
      nodeDragging = null;
      svg.releasePointerCapture(event.pointerId);
    }
  };

  svg.onpointercancel = () => {
    nodeDragging = null;
  };
}

async function saveMBMap() {
  MB.name = (document.getElementById('mb-name')?.value || MB.name).trim();
  MB.storageName = (document.getElementById('mb-storage-name')?.value || MB.storageName || 'Storage').trim() || 'Storage';
  if (!MB.name) { alert('Enter a map name first.'); return; }
  if (!MB.plants.length) { alert('Select at least one plant.'); return; }

  const mergeDefinitions = MB.merges.map(m => ({
    merge_name: m.merge_name,
    sources: m.sources,
  }));
  const mergePipeInputs = Object.fromEntries(
    MB.merges.map(m => [m.merge_name, { pipelength: m.pipelength, pipediameter: m.pipediameter }])
  );

  try {
    await api('/api/maps/', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        name: MB.name,
        pipeline_map: { merge_definitions: mergeDefinitions, merge_pipe_inputs: mergePipeInputs, storage_name: MB.storageName },
      }),
    });
    closeModal('map-modal');
    loadMaps();
  } catch (e) {
    alert('Save failed: ' + e.message);
  }
}

function setWizardStep(n) {
  [1, 2, 3].forEach(i => {
    document.getElementById('mb-step' + i).classList.toggle('active', i === n);
    const s = document.getElementById('wstep' + i);
    s.classList.toggle('active', i === n);
    s.classList.toggle('done', i < n);
  });
  document.getElementById('mb-next-btn').style.display = (n === 1 || n === 2) ? '' : 'none';
  document.getElementById('mb-back-btn').style.display = (n === 2 || n === 3) ? '' : 'none';
  document.getElementById('mb-save-btn').style.display = n === 3 ? '' : 'none';
  MB.step = n;
}
