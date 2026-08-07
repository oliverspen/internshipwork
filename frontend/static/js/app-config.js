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

function addConfigExtraContaminant(selectedSpecies = '', options = {}) {
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
  const openPlantIndexes = _getOpenPlantBodyIndexes();
  if (Number.isFinite(Number(options.openPlantIndex))) {
    openPlantIndexes.add(Number(options.openPlantIndex));
  }
  renderConfigEditor({
    openPlantIndexes,
    openContaminantPickerIndexes: options.keepPickerOpen
      ? [Number(options.openPlantIndex)]
      : [],
  });
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
  addConfigExtraContaminant(species, {
    openPlantIndex: Number(index),
    keepPickerOpen: true,
  });
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

function _focusConfigEditorForNode(nodeId) {
  const raw = String(nodeId || '');
  if (!raw.includes(':')) return;

  const [nodeType, ...rest] = raw.split(':');
  const nodeValue = rest.join(':');
  if (!nodeType || !nodeValue) return;

  if (nodeType === 'plant') {
    const idx = Number(nodeValue);
    if (!Number.isFinite(idx) || idx < 0) return;
    const body = document.getElementById(`plant-body-${idx}`);
    if (body && !body.classList.contains('open')) body.classList.add('open');

    const targetInput = document.querySelector(`[data-pi="${idx}"][data-f="name"]`)
      || document.querySelector(`[data-pi="${idx}"][data-f="flowrate"]`);
    if (targetInput) {
      targetInput.scrollIntoView({ behavior: 'smooth', block: 'center' });
      targetInput.focus();
    }
    return;
  }

  if (nodeType === 'merge') {
    const mergeNameInputs = Array.from(document.querySelectorAll('.merge-name'));
    const targetInput = mergeNameInputs.find(el => el.dataset.mkey === nodeValue);
    if (!targetInput) return;

    const mergeIndex = mergeNameInputs.indexOf(targetInput);
    if (mergeIndex >= 0) {
      const body = document.getElementById(`merge-body-${mergeIndex}`);
      if (body && !body.classList.contains('open')) body.classList.add('open');
    }
    targetInput.scrollIntoView({ behavior: 'smooth', block: 'center' });
    targetInput.focus();
    return;
  }

  if (nodeType === 'storage') {
    const storageInput = document.getElementById('cfg-storage-name');
    if (storageInput) {
      storageInput.scrollIntoView({ behavior: 'smooth', block: 'center' });
      storageInput.focus();
    }
  }
}

async function openConfigEditorForMapNode(nodeId) {
  await openConfigEditor();
  _focusConfigEditorForNode(nodeId);
}

function _getOpenPlantBodyIndexes() {
  const openBodies = document.querySelectorAll('.plant-card-body.open[id^="plant-body-"]');
  const indexes = new Set();
  openBodies.forEach(body => {
    const idxText = String(body.id || '').replace('plant-body-', '');
    const idx = Number(idxText);
    if (Number.isFinite(idx) && idx >= 0) indexes.add(idx);
  });
  return indexes;
}

function renderConfigEditor(options = {}) {
  const openPlantIndexes = options.openPlantIndexes instanceof Set
    ? options.openPlantIndexes
    : _getOpenPlantBodyIndexes();
  const openContaminantPickerIndexes = new Set(
    Array.isArray(options.openContaminantPickerIndexes)
      ? options.openContaminantPickerIndexes.map(v => Number(v)).filter(v => Number.isFinite(v) && v >= 0)
      : []
  );

  document.getElementById('cfg-p-bara').value = _cfg.p_bara ?? '';
  document.getElementById('cfg-storage-name').value = _cfg.storage_name ?? 'Storage';

  const { baseSpecies, extraSpecies, allowExtras } = _getConfigInletSpeciesForModel();
  const activeSpecies = [...baseSpecies, ...extraSpecies];
  const availableToAdd = allowExtras ? _getAvailablePhpitzContaminantsForAdd() : [];

  const extraControlsHtml = allowExtras
    ? `<div style="font-size:.78rem;color:#4a5568;margin:.1rem 0 .8rem;">PH_PITZ is active. You can add contaminants from each plant inlet section.</div>`
    : `<div style="font-size:.78rem;color:#4a5568;margin:.1rem 0 .8rem;">Tocomo models are limited to O2, H2O, H2S, SO2, and NO2.</div>`;

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

  openPlantIndexes.forEach(idx => {
    const body = document.getElementById(`plant-body-${idx}`);
    if (body) body.classList.add('open');
  });
  openContaminantPickerIndexes.forEach(idx => {
    const row = document.getElementById(`cfg-add-contaminant-row-${idx}`);
    if (row) row.style.display = 'flex';
  });

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

  if (!_cfg.merge_pipe_inputs || typeof _cfg.merge_pipe_inputs !== 'object') {
    _cfg.merge_pipe_inputs = {};
  }

  const existingNames = new Set(Object.keys(_cfg.merge_pipe_inputs));
  let nextIndex = 1;
  while (existingNames.has(`Merge ${nextIndex}`)) {
    nextIndex += 1;
  }

  const placeholderName = `Merge ${nextIndex}`;
  _cfg.merge_pipe_inputs[placeholderName] = { pipelength: 10000, pipediameter: 0.5 };
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
