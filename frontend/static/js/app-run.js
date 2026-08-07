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
            ${s.phase_envelope_zip_url
              ? `<a class="btn btn-sm link" href="${s.phase_envelope_zip_url}" download>Phase Envelopes ZIP</a>`
              : (s.phase_envelope_folder_url
                ? `<a class="btn btn-sm link" href="${s.phase_envelope_folder_url}" target="_blank">Phase Envelopes Folder</a>`
                : (Array.isArray(s.phase_envelope_urls) && s.phase_envelope_urls.length
                  ? `<a class="btn btn-sm link" href="${s.phase_envelope_urls[0]}" target="_blank">Phase Envelope</a>`
                  : ''))}
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
  const mapSelector = document.getElementById('map-sel');
  if (mapSelector) mapSelector.value = mapName;
  btn.disabled = true;
  btn.innerHTML = '<span class="spinner"></span> Starting…';
  clearStatus();
  setRunProgress(0);

  try {
    let popupMapData = null;
    let popupPlantInputs = [];

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
      let dynamicMapData = null;
      let dynamicPlantInputs = [];
      try {
        const [mapData, cfg] = await _loadMapAndConfigWithRetry(mapName);
        dynamicMapData = mapData;
        dynamicPlantInputs = Array.isArray(cfg?.plant_inputs) ? cfg.plant_inputs : [];
        _currentPlantInputs = dynamicPlantInputs;
        popupMapData = mapData;
        popupPlantInputs = dynamicPlantInputs;
      } catch {
        // Keep graphs visible even if map preview data fails to load.
      }

      renderDynamicGraphs(result.graph_urls || [], mapName, dynamicMapData, dynamicPlantInputs);
      hideResultsSummary();
    } else {
      showMapLoading(`Loading interactive pipeline map: ${mapName}...`);
      const [mapData, cfg] = await _loadMapAndConfigWithRetry(mapName);
      const plantInputs = Array.isArray(cfg?.plant_inputs) ? cfg.plant_inputs : [];
      _currentPlantInputs = plantInputs;
      popupMapData = mapData;
      popupPlantInputs = plantInputs;
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

    if (!popupMapData) {
      try {
        const [mapData, cfg] = await _loadMapAndConfigWithRetry(mapName);
        popupMapData = mapData;
        popupPlantInputs = Array.isArray(cfg?.plant_inputs) ? cfg.plant_inputs : [];
      } catch {
        // Ignore popup refresh failures when simulation succeeded.
      }
    }
    if (popupMapData) {
      renderMapVariablesPopup(mapName, popupMapData, popupPlantInputs);
      openModal('map-vars-modal');
    }

    const statusEl = document.getElementById('run-status');
    statusEl.className = 'status success';
    setRunProgress(100);
    const warningEl = document.getElementById('run-warning');
    if (result.phase_envelope_warning) {
      warningEl.className = 'status warning';
      warningEl.textContent = result.phase_envelope_warning;
      warningEl.style.display = '';
    } else {
      warningEl.style.display = 'none';
    }
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

